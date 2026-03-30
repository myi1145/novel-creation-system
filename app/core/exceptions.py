class AppError(Exception):
    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message=message, code="NOT_FOUND", status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "资源状态冲突"):
        super().__init__(message=message, code="CONFLICT", status_code=409)


class ValidationError(AppError):
    def __init__(self, message: str = "请求参数不合法"):
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422)
