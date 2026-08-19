"""Logging configuration, request correlation IDs, and Prometheus metrics."""

import logging
import time
import uuid
from logging.config import dictConfig

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from src.config import settings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)


def configure_logging() -> None:
    """Configure structured, level-appropriate logging for the application."""
    level = "DEBUG" if settings.DEBUG else "INFO"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] "
                    "[req=%(request_id)s] %(message)s",
                    "defaults": {"request_id": "-"},
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "a3zen": {"handlers": ["console"], "level": level, "propagate": False},
            },
        }
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to each request and record Prometheus metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed = time.perf_counter() - start
            # Use the matched route template (not the raw path) to bound label cardinality.
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
        response.headers["X-Request-ID"] = request_id
        return response


def metrics_response() -> Response:
    """Render the Prometheus exposition payload."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


logging.getLogger("a3zen").debug("observability module loaded")
