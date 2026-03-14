"""
database.py — Async Database Engine & Session Factory
======================================================
This file sets up the SQLAlchemy async engine and session.

Concepts:
  - Engine: the low-level connection to SQLite / PostgreSQL.
  - SessionLocal: a factory that creates new DB sessions per request.
  - Base: every model (table) inherits from this.
  - init_db(): creates tables the first time the app starts.

We use async SQLAlchemy so the DB calls don't block the FastAPI event loop,
letting the server handle many requests concurrently.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,    # builds the async DB connection
    AsyncSession,           # async version of a SQLAlchemy session
    async_sessionmaker,     # factory class for creating sessions
)
from sqlalchemy.orm import DeclarativeBase  # modern base class for ORM models
from config import settings
import logging

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------
# create_async_engine builds the connection pool.
#   echo=True  → prints every SQL statement to stdout (helpful for debugging)
#   future=True → uses the modern 2.0 SQLAlchemy style
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,   # only log SQL when DEBUG=True
    future=True,
    # ---- SQLite-specific optimisation ----
    # connect_args is ignored for PostgreSQL, but for SQLite we need
    # check_same_thread=False so multiple coroutines can share one connection.
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)


# ------------------------------------------------------------------
# Session factory
# ------------------------------------------------------------------
# expire_on_commit=False  → keep model attributes accessible after commit
#   (important in async code where we might access attributes after session closes)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ------------------------------------------------------------------
# Declarative Base
# ------------------------------------------------------------------
# All ORM model classes (tables) inherit from Base.
# SQLAlchemy looks at all subclasses of Base when creating tables.
class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------
# Dependency — used with FastAPI's Depends()
# ------------------------------------------------------------------
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that yields one DB session per HTTP request.

    Usage in a route:
        @app.get("/tasks")
        async def list_tasks(db: AsyncSession = Depends(get_db)):
            ...

    The 'async with' block guarantees the session is closed even if
    an exception is raised mid-request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session          # hand the session to the route handler
            await session.commit() # auto-commit if no error was raised
        except Exception:
            await session.rollback()  # undo any partial writes on error
            raise


# ------------------------------------------------------------------
# Table creation
# ------------------------------------------------------------------
async def init_db():
    """
    Creates all tables defined in models.py the first time the app starts.
    In production you would typically use Alembic migrations instead,
    but create_all is fine for development and demo projects.
    """
    # We import models here (not at the top) to avoid circular imports.
    # Importing models registers them on Base.metadata so SQLAlchemy knows
    # which tables to create.
    import models  # noqa: F401 — side-effect import to register models

    logger.info("Initialising database tables…")
    async with engine.begin() as conn:
        # create_all is idempotent — safe to call on every startup
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database ready.")
