# --- Stage 1: Build with uv ---------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code and install the project
COPY app/ app/
RUN uv sync --frozen --no-dev

# --- Stage 2: Runtime ---------------------------------------------------------
FROM python:3.12-slim-bookworm

# Non-root user
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

# Ensure venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Cloud Run injects PORT (default 8080)
ENV PORT=8080

USER appuser

EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn app.server:fastapi_app --host 0.0.0.0 --port ${PORT}"]
