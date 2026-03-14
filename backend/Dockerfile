# backend/Dockerfile
# ===================
# Multi-stage build for the FastAPI backend.
#
# Stage 1 (builder): installs dependencies into a virtual env
# Stage 2 (runtime): copies only the venv + app code — no build tools
# This keeps the final image small and reduces the attack surface.

# ---- Stage 1: Install dependencies ----------------------------------
FROM python:3.11-slim AS builder

# Set working directory inside the container
WORKDIR /build

# Copy only requirements first (Docker caches this layer if requirements.txt
# hasn't changed — speeds up rebuilds when you only change Python files)
COPY requirements.txt .

# Create a virtual environment and install packages into it
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Runtime image -----------------------------------------
FROM python:3.11-slim AS runtime

# Install curl (needed by the Docker healthcheck in docker-compose.yml)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Activate the virtual env for all subsequent RUN / CMD instructions
ENV PATH="/opt/venv/bin:$PATH"

# Non-root user for security best practice
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose the FastAPI port
EXPOSE 8000

# Default startup command — use uvicorn to serve the app
# --no-access-log keeps the Docker logs clean; remove if you want request logs
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
