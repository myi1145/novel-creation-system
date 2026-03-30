from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.gate import RunGateReviewRequest
from app.services.gate_service import gate_service
from app.utils.response import success_response

router = APIRouter()


@router.post("/reviews")
def run_gate_reviews(request: RunGateReviewRequest, db: Session = Depends(get_db)) -> dict:
    results = gate_service.run_reviews(db=db, request=request)
    return success_response(
        data={
            "gate_names": [gate.value for gate in request.gate_names],
            "results": [item.model_dump(mode="json") for item in results],
        },
        message="闸门审查已完成",
    )
