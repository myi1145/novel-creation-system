from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT

_LOG_INITIALIZED = False


class ContextMergingLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = dict(self.extra)
        passed_extra = kwargs.get("extra")
        if isinstance(passed_extra, dict):
            extra.update(passed_extra)
        kwargs["extra"] = extra
        return msg, kwargs


class HumanReadableFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        message = f"{timestamp} [{record.levelname}] {record.getMessage()}"
        elapsed_ms = getattr(record, "elapsed_ms", None)
        if elapsed_ms is not None and elapsed_ms != "":
            message = f"{message} | 耗时={elapsed_ms}ms"
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return message


class RuntimeLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "novel.agent" and record.levelno < logging.ERROR:
            return False
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
    return ContextMergingLoggerAdapter(logger, {"category": category})
