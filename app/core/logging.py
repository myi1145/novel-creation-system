from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.core.logging_context import get_log_context

_LOG_INITIALIZED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "category": getattr(record, "category", "app"),
            "message": record.getMessage(),
        }
        payload.update(get_log_context())
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(sanitize_for_logging(payload), ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = get_log_context()
        extra_fields = getattr(record, "extra_fields", {})
        if not isinstance(extra_fields, dict):
            extra_fields = {}
        timestamp = self.formatTime(record, self.datefmt)
        method = extra_fields.get("method") or getattr(record, "method", None)
        path = extra_fields.get("path") or getattr(record, "path", None)
        status_code = extra_fields.get("status_code", getattr(record, "status_code", None))
        duration_ms = extra_fields.get("duration_ms", getattr(record, "duration_ms", None))
        request_id = extra_fields.get("request_id") or getattr(record, "request_id", None) or context.get("request_id")

        parts = [f"{timestamp} [{record.levelname}] {record.getMessage()}"]
        http_parts: list[str] = []
        if method:
            http_parts.append(str(method))
        if path:
            http_parts.append(str(path))
        if status_code is not None:
            http_parts.append(f"status={status_code}")
        if duration_ms is not None:
            http_parts.append(f"duration={duration_ms}ms")
        if http_parts:
            parts.append(" | " + " ".join(http_parts))
        if request_id:
            parts.append(f" | request_id={request_id}")
        return "".join(parts)


class RuntimeLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            return True
        if record.name in {"novel.app", "novel.error"}:
            return True
        return False


def sanitize_for_logging(value: Any, *, max_str_len: int = 300, max_items: int = 8) -> Any:
    blocked_keys = {"api_key", "authorization", "token", "password", "secret", "agent_api_key"}
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(blocked in lowered for blocked in blocked_keys):
                sanitized[key] = "***"
                continue
            sanitized[key] = sanitize_for_logging(item, max_str_len=max_str_len, max_items=max_items)
        return sanitized
    if isinstance(value, (list, tuple)):
        trimmed = list(value)[:max_items]
        items = [sanitize_for_logging(item, max_str_len=max_str_len, max_items=max_items) for item in trimmed]
        if len(value) > max_items:
            items.append(f"...({len(value) - max_items} more items)")
        return items
    if isinstance(value, str):
        if len(value) > max_str_len:
            return f"{value[:max_str_len]}...(truncated, len={len(value)})"
        return value
    return value


def setup_logging(level: str = "INFO") -> None:
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    json_formatter = JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z")
    console_formatter = ConsoleFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(console_formatter)
    stream_handler.addFilter(RuntimeLogFilter())
    root_logger.addHandler(stream_handler)

    log_dir = PROJECT_ROOT / "logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(json_formatter)
    file_handler.addFilter(RuntimeLogFilter())
    root_logger.addHandler(file_handler)

    for noisy_logger in ("asyncio", "httpx", "httpcore", "urllib3", "uvicorn.access"):
        logging.getLogger(noisy_logger).setLevel(logging.ERROR)

    _LOG_INITIALIZED = True


def get_logger(category: str = "app") -> logging.LoggerAdapter:
    logger = logging.getLogger(f"novel.{category}")
    return logging.LoggerAdapter(logger, {"category": category})
