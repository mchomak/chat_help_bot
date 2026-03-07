# syntax=docker/dockerfile:1
# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps
RUN pip install --upgrade pip

COPY pyproject.toml .
COPY app/ app/

# Install only prod dependencies into a prefix we'll copy
RUN pip install --no-cache-dir --prefix=/install .


# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r botuser && useradd -r -g botuser botuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

# Create temp dir and set permissions
RUN mkdir -p /tmp/chat_help_bot && chown botuser:botuser /tmp/chat_help_bot

USER botuser

# aiohttp webhook server
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "-m", "app.main"]
