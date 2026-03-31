from __future__ import annotations

import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.core.logging_context import clear_log_context, set_log_context

logger = get_logger("app")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        trace_id = request.headers.get("X-Trace-ID")
        client_ip = request.client.host if request.client else None
        start = time.perf_counter()

        set_log_context(
            request_id=request_id,
            trace_id=trace_id,
            module="http",
            event="request",
            status="started",
        )
        logger.info(
            "收到请求",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                    "request_id": request_id,
                    "event": "request.received",
                    "status": "started",
                }
            },
        )

        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            response.headers["X-Request-ID"] = request_id
            set_log_context(status="success", event="request.completed")
            logger.info(
                "请求处理完成",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip,
                        "request_id": request_id,
                        "event": "request.completed",
                        "status": "success",
                    }
                },
            )
            return response
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            set_log_context(status="failed", event="request.failed")
            logger.exception(
                "请求处理失败",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip,
                        "request_id": request_id,
                        "event": "request.failed",
                        "status": "failed",
                    }
                },
            )
            raise
        finally:
            clear_log_context()
