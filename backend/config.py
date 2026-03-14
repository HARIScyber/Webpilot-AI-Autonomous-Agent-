"""
config.py — Application Configuration
======================================
Loads all settings from environment variables (or .env file).
Uses Pydantic's BaseSettings so every value is validated at startup.

How it works:
  1. Python reads the .env file automatically (via python-dotenv).
  2. Each field has a sane default so the app can start without any .env file.
  3. Import `settings` anywhere in the app:  from config import settings
"""

import os
from pydantic_settings import BaseSettings  # pip install pydantic-settings
from functools import lru_cache             # caches the settings object (singleton)


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # TinyFish API
    # ------------------------------------------------------------------
    # Your secret API key — get one at https://tinyfish.ai
    TINYFISH_API_KEY: str = "your-tinyfish-api-key-here"

    # The SSE endpoint for running automations
    TINYFISH_BASE_URL: str = "https://agent.tinyfish.ai/v1/automation/run-sse"

    # How many seconds to wait for TinyFish to respond before giving up
    TINYFISH_TIMEOUT: int = 300  # 5 minutes — browser tasks can take a while

    # Demo mode: simulate task execution without a real API key (for testing)
    DEMO_MODE: bool = False

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    # SQLite by default (no server needed — great for local dev / students).
    # Switch to PostgreSQL for production:
    #   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/webpilot
    DATABASE_URL: str = "sqlite+aiosqlite:///./webpilot.db"

    # ------------------------------------------------------------------
    # FastAPI / CORS
    # ------------------------------------------------------------------
    # The React dev server runs on port 3000 — we allow it here so the
    # browser doesn't block cross-origin requests.
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Uvicorn host and port
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Set DEBUG=True during development to see detailed tracebacks in the API
    DEBUG: bool = True

    # ------------------------------------------------------------------
    # App metadata
    # ------------------------------------------------------------------
    APP_NAME: str = "WebPilot AI"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Autonomous Web Agent powered by TinyFish"

    class Config:
        # Tell Pydantic to read from the .env file in the project root
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow extra env vars without raising an error
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached singleton of the Settings object.
    Using lru_cache means we only read the .env file once, not on every import.
    """
    return Settings()


# Convenience alias — most files just do:  from config import settings
settings = get_settings()
