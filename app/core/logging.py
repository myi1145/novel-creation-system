from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.core.logging_context import get_log_context

_LOG_INITIALIZED = False


class HumanReadableFormatter(logging.Formatter):
    PRIORITY_KEYS = [
        "method",
        "path",
        "status_code",
        "duration_ms",
        "project_id",
        "chapter_no",
        "workflow_run_id",
        "next_action",
        "stop_reason",
        "blueprint_id",
        "changeset_id",
        "published_chapter_id",
    ]

    def _stringify(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return ",".join(str(item) for item in value)
        return str(value)

    def format(self, record: logging.LogRecord) -> str:
        combined = sanitize_for_logging(get_log_context())
        extra_fields = getattr(record, "extra_fields", {})
        if not isinstance(extra_fields, dict):
            extra_fields = {}
        combined.update(sanitize_for_logging(extra_fields))
        timestamp = self.formatTime(record, self.datefmt)
        parts = [f"{timestamp} [{record.levelname}] {record.getMessage()}"]
        used: set[str] = set()
        for key in self.PRIORITY_KEYS:
            value = combined.get(key)
            if value is None or value == "":
                continue
            display = f"{key}={self._stringify(value)}"
            if key == "duration_ms":
                display = f"duration={self._stringify(value)}ms"
            parts.append(f" | {display}")
            used.add(key)
        for key in sorted(combined.keys()):
            if key in used or key in {"module", "event", "status", "request_id", "trace_id"}:
                continue
            value = combined.get(key)
            if value is None or value == "":
                continue
            parts.append(f" | {key}={self._stringify(value)}")
        if record.exc_info:
            error_type = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            parts.append(f" | error_type={error_type}")
        return "".join(parts)


class RuntimeLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            return True
        if record.name in {"novel.app", "novel.error", "novel.workflow", "novel.agent"}:
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
    text_formatter = HumanReadableFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(text_formatter)
    stream_handler.addFilter(RuntimeLogFilter())
    root_logger.addHandler(stream_handler)

    log_dir = PROJECT_ROOT / "logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(text_formatter)
    file_handler.addFilter(RuntimeLogFilter())
    root_logger.addHandler(file_handler)

    for noisy_logger in ("asyncio", "httpx", "httpcore", "urllib3", "uvicorn.access"):
        logging.getLogger(noisy_logger).setLevel(logging.ERROR)

    _LOG_INITIALIZED = True


def get_logger(category: str = "app") -> logging.LoggerAdapter:
    logger = logging.getLogger(f"novel.{category}")
    return logging.LoggerAdapter(logger, {"category": category})
