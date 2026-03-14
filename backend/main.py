"""
main.py — FastAPI Application Entry Point
==========================================
This file wires together all the pieces:
  - Creates the FastAPI app
  - Registers CORS middleware (so the React frontend can talk to us)
  - Defines all API routes
  - Starts the async DB on startup

API Endpoints:
  POST   /api/tasks              → create & run a new automation task
  GET    /api/tasks              → list all tasks (with pagination)
  GET    /api/tasks/{id}         → get full task detail (logs + result)
  DELETE /api/tasks/{id}         → delete a task
  GET    /api/tasks/{id}/stream  → SSE stream — live progress updates
  GET    /api/health             → health check

Run with:
  cd backend
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from config import settings
from database import get_db, init_db
import models
from models import Task, TaskStatus
import schemas
from schemas import (
    TaskCreate, TaskResponse, TaskDetail,
    TaskListResponse, HealthResponse,
)
import agent_service

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------
# Configure the root logger so all modules use the same format.
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Application lifespan (startup / shutdown logic)
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before `yield` runs at startup.
    Code after `yield` runs at shutdown.
    Using the new lifespan context manager is the modern FastAPI approach
    (replaces the older @app.on_event("startup") decorator).
    """
    # ---- Startup ----
    logger.info("Starting %s v%s…", settings.APP_NAME, settings.APP_VERSION)
    await init_db()          # create tables if they don't exist yet
    logger.info("API ready on http://%s:%s", settings.HOST, settings.PORT)
    yield
    # ---- Shutdown ----
    logger.info("Shutting down %s…", settings.APP_NAME)


# ------------------------------------------------------------------
# FastAPI app instance
# ------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs",        # Swagger UI  → http://localhost:8000/docs
    redoc_url="/redoc",      # ReDoc UI    → http://localhost:8000/redoc
    lifespan=lifespan,
)


# ------------------------------------------------------------------
# CORS Middleware
# ------------------------------------------------------------------
# Without this, the browser will block requests from localhost:3000
# (React) to localhost:8000 (FastAPI) because they're on different ports.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # only allow our React dev server
    allow_credentials=True,
    allow_methods=["*"],    # GET, POST, DELETE, etc.
    allow_headers=["*"],    # Content-Type, Authorization, etc.
)


# ======================================================================
# Routes
# ======================================================================

# -- Health check -------------------------------------------------------

@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health_check():
    """Returns 200 OK if the API is running. Used by Docker health checks."""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        database="connected",
    )


# -- Create & run a task ------------------------------------------------

@app.post(
    "/api/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new automation task",
    tags=["Tasks"],
)
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a Task record in the database with status=PENDING.

    The actual agent execution happens via the /stream endpoint — the
    browser connects there immediately after task creation.

    Why separate creation from streaming?
    → It lets the frontend store the task_id and reconnect if the SSE
      connection drops, without losing the task record.
    """
    task = Task(
        title=payload.title,
        target_url=payload.target_url,
        goal=payload.goal,
        category=payload.category,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()   # flush to get task.id assigned (UUID is set by Python)
    await db.commit()
    await db.refresh(task)

    logger.info("Created task %s: %r", task.id, task.title)
    return task


# -- List tasks ---------------------------------------------------------

@app.get(
    "/api/tasks",
    response_model=TaskListResponse,
    summary="List all tasks with optional filters",
    tags=["Tasks"],
)
async def list_tasks(
    page: int       = Query(default=1, ge=1, description="Page number (starts at 1)"),
    page_size: int  = Query(default=20, ge=1, le=100, description="Items per page"),
    status: str | None   = Query(default=None, description="Filter by task status"),
    category: str | None = Query(default=None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a paginated list of tasks, newest first.
    Use ?status=running or ?category=price_check to filter.
    """
    tasks, total = await agent_service.get_all_tasks(
        db=db,
        page=page,
        page_size=page_size,
        status_filter=status,
        category_filter=category,
    )
    return TaskListResponse(
        tasks=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


# -- Get task detail ----------------------------------------------------

@app.get(
    "/api/tasks/{task_id}",
    response_model=TaskDetail,
    summary="Get full task detail (with logs and result)",
    tags=["Tasks"],
)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a single task by ID, including all log entries and the
    final result (if the task has completed).
    """
    # Use selectinload to eagerly load logs and result in one query
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.logs),
            selectinload(Task.result),
        )
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id!r} not found",
        )
    return task


# -- Delete a task ------------------------------------------------------

@app.delete(
    "/api/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task and its logs/result",
    tags=["Tasks"],
)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently deletes a task and all associated logs/results.
    The cascade="all, delete-orphan" on the Task model handles cleanup.
    """
    task = await agent_service.get_task_by_id(task_id, db)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id!r} not found",
        )
    await db.delete(task)
    await db.commit()
    logger.info("Deleted task %s", task_id)
    # 204 No Content — no body returned


# -- SSE stream: live task execution ------------------------------------

@app.get(
    "/api/tasks/{task_id}/stream",
    summary="Stream live task progress via Server-Sent Events",
    tags=["Tasks"],
    responses={
        200: {"description": "SSE stream of task progress events"},
        404: {"description": "Task not found"},
        409: {"description": "Task is not in PENDING status"},
    },
)
async def stream_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Opens an SSE stream for the given task.

    The browser's EventSource connects here right after POST /api/tasks.
    Each event looks like:

        data: {"event": "PROGRESS", "task_id": "...", "message": "Clicked search"}\\n\\n

    The stream closes when the task reaches COMPLETE or ERROR.

    Note: we use a separate DB session inside the generator so the
    session stays open for the duration of the stream (which can be
    minutes long for complex tasks).
    """
    # Verify the task exists and is in PENDING state
    task = await agent_service.get_task_by_id(task_id, db)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")

    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        # Allow reconnecting to a running task (browser refresh)
        if task.status == TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=409,
                detail="Task already completed. Fetch result via GET /api/tasks/{id}",
            )
        if task.status == TaskStatus.FAILED:
            raise HTTPException(
                status_code=409,
                detail=f"Task failed: {task.error_message}",
            )

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Inner async generator that yields raw SSE-formatted strings.
        We create a fresh DB session here because the one from Depends(get_db)
        may close before our long-running stream finishes.
        """
        from database import AsyncSessionLocal  # import here to avoid circular

        async with AsyncSessionLocal() as stream_db:
            # Re-fetch the task within the new session
            result = await stream_db.execute(select(Task).where(Task.id == task_id))
            stream_task = result.scalar_one_or_none()

            if not stream_task:
                yield _sse_format({"event": "ERROR", "message": "Task not found"})
                return

            # Execute the task and stream events
            async for sse_event in agent_service.execute_task_stream(stream_task, stream_db):
                # Format as the SSE wire protocol:
                #   data: <json>\n\n
                yield _sse_format(sse_event.model_dump())

                # Small sleep to prevent overwhelming the browser
                await asyncio.sleep(0.01)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # These headers are important for SSE to work correctly in browsers
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering if behind proxy
        },
    )


# ======================================================================
# Utility
# ======================================================================

def _sse_format(data: dict) -> str:
    """
    Formats a dict as an SSE message string.
    SSE protocol: each message is `data: <payload>\\n\\n`
    The double newline signals the end of one event to the browser.
    """
    return f"data: {json.dumps(data)}\n\n"


# ======================================================================
# Dev server entry point
# ======================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,   # auto-reload on file changes when DEBUG=True
        log_level="debug" if settings.DEBUG else "info",
    )
