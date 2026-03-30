from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.changeset import GenerateChangeSetProposalRequest
from app.schemas.continuity import ResolveContinuityPackRequest
from app.schemas.chapter import (
    CreateChapterGoalRequest,
    DecomposeScenesRequest,
    GenerateBlueprintsRequest,
    GenerateChapterSummaryRequest,
    GenerateDraftRequest,
    PublishDraftRequest,
    ReviseDraftRequest,
    SelectBlueprintRequest,
)
from app.schemas.derived_update import RunDerivedUpdatesRequest
from app.services.chapter_service import chapter_service
from app.services.changeset_service import changeset_service
from app.services.publish_service import publish_service
from app.utils.response import success_response

router = APIRouter()


@router.post("/goals")
def create_goal(request: CreateChapterGoalRequest, db: Session = Depends(get_db)) -> dict:
    goal = chapter_service.create_goal(db=db, request=request)
    return success_response(data=goal.model_dump(mode="json"), message="chapter goal created")


@router.post("/blueprints/generate")
def generate_blueprints(request: GenerateBlueprintsRequest, db: Session = Depends(get_db)) -> dict:
    blueprints = [item.model_dump(mode="json") for item in chapter_service.generate_blueprints(db=db, request=request)]
    return success_response(data=blueprints, message="chapter blueprints generated")


@router.get("/blueprints")
def list_blueprints(project_id: str, chapter_goal_id: str | None = Query(default=None), selected_only: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_blueprints(db=db, project_id=project_id, chapter_goal_id=chapter_goal_id, selected_only=selected_only)]
    return success_response(data=items, message="chapter blueprints fetched")


@router.post("/blueprints/select")
def select_blueprint(request: SelectBlueprintRequest, db: Session = Depends(get_db)) -> dict:
    blueprint = chapter_service.select_blueprint(db=db, request=request)
    return success_response(data=blueprint.model_dump(mode="json"), message="chapter blueprint selected")


@router.post("/scenes/decompose")
def decompose_scenes(request: DecomposeScenesRequest, db: Session = Depends(get_db)) -> dict:
    scenes = [item.model_dump(mode="json") for item in chapter_service.decompose_scenes(db=db, request=request)]
    return success_response(data=scenes, message="scene cards generated")


@router.post("/drafts/generate")
def generate_draft(request: GenerateDraftRequest, db: Session = Depends(get_db)) -> dict:
    draft = chapter_service.generate_draft(db=db, request=request)
    return success_response(data=draft.model_dump(mode="json"), message="chapter draft generated")


@router.post("/drafts/revise")
def revise_draft(request: ReviseDraftRequest, db: Session = Depends(get_db)) -> dict:
    draft = chapter_service.revise_draft(db=db, request=request)
    return success_response(data=draft.model_dump(mode="json"), message="chapter draft revised")


@router.post("/drafts/publish")
def publish_draft(request: PublishDraftRequest, db: Session = Depends(get_db)) -> dict:
    result = publish_service.publish_draft(db=db, request=request)
    return success_response(data=result.model_dump(mode="json"), message="chapter draft published")


@router.get("/published")
def list_published(project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_published_chapters(db=db, project_id=project_id)]
    return success_response(data=items, message="published chapters fetched")


@router.get("/publish-records")
def list_publish_records(project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_publish_records(db=db, project_id=project_id)]
    return success_response(data=items, message="publish records fetched")


@router.get("/drafts/{draft_id}/state-history")
def get_draft_state_history(draft_id: str, project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_state_history(db=db, draft_id=draft_id, project_id=project_id)]
    return success_response(data=items, message="draft state history fetched")


@router.post("/drafts/{draft_id}/changeset-proposals/generate")
def generate_changeset_proposal(draft_id: str, request: GenerateChangeSetProposalRequest, db: Session = Depends(get_db)) -> dict:
    payload = request.model_copy(update={"draft_id": draft_id})
    proposal = changeset_service.generate_proposal(db=db, request=payload)
    return success_response(data=proposal.model_dump(mode="json"), message="changeset proposal generated")

@router.post("/published/{published_chapter_id}/summary/generate")
def generate_published_chapter_summary(published_chapter_id: str, request: GenerateChapterSummaryRequest, db: Session = Depends(get_db)) -> dict:
    payload = request.model_copy(update={"published_chapter_id": published_chapter_id})
    summary = chapter_service.generate_published_chapter_summary(db=db, request=payload)
    return success_response(data=summary.model_dump(mode="json"), message="chapter summary generated")


@router.get("/published/{published_chapter_id}/summary")
def get_published_chapter_summary(published_chapter_id: str, project_id: str, force_regenerate: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    summary = chapter_service.get_published_chapter_summary(db=db, project_id=project_id, published_chapter_id=published_chapter_id, force_regenerate=force_regenerate)
    return success_response(data=summary.model_dump(mode="json"), message="chapter summary fetched")


@router.get("/projects/{project_id}/latest-summary")
def get_latest_project_summary(project_id: str, before_chapter_no: int | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    summary = chapter_service.get_latest_project_summary(db=db, project_id=project_id, before_chapter_no=before_chapter_no)
    return success_response(data=summary.model_dump(mode="json") if summary else None, message="latest chapter summary fetched")

@router.get("/projects/{project_id}/continuity-pack")
def get_project_continuity_pack(project_id: str, target_chapter_no: int, workflow_run_id: str | None = Query(default=None), trace_id: str | None = Query(default=None), force_refresh: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    pack = chapter_service.get_continuity_pack(db=db, project_id=project_id, target_chapter_no=target_chapter_no, workflow_run_id=workflow_run_id, trace_id=trace_id, force_refresh=force_refresh)
    return success_response(data=pack.model_dump(mode="json"), message="continuity pack fetched")

@router.post("/published/{published_chapter_id}/derived-updates/run")
def run_post_publish_updates(published_chapter_id: str, request: RunDerivedUpdatesRequest, db: Session = Depends(get_db)) -> dict:
    payload = request.model_copy(update={"published_chapter_id": published_chapter_id})
    result = chapter_service.run_post_publish_updates(db=db, request=payload)
    return success_response(data=result.model_dump(mode="json"), message="post publish derived updates executed")


@router.get("/published/{published_chapter_id}/derived-updates")
def get_post_publish_updates(published_chapter_id: str, project_id: str, db: Session = Depends(get_db)) -> dict:
    result = chapter_service.get_post_publish_updates(db=db, project_id=project_id, published_chapter_id=published_chapter_id)
    return success_response(data=result.model_dump(mode="json") if result else None, message="post publish derived updates fetched")

