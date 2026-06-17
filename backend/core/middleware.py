"""
core/middleware.py — FastAPI middleware stack.

Registers:
  1. CORS middleware (reads allowed origins from config)
  2. Request ID injection (X-Request-ID header)
  3. Response time logging (X-Response-Time-Ms header)
"""

import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the app. Call once during app factory."""
    settings = get_settings()

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID + Response Time ────────────────────────────────────────────
    app.add_middleware(RequestMetaMiddleware)


class RequestMetaMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID and X-Response-Time-Ms into every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        # Make request_id available to route handlers via request.state
        request.state.request_id = request_id

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        logger.debug(
            f"{request.method} {request.url.path} → {response.status_code} ({elapsed_ms}ms)",
        )
        return response