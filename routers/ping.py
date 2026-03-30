from fastapi import APIRouter

from app.utils.response import success_response

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return success_response(data={"pong": "pong"})
