from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_EXTRA_FIELDS = {
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "username",
    "role",
    "action",
    "resource_type",
    "resource_id",
    "collection",
}


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get("-")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_ctx.get("-")),
        }
        for field in _EXTRA_FIELDS:
            if field == "request_id":
                continue
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(log_level: str) -> None:
    root_logger = logging.getLogger()
    level_value = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level_value)

    for handler in root_logger.handlers:
        handler.addFilter(RequestContextFilter())
        handler.setFormatter(JsonFormatter())
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(RequestContextFilter())
        handler.setFormatter(JsonFormatter())
        root_logger.addHandler(handler)

