from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


DEFAULT_LOG_CONTEXT: dict[str, Any] = {
    "request_id": None,
    "trace_id": None,
    "workflow_run_id": None,
    "project_id": None,
    "chapter_no": None,
    "module": None,
    "event": None,
    "status": None,
}


def get_log_context() -> dict[str, Any]:
    current = _LOG_CONTEXT.get()
    return {**DEFAULT_LOG_CONTEXT, **current}


def set_log_context(**kwargs: Any) -> Token:
    merged = get_log_context()
    for key, value in kwargs.items():
        if key in DEFAULT_LOG_CONTEXT:
            merged[key] = value
    return _LOG_CONTEXT.set(merged)


def clear_log_context() -> None:
    _LOG_CONTEXT.set(dict(DEFAULT_LOG_CONTEXT))


def reset_log_context(token: Token) -> None:
    _LOG_CONTEXT.reset(token)
