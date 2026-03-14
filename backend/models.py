"""
models.py — SQLAlchemy ORM Models (Database Tables)
====================================================
Each class here maps to a table in the database.

Tables:
  - Task       → one automation job the user submitted
  - TaskLog    → individual SSE progress events for a task
  - TaskResult → the final extracted data from a completed task

Relationships:
  Task 1──* TaskLog    (one task produces many log lines)
  Task 1──1 TaskResult (one task produces one final result)
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, JSON, DateTime, Enum as SAEnum,
    ForeignKey, Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base  # our declarative base from database.py


# ------------------------------------------------------------------
# Enumerations
# ------------------------------------------------------------------

class TaskStatus(str, enum.Enum):
    """
    Lifecycle states of an automation task.
    Using str + enum means the raw value (e.g. "running") is stored in SQLite,
    which is more readable than an integer code.
    """
    PENDING   = "pending"    # just created, not yet sent to TinyFish
    RUNNING   = "running"    # TinyFish agent is actively working
    COMPLETED = "completed"  # successfully finished, result available
    FAILED    = "failed"     # TinyFish returned an error or timed out


class LogLevel(str, enum.Enum):
    """Severity levels for task log entries."""
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"
    DEBUG   = "debug"


# ------------------------------------------------------------------
# Task — core entity
# ------------------------------------------------------------------

class Task(Base):
    """
    Represents one automation job.

    Example row:
      id          = "abc123"
      title       = "Find AirPods Pro price"
      target_url  = "https://amazon.com"
      goal        = "Search AirPods Pro and return the price"
      status      = "completed"
      created_at  = 2024-03-12 10:00:00
      completed_at= 2024-03-12 10:01:23
    """

    __tablename__ = "tasks"

    # Primary key — UUID means no sequential ID leakage and works across DBs
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Human-readable label (user can optionally name the task)
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # The website the agent should start on
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Natural language instruction sent to TinyFish
    goal: Mapped[str] = mapped_column(Text, nullable=False)

    # Current lifecycle status (see TaskStatus enum above)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,   # we query by status a lot, so index it
    )

    # Optional category helps the frontend group tasks
    # e.g. "price_check", "job_search", "availability_check"
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps — all stored in UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # How long the task took in seconds (filled in on completion)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error message if status == FAILED
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Relationships (back-references so we can do task.logs, task.result)
    # ------------------------------------------------------------------
    logs: Mapped[list["TaskLog"]] = relationship(
        "TaskLog",
        back_populates="task",
        cascade="all, delete-orphan",  # deleting a task deletes its logs
        order_by="TaskLog.timestamp",
    )
    result: Mapped["TaskResult | None"] = relationship(
        "TaskResult",
        back_populates="task",
        cascade="all, delete-orphan",
        uselist=False,  # one-to-one
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id!r} title={self.title!r} status={self.status}>"


# ------------------------------------------------------------------
# TaskLog — streaming progress events
# ------------------------------------------------------------------

class TaskLog(Base):
    """
    Each SSE event emitted by TinyFish (STARTED, PROGRESS, COMPLETE)
    becomes one row here.  This gives us an audit trail and lets the
    frontend replay exactly what the agent did.
    """

    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key back to the parent Task
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # When this event was received by our backend
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # The raw SSE event type: "STARTED" | "PROGRESS" | "COMPLETE" | "ERROR"
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Human-readable description of what the agent just did
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Log severity level
    level: Mapped[LogLevel] = mapped_column(
        SAEnum(LogLevel), default=LogLevel.INFO, nullable=False
    )

    # Optional raw JSON data from TinyFish (screenshot URL, action details, etc.)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationship back to parent task
    task: Mapped["Task"] = relationship("Task", back_populates="logs")

    def __repr__(self) -> str:
        return f"<TaskLog task_id={self.task_id!r} event={self.event_type!r}>"


# ------------------------------------------------------------------
# TaskResult — final extracted data
# ------------------------------------------------------------------

class TaskResult(Base):
    """
    Stores the final structured output that TinyFish extracted.
    Examples:
      • {"price": "$249.00", "title": "Apple AirPods Pro (2nd Gen)"}
      • {"jobs": [{"title": "ML Engineer", "company": "OpenAI", "link": "..."}]}
      • {"available": true, "stock": "In Stock"}
    """

    __tablename__ = "task_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # The structured result as JSON (flexible — different tasks return different shapes)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Raw text summary from TinyFish (always present, even if data is empty)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # URL of a screenshot taken by TinyFish at task completion (if available)
    screenshot_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    task: Mapped["Task"] = relationship("Task", back_populates="result")

    def __repr__(self) -> str:
        return f"<TaskResult task_id={self.task_id!r}>"
