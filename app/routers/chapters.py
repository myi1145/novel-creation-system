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
    ManualEditBlueprintRequest,
    ManualEditDraftRequest,
    ManualEditSceneRequest,
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
    return success_response(data=goal.model_dump(mode="json"), message="章节目标已创建")


@router.get("/workbench-state")
def get_workbench_state(project_id: str, chapter_no: int, db: Session = Depends(get_db)) -> dict:
    state = chapter_service.get_chapter_workbench_state(db=db, project_id=project_id, chapter_no=chapter_no)
    return success_response(data=state.model_dump(mode="json"), message="章节工作台恢复状态获取成功")


@router.post("/blueprints/generate")
def generate_blueprints(request: GenerateBlueprintsRequest, db: Session = Depends(get_db)) -> dict:
    blueprints = [item.model_dump(mode="json") for item in chapter_service.generate_blueprints(db=db, request=request)]
    return success_response(data=blueprints, message="章节蓝图候选已生成")


@router.get("/blueprints")
def list_blueprints(project_id: str, chapter_goal_id: str | None = Query(default=None), selected_only: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_blueprints(db=db, project_id=project_id, chapter_goal_id=chapter_goal_id, selected_only=selected_only)]
    return success_response(data=items, message="章节蓝图列表获取成功")


@router.get("/blueprints/{blueprint_id}")
def get_blueprint(blueprint_id: str, project_id: str, db: Session = Depends(get_db)) -> dict:
    blueprint = chapter_service.get_blueprint(db=db, project_id=project_id, blueprint_id=blueprint_id)
    return success_response(data=blueprint.model_dump(mode="json"), message="章节蓝图获取成功")


@router.patch("/blueprints/{blueprint_id}")
def manual_edit_blueprint(blueprint_id: str, request: ManualEditBlueprintRequest, db: Session = Depends(get_db)) -> dict:
    blueprint = chapter_service.manual_edit_blueprint(db=db, blueprint_id=blueprint_id, request=request)
    return success_response(data=blueprint.model_dump(mode="json"), message="章节蓝图已人工编辑")


@router.get("/blueprints/{blueprint_id}/state-history")
def get_blueprint_state_history(blueprint_id: str, project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_blueprint_state_history(db=db, blueprint_id=blueprint_id, project_id=project_id)]
    return success_response(data=items, message="蓝图状态流转历史获取成功")


@router.post("/blueprints/select")
def select_blueprint(request: SelectBlueprintRequest, db: Session = Depends(get_db)) -> dict:
    blueprint = chapter_service.select_blueprint(db=db, request=request)
    return success_response(data=blueprint.model_dump(mode="json"), message="章节蓝图已确认")


@router.post("/scenes/decompose")
def decompose_scenes(request: DecomposeScenesRequest, db: Session = Depends(get_db)) -> dict:
    scenes = [item.model_dump(mode="json") for item in chapter_service.decompose_scenes(db=db, request=request)]
    return success_response(data=scenes, message="场景卡已生成")


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: str, project_id: str, db: Session = Depends(get_db)) -> dict:
    scene = chapter_service.get_scene(db=db, project_id=project_id, scene_id=scene_id)
    return success_response(data=scene.model_dump(mode="json"), message="场景卡获取成功")


@router.patch("/scenes/{scene_id}")
def manual_edit_scene(scene_id: str, request: ManualEditSceneRequest, db: Session = Depends(get_db)) -> dict:
    scene = chapter_service.manual_edit_scene(db=db, scene_id=scene_id, request=request)
    return success_response(data=scene.model_dump(mode="json"), message="场景卡已人工编辑")


@router.get("/scenes/{scene_id}/state-history")
def get_scene_state_history(scene_id: str, project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_scene_state_history(db=db, scene_id=scene_id, project_id=project_id)]
    return success_response(data=items, message="场景状态流转历史获取成功")


@router.post("/drafts/generate")
def generate_draft(request: GenerateDraftRequest, db: Session = Depends(get_db)) -> dict:
    draft = chapter_service.generate_draft(db=db, request=request)
    return success_response(data=draft.model_dump(mode="json"), message="章节草稿已生成")


@router.post("/drafts/revise")
def revise_draft(request: ReviseDraftRequest, db: Session = Depends(get_db)) -> dict:
    draft = chapter_service.revise_draft(db=db, request=request)
    return success_response(data=draft.model_dump(mode="json"), message="章节草稿已修订")


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, project_id: str, db: Session = Depends(get_db)) -> dict:
    draft = chapter_service.get_draft(db=db, project_id=project_id, draft_id=draft_id)
    return success_response(data=draft.model_dump(mode="json"), message="章节草稿获取成功")


@router.post("/drafts/{draft_id}/manual-edit")
def manual_edit_draft(draft_id: str, request: ManualEditDraftRequest, db: Session = Depends(get_db)) -> dict:
    draft = chapter_service.manual_edit_draft(db=db, draft_id=draft_id, request=request)
    return success_response(data=draft.model_dump(mode="json"), message="章节草稿已人工编辑")


@router.post("/drafts/publish")
def publish_draft(request: PublishDraftRequest, db: Session = Depends(get_db)) -> dict:
    result = publish_service.publish_draft(db=db, request=request)
    return success_response(data=result.model_dump(mode="json"), message="章节草稿已发布")


@router.get("/published")
def list_published(project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_published_chapters(db=db, project_id=project_id)]
    return success_response(data=items, message="已发布章节列表获取成功")


@router.get("/publish-records")
def list_publish_records(project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_publish_records(db=db, project_id=project_id)]
    return success_response(data=items, message="发布记录获取成功")


@router.get("/drafts/{draft_id}/state-history")
def get_draft_state_history(draft_id: str, project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in chapter_service.list_state_history(db=db, draft_id=draft_id, project_id=project_id)]
    return success_response(data=items, message="草稿状态流转历史获取成功")


@router.post("/drafts/{draft_id}/changeset-proposals/generate")
def generate_changeset_proposal(draft_id: str, request: GenerateChangeSetProposalRequest, db: Session = Depends(get_db)) -> dict:
    payload = request.model_copy(update={"draft_id": draft_id})
    proposal = changeset_service.generate_proposal(db=db, request=payload)
    return success_response(data=proposal.model_dump(mode="json"), message="ChangeSet 提议已生成")

@router.post("/published/{published_chapter_id}/summary/generate")
def generate_published_chapter_summary(published_chapter_id: str, request: GenerateChapterSummaryRequest, db: Session = Depends(get_db)) -> dict:
    payload = request.model_copy(update={"published_chapter_id": published_chapter_id})
    summary = chapter_service.generate_published_chapter_summary(db=db, request=payload)
    return success_response(data=summary.model_dump(mode="json"), message="章节摘要已生成")


@router.get("/published/{published_chapter_id}/summary")
def get_published_chapter_summary(published_chapter_id: str, project_id: str, force_regenerate: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    summary = chapter_service.get_published_chapter_summary(db=db, project_id=project_id, published_chapter_id=published_chapter_id, force_regenerate=force_regenerate)
    return success_response(data=summary.model_dump(mode="json"), message="章节摘要获取成功")


@router.get("/projects/{project_id}/latest-summary")
def get_latest_project_summary(project_id: str, before_chapter_no: int | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    summary = chapter_service.get_latest_project_summary(db=db, project_id=project_id, before_chapter_no=before_chapter_no)
    return success_response(data=summary.model_dump(mode="json") if summary else None, message="最新章节摘要获取成功")

@router.get("/projects/{project_id}/continuity-pack")
def get_project_continuity_pack(project_id: str, target_chapter_no: int, workflow_run_id: str | None = Query(default=None), trace_id: str | None = Query(default=None), force_refresh: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    pack = chapter_service.get_continuity_pack(db=db, project_id=project_id, target_chapter_no=target_chapter_no, workflow_run_id=workflow_run_id, trace_id=trace_id, force_refresh=force_refresh)
    return success_response(data=pack.model_dump(mode="json"), message="连续性上下文包获取成功")

@router.post("/published/{published_chapter_id}/derived-updates/run")
def run_post_publish_updates(published_chapter_id: str, request: RunDerivedUpdatesRequest, db: Session = Depends(get_db)) -> dict:
    payload = request.model_copy(update={"published_chapter_id": published_chapter_id})
    result = chapter_service.run_post_publish_updates(db=db, request=payload)
    return success_response(data=result.model_dump(mode="json"), message="发布后派生更新任务已执行")


@router.get("/published/{published_chapter_id}/derived-updates")
def get_post_publish_updates(published_chapter_id: str, project_id: str, db: Session = Depends(get_db)) -> dict:
    result = chapter_service.get_post_publish_updates(db=db, project_id=project_id, published_chapter_id=published_chapter_id)
    return success_response(data=result.model_dump(mode="json") if result else None, message="发布后派生更新结果获取成功")
