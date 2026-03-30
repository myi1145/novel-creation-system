from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.canon import InitCanonSnapshotRequest
from app.services.canon_service import canon_service
from app.utils.response import success_response

router = APIRouter()


@router.post("/snapshots/init")
def init_snapshot(request: InitCanonSnapshotRequest, db: Session = Depends(get_db)) -> dict:
    snapshot = canon_service.init_snapshot(db=db, request=request)
    return success_response(data=snapshot.model_dump(mode="json"), message="canon snapshot initialized")


@router.get("/snapshots")
def list_snapshots(project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    snapshots = [item.model_dump(mode="json") for item in canon_service.list_snapshots(db=db, project_id=project_id)]
    return success_response(data=snapshots)
