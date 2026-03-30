from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.changeset import ProposeChangeSetRequest, RollbackChangeSetRequest
from app.services.changeset_service import changeset_service
from app.utils.response import success_response

router = APIRouter()


@router.post("/propose")
def propose_changeset(request: ProposeChangeSetRequest, db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.propose(db=db, request=request)
    return success_response(data=changeset.model_dump(mode="json"), message="changeset proposed")


@router.post("/{changeset_id}/approve")
def approve_changeset(changeset_id: str, approved_by: str = Body(embed=True), db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.approve(db=db, changeset_id=changeset_id, approved_by=approved_by)
    return success_response(data=changeset.model_dump(mode="json"), message="changeset approved")


@router.post("/{changeset_id}/reject")
def reject_changeset(changeset_id: str, rejected_by: str = Body(embed=True), reason: str | None = Body(default=None, embed=True), db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.reject(db=db, changeset_id=changeset_id, rejected_by=rejected_by, reason=reason)
    return success_response(data=changeset.model_dump(mode="json"), message="changeset rejected")


@router.post("/{changeset_id}/apply")
def apply_changeset(changeset_id: str, db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.apply(db=db, changeset_id=changeset_id)
    return success_response(data=changeset.model_dump(mode="json"), message="changeset applied")


@router.post("/{changeset_id}/rollback")
def rollback_changeset(changeset_id: str, request: RollbackChangeSetRequest, db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.rollback(db=db, changeset_id=changeset_id, rolled_back_by=request.rolled_back_by, reason=request.reason, workflow_run_id=request.workflow_run_id, trace_id=request.trace_id)
    return success_response(data=changeset.model_dump(mode="json"), message="changeset rolled back")


@router.get("")
def list_changesets(db: Session = Depends(get_db)) -> dict:
    changesets = [item.model_dump(mode="json") for item in changeset_service.list_changesets(db=db)]
    return success_response(data=changesets)
