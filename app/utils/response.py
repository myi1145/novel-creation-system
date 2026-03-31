from typing import Any


def success_response(data: Any = None, message: str = "success") -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_response(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
