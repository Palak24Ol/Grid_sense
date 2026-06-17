"""
core/logging.py — Structured JSON logging for GridSense backend.

Usage:
    from backend.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Prediction complete", extra={"inference_ms": 34})
"""

import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Merge any extra fields passed via extra={}
        for key, val in record.__dict__.items():
            if key not in (
                "args", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno",
                "message", "module", "msecs", "msg", "name", "pathname",
                "process", "processName", "relativeCreated", "stack_info",
                "taskName", "thread", "threadName",
            ):
                payload[key] = val

        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Uses JSON formatter in production, plain in dev."""
    from backend.config import get_settings

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    handler = logging.StreamHandler(sys.stdout)

    settings = get_settings()
    if settings.is_production:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if not settings.is_production else logging.INFO)
    logger.propagate = False
    return logger