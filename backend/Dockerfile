# LDIP Backend Dockerfile
# Multi-stage build for production optimization

# ==============================================================================
# Stage 1: Builder - Install dependencies
# ==============================================================================
FROM python:3.12-slim AS builder

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
# Create virtual environment in container
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN uv sync --frozen --no-install-project --no-dev

# ==============================================================================
# Stage 2: Runtime - Final production image
# ==============================================================================
FROM python:3.12-slim AS runtime

# Create non-root user for security
RUN groupadd --gid 1000 ldip && \
    useradd --uid 1000 --gid ldip --shell /bin/bash --create-home ldip

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=ldip:ldip . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER ldip

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health')" || exit 1

# Run the application with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
