from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.utils.response import error_response

logger = get_logger("error")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        message = exc.message
        if exc.code == "CONFLICT":
            if "章目标" in exc.message and ("已存在" in exc.message or "重复" in exc.message):
                message = "当前项目下该章节目标已存在，不能重复创建"
            elif "manual" in exc.message or "人工" in exc.message:
                message = "非法恢复执行：请先完成人工审阅流程再继续"
        logger.warning(
            "业务请求失败",
            extra={"extra_fields": {"event": "app_error", "status": "failed", "error_code": exc.code, "error_message": message}},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(code=exc.code, message=message, details=exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("请求参数缺失或格式不正确", extra={"extra_fields": {"event": "request_validation_error", "status": "failed"}})
        return JSONResponse(
            status_code=422,
            content=error_response(
                code="MISSING_REQUIRED_PARAMETERS",
                message="请求参数缺失或格式不正确，请检查后重试",
                details={"errors": exc.errors()[:5]},
            ),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        raw = str(exc.orig) if getattr(exc, "orig", None) is not None else str(exc)
        message = "数据冲突，请勿重复创建或提交相同记录"
        if "unique" in raw.lower() or "duplicate" in raw.lower():
            message = "唯一约束冲突：记录已存在，请勿重复创建"
        logger.exception("数据库约束冲突", extra={"extra_fields": {"event": "db_integrity_error", "status": "failed"}})
        return JSONResponse(
            status_code=409,
            content=error_response(code="UNIQUE_CONSTRAINT_CONFLICT", message=message, details={}),
        )

    @app.exception_handler(Exception)
    async def handle_generic_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("系统内部错误", extra={"extra_fields": {"event": "internal_error", "status": "failed"}})
        return JSONResponse(
            status_code=500,
            content=error_response(code="INTERNAL_SERVER_ERROR", message="系统内部异常，请稍后重试或联系管理员", details={}),
        )
