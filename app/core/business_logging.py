from __future__ import annotations

from time import perf_counter
from typing import Any

from app.core.logging import get_logger, sanitize_for_logging
from app.core.logging_context import set_log_context


def truncate_ids(values: list[str] | None, *, max_items: int = 6) -> list[str]:
    if not values:
        return []
    items = [str(item) for item in values[:max_items]]
    if len(values) > max_items:
        items.append(f"...(+{len(values) - max_items})")
    return items


class StepLogScope:
    def __init__(
        self,
        *,
        logger_name: str,
        module: str,
        event: str,
        message_started: str,
        start_fields: dict[str, Any] | None = None,
    ) -> None:
        self._logger = get_logger(logger_name)
        self._module = module
        self._event = event
        self._start = perf_counter()
        set_log_context(module=module, event=event, status="started")
        self._logger.info(
            message_started,
            extra={"extra_fields": {"module": module, "event": event, "status": "started", **sanitize_for_logging(start_fields or {})}},
        )

    def success(self, message: str, **fields: Any) -> None:
        latency_ms = int((perf_counter() - self._start) * 1000)
        set_log_context(module=self._module, event=self._event, status="success")
        self._logger.info(
            message,
            extra={
                "extra_fields": {
                    "module": self._module,
                    "event": self._event,
                    "status": "success",
                    "latency_ms": latency_ms,
                    **sanitize_for_logging(fields),
                }
            },
        )

    def failure(self, message: str, error: Exception, **fields: Any) -> None:
        latency_ms = int((perf_counter() - self._start) * 1000)
        set_log_context(module=self._module, event=self._event, status="failed")
        self._logger.exception(
            message,
            extra={
                "extra_fields": {
                    "module": self._module,
                    "event": self._event,
                    "status": "failed",
                    "latency_ms": latency_ms,
                    "error_message": str(error),
                    **sanitize_for_logging(fields),
                }
            },
        )
