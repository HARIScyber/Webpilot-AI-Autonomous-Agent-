"""
agent_service.py — TinyFish API Integration & Task Orchestration
=================================================================
This is the heart of WebPilot AI.  It:

  1. Takes a task from the database (status=PENDING)
  2. Sends it to the TinyFish SSE endpoint
  3. Reads the streaming response event-by-event
  4. Saves each event as a TaskLog row
  5. On COMPLETE, saves the TaskResult
  6. Updates the Task status throughout (RUNNING → COMPLETED/FAILED)

The module also exposes an async generator (stream_task_events) that
FastAPI uses to forward the SSE stream directly to the browser, giving
users live progress updates.

TinyFish SSE Event Format
--------------------------
Each line from TinyFish looks like:

    data: {"event":"PROGRESS","message":"Clicked search button","data":{...}}

We parse each `data:` line as JSON and act on the `event` field.
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx
from httpx_sse import aconnect_sse      # async SSE helper from httpx-sse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import settings
from models import Task, TaskLog, TaskResult, TaskStatus, LogLevel
from schemas import SSEEvent

logger = logging.getLogger(__name__)


# ======================================================================
# Low-level TinyFish API helpers
# ======================================================================

def _build_request_headers() -> dict[str, str]:
    """
    Build the headers required by every TinyFish request.
    The API key is read from settings (which reads from .env).
    """
    return {
        "X-API-Key": settings.TINYFISH_API_KEY,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",  # tell TinyFish we want SSE
    }


def _build_request_body(url: str, goal: str) -> dict[str, str]:
    """
    Construct the JSON payload for the TinyFish automation endpoint.

    Args:
        url:  The starting URL for the browser session.
        goal: Natural language instruction for the agent.

    Returns:
        A dict that will be serialised to JSON by httpx.
    """
    return {
        "url": url,
        "goal": goal,
    }


# ======================================================================
# Core execution: run a task and yield SSE events
# ======================================================================

async def execute_task_stream(
    task: Task,
    db: AsyncSession,
) -> AsyncGenerator[SSEEvent, None]:
    """
    Calls TinyFish, streams progress events, persists them, and yields
    SSEEvent objects so the FastAPI route can forward them to the browser.

    This is an async generator — callers use `async for event in execute_task_stream(...)`.

    Lifecycle:
      PENDING → RUNNING → COMPLETED (or FAILED)

    Args:
        task: The Task ORM object (already saved to DB with status=PENDING).
        db:   An open AsyncSession — we write logs here in real-time.

    Yields:
        SSEEvent objects (STARTED, PROGRESS, COMPLETE, ERROR).
    """
    start_time = datetime.now(timezone.utc)

    # ---- Mark task as RUNNING ----------------------------------------
    task.status = TaskStatus.RUNNING
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Task %s → RUNNING", task.id)

    yield SSEEvent(
        event="STARTED",
        task_id=task.id,
        message=f"Agent started. Navigating to {task.target_url}…",
    )

    # ---- Log the STARTED event to DB ---------------------------------
    await _save_log(
        db=db,
        task_id=task.id,
        event_type="STARTED",
        message=f"Task started. URL: {task.target_url} | Goal: {task.goal}",
        level=LogLevel.INFO,
    )

    # ---- Call TinyFish -----------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=settings.TINYFISH_TIMEOUT) as client:
            async with aconnect_sse(
                client,
                method="POST",
                url=settings.TINYFISH_BASE_URL,
                headers=_build_request_headers(),
                json=_build_request_body(task.target_url, task.goal),
            ) as event_source:

                # aconnect_sse raises if the HTTP status is not 2xx
                event_source.response.raise_for_status()

                # Iterate over each SSE event from TinyFish
                async for sse in event_source.aiter_sse():
                    # Each event has: sse.event, sse.data, sse.id, sse.retry
                    raw_event_type = (sse.event or "PROGRESS").upper()
                    raw_data_str   = sse.data or ""

                    # Try to parse the data as JSON
                    parsed_data: dict[str, Any] | None = None
                    message = raw_data_str  # fallback: use raw string as message

                    if raw_data_str:
                        try:
                            parsed_data = json.loads(raw_data_str)
                            # TinyFish sometimes nests the message under "message"
                            message = parsed_data.get("message", raw_data_str)
                        except json.JSONDecodeError:
                            # Not JSON — treat as plain text progress message
                            message = raw_data_str

                    logger.debug("TinyFish SSE [%s]: %s", raw_event_type, message)

                    # ---- Persist the log row ---------------------------
                    await _save_log(
                        db=db,
                        task_id=task.id,
                        event_type=raw_event_type,
                        message=message,
                        level=LogLevel.INFO,
                        metadata_json=parsed_data,
                    )

                    # ---- Yield progress to the browser ----------------
                    yield SSEEvent(
                        event=raw_event_type,
                        task_id=task.id,
                        message=message,
                        data=parsed_data,
                    )

                    # ---- Handle terminal events -----------------------
                    if raw_event_type == "COMPLETE":
                        await _handle_completion(
                            task=task,
                            db=db,
                            parsed_data=parsed_data,
                            start_time=start_time,
                        )
                        return  # generator done — stop iterating

                    elif raw_event_type == "ERROR":
                        error_msg = message or "TinyFish returned an error event"
                        await _handle_failure(task, db, error_msg, start_time)
                        return

        # If TinyFish closed the stream without a COMPLETE event
        # treat it as an unexpected completion
        await _handle_failure(
            task, db,
            "TinyFish stream ended without a COMPLETE event",
            start_time,
        )
        yield SSEEvent(
            event="ERROR",
            task_id=task.id,
            message="Stream ended unexpectedly. Please retry.",
        )

    except httpx.HTTPStatusError as exc:
        # TinyFish returned 4xx / 5xx
        error_msg = f"TinyFish API error {exc.response.status_code}: {exc.response.text}"
        logger.error(error_msg)
        await _handle_failure(task, db, error_msg, start_time)
        yield SSEEvent(event="ERROR", task_id=task.id, message=error_msg)

    except httpx.TimeoutException:
        error_msg = f"TinyFish request timed out after {settings.TINYFISH_TIMEOUT}s"
        logger.error(error_msg)
        await _handle_failure(task, db, error_msg, start_time)
        yield SSEEvent(event="ERROR", task_id=task.id, message=error_msg)

    except Exception as exc:
        error_msg = f"Unexpected error during task execution: {exc}"
        logger.exception(error_msg)
        await _handle_failure(task, db, error_msg, start_time)
        yield SSEEvent(event="ERROR", task_id=task.id, message=error_msg)


# ======================================================================
# Helper: persist a log row
# ======================================================================

async def _save_log(
    db: AsyncSession,
    task_id: str,
    event_type: str,
    message: str,
    level: LogLevel = LogLevel.INFO,
    metadata_json: dict | None = None,
) -> TaskLog:
    """Creates and flushes one TaskLog row."""
    log_entry = TaskLog(
        task_id=task_id,
        event_type=event_type,
        message=message,
        level=level,
        metadata_json=metadata_json,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    # flush() writes to DB without committing, keeping the transaction open
    await db.flush()
    return log_entry


# ======================================================================
# Helper: mark task as COMPLETED
# ======================================================================

async def _handle_completion(
    task: Task,
    db: AsyncSession,
    parsed_data: dict | None,
    start_time: datetime,
) -> None:
    """
    Saves the final result and marks the task as COMPLETED.
    Extracts the data payload from TinyFish's COMPLETE event.
    """
    now = datetime.now(timezone.utc)
    duration = int((now - start_time).total_seconds())

    task.status          = TaskStatus.COMPLETED
    task.completed_at    = now
    task.updated_at      = now
    task.duration_seconds = duration

    # Build the TaskResult row from the COMPLETE event's data
    result_data       = parsed_data or {}
    extracted_data    = result_data.get("data") or result_data.get("result")
    raw_text          = result_data.get("message") or result_data.get("summary") or str(result_data)
    screenshot_url    = result_data.get("screenshot") or result_data.get("screenshot_url")

    task_result = TaskResult(
        task_id=task.id,
        data=extracted_data,
        raw_text=raw_text,
        screenshot_url=screenshot_url,
    )
    db.add(task_result)
    await db.commit()
    logger.info("Task %s COMPLETED in %ds", task.id, duration)


# ======================================================================
# Helper: mark task as FAILED
# ======================================================================

async def _handle_failure(
    task: Task,
    db: AsyncSession,
    error_message: str,
    start_time: datetime,
) -> None:
    """Marks the task as FAILED and saves the error message."""
    now = datetime.now(timezone.utc)
    task.status           = TaskStatus.FAILED
    task.updated_at       = now
    task.completed_at     = now
    task.duration_seconds = int((now - start_time).total_seconds())
    task.error_message    = error_message

    await _save_log(
        db=db,
        task_id=task.id,
        event_type="ERROR",
        message=error_message,
        level=LogLevel.ERROR,
    )
    await db.commit()
    logger.warning("Task %s FAILED: %s", task.id, error_message)


# ======================================================================
# DB query helpers used by main.py routes
# ======================================================================

async def get_task_by_id(task_id: str, db: AsyncSession) -> Task | None:
    """Fetch a single task by UUID, or return None if not found."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def get_all_tasks(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    category_filter: str | None = None,
) -> tuple[list[Task], int]:
    """
    Returns a page of tasks (most recent first) plus the total count.

    Args:
        page:            Page number (1-indexed).
        page_size:       How many items per page.
        status_filter:   Only return tasks with this status (optional).
        category_filter: Only return tasks in this category (optional).

    Returns:
        (list_of_tasks, total_count)
    """
    query = select(Task)

    if status_filter:
        query = query.where(Task.status == status_filter)
    if category_filter:
        query = query.where(Task.category == category_filter)

    # Count total matching rows (for pagination metadata)
    count_result = await db.execute(select(Task).where(
        *([Task.status == status_filter] if status_filter else []),
        *([Task.category == category_filter] if category_filter else []),
    ))
    total = len(count_result.scalars().all())

    # Apply ordering and pagination
    query = (
        query
        .order_by(Task.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    return result.scalars().all(), total
