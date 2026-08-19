# Stride backend production image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install the uv package manager.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first (leverages Docker layer caching).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source and migration assets.
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Serve with multiple Uvicorn workers under Gunicorn. Cross-worker realtime is handled
# by the per-org Redis pub/sub sharding, so multiple workers are safe.
# Migrations are applied by a separate one-shot step (see docker-compose `migrate`),
# NOT here — running `alembic upgrade` in every worker would race on multi-replica deploys.
CMD ["uv", "run", "gunicorn", "src.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", "--error-logfile", "-"]
