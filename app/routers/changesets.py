from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.changeset import ProposeChangeSetRequest, RollbackChangeSetRequest
from app.services.changeset_service import changeset_service
from app.utils.response import success_response

router = APIRouter()


@router.post("/propose")
def propose_changeset(request: ProposeChangeSetRequest, db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.propose(db=db, request=request)
    return success_response(data=changeset.model_dump(mode="json"), message="ChangeSet 已提议")


@router.post("/{changeset_id}/approve")
def approve_changeset(changeset_id: str, approved_by: str = Body(embed=True), db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.approve(db=db, changeset_id=changeset_id, approved_by=approved_by)
    return success_response(data=changeset.model_dump(mode="json"), message="ChangeSet 已审批通过")


@router.post("/{changeset_id}/reject")
def reject_changeset(changeset_id: str, rejected_by: str = Body(embed=True), reason: str | None = Body(default=None, embed=True), db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.reject(db=db, changeset_id=changeset_id, rejected_by=rejected_by, reason=reason)
    return success_response(data=changeset.model_dump(mode="json"), message="ChangeSet 已驳回")


@router.post("/{changeset_id}/apply")
def apply_changeset(changeset_id: str, db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.apply(db=db, changeset_id=changeset_id)
    return success_response(data=changeset.model_dump(mode="json"), message="ChangeSet 已应用")


@router.post("/{changeset_id}/rollback")
def rollback_changeset(changeset_id: str, request: RollbackChangeSetRequest, db: Session = Depends(get_db)) -> dict:
    changeset = changeset_service.rollback(db=db, changeset_id=changeset_id, rolled_back_by=request.rolled_back_by, reason=request.reason, workflow_run_id=request.workflow_run_id, trace_id=request.trace_id)
    return success_response(data=changeset.model_dump(mode="json"), message="ChangeSet 已回滚")


@router.get("")
def list_changesets(db: Session = Depends(get_db)) -> dict:
    changesets = [item.model_dump(mode="json") for item in changeset_service.list_changesets(db=db)]
    return success_response(data=changesets)


@router.get("/recovery-events")
def list_changeset_apply_recovery_events(
    project_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    events = [
        item.model_dump(mode="json")
        for item in changeset_service.list_apply_recovery_events(
            db=db,
            project_id=project_id,
            event_type=event_type,
            limit=limit,
        )
    ]
    return success_response(data=events)
