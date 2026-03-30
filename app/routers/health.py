from fastapi import APIRouter

from app.utils.response import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return success_response(data={"status": "ok"})
