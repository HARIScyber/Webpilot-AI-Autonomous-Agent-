"""
schemas.py — Pydantic Schemas (Request / Response Shapes)
==========================================================
These classes define the JSON structure that our API accepts and returns.
They are completely separate from the SQLAlchemy models in models.py.

Why keep them separate?
  - The ORM model is the DB representation (columns, relationships).
  - The schema is the API representation (what JSON looks like over the wire).
  - Keeping them separate lets us hide internal fields, rename fields for
    the API, and add extra validation without touching the DB layer.

Pattern:
  TaskCreate   → data the client sends us  (input)
  TaskResponse → data we send back         (output)
  TaskDetail   → richer output with logs and result included
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, HttpUrl, field_validator


# ======================================================================
# Shared / base schemas
# ======================================================================

class TaskLogResponse(BaseModel):
    """
    A single log line shown in the UI timeline.
    Example: {"event_type": "PROGRESS", "message": "Clicked search button", "level": "info"}
    """
    id: int
    event_type: str
    message: str
    level: str
    timestamp: datetime
    metadata_json: dict[str, Any] | None = None

    model_config = {"from_attributes": True}  # lets Pydantic read SQLAlchemy models


class TaskResultResponse(BaseModel):
    """
    The final extracted payload.
    Example: {"data": {"price": "$249"}, "raw_text": "The price is $249", "screenshot_url": null}
    """
    data: dict[str, Any] | None = None
    raw_text: str | None = None
    screenshot_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ======================================================================
# Task input schemas (what the client sends)
# ======================================================================

class TaskCreate(BaseModel):
    """
    Payload for POST /api/tasks — create and run a new automation task.

    Example request body:
    {
        "title": "Find AirPods Pro price",
        "target_url": "https://www.amazon.com",
        "goal": "Search for AirPods Pro and return the price",
        "category": "price_check"
    }
    """
    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Short human-readable name for the task",
        examples=["Find AirPods Pro price on Amazon"],
    )
    target_url: str = Field(
        ...,
        description="The URL where the agent should start browsing",
        examples=["https://www.amazon.com"],
    )
    goal: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural language instruction for the TinyFish agent",
        examples=["Search for AirPods Pro and return the cheapest price"],
    )
    category: str | None = Field(
        default=None,
        max_length=100,
        description="Optional tag for grouping tasks in the UI",
        examples=["price_check", "job_search", "availability_check"],
    )

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """
        Ensure the URL has a proper scheme to avoid sending the agent to a broken URL.
        We do a simple string check rather than using HttpUrl so the error
        message is friendlier for students.
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError("target_url must start with http:// or https://")
        return v.strip()

    @field_validator("goal")
    @classmethod
    def goal_not_empty(cls, v: str) -> str:
        """Strip whitespace and confirm the goal isn't just spaces."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("goal cannot be blank")
        return cleaned


# ======================================================================
# Task output schemas (what we send back)
# ======================================================================

class TaskResponse(BaseModel):
    """
    Lightweight task summary returned in lists and after creation.
    Does NOT include logs or result to keep list responses small.
    """
    id: str
    title: str
    target_url: str
    goal: str
    status: str
    category: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class TaskDetail(TaskResponse):
    """
    Full task detail including logs and the final result.
    Returned by GET /api/tasks/{id}.
    """
    logs: list[TaskLogResponse] = Field(default_factory=list)
    result: TaskResultResponse | None = None


class TaskListResponse(BaseModel):
    """
    Paginated list of tasks.
    Example: {"tasks": [...], "total": 42, "page": 1, "page_size": 20}
    """
    tasks: list[TaskResponse]
    total: int
    page: int
    page_size: int


# ======================================================================
# Live streaming schema
# ======================================================================

class SSEEvent(BaseModel):
    """
    The shape of each Server-Sent Event we forward to the frontend.
    The frontend's EventSource listener receives these one at a time.

    Example JSON the frontend receives:
    {
        "event": "PROGRESS",
        "task_id": "abc-123",
        "message": "Typed 'AirPods Pro' into the search box",
        "data": null
    }
    """
    event: str          # STARTED | PROGRESS | COMPLETE | ERROR
    task_id: str
    message: str
    data: dict[str, Any] | None = None


# ======================================================================
# Health check
# ======================================================================

class HealthResponse(BaseModel):
    """Simple response for the /api/health endpoint."""
    status: str = "ok"
    app: str
    version: str
    database: str = "connected"
