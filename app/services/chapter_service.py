from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.business_logging import StepLogScope, truncate_ids
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.logging_context import set_log_context
from app.db.models import (
    CanonSnapshotORM,
    ChapterBlueprintORM,
    ChapterDraftORM,
    ChapterGoalORM,
    GateReviewORM,
    ImmutableLogORM,
    OpenLoopCardORM,
    ProjectORM,
    PublishedChapterORM,
    PublishRecordORM,
    SceneCardORM,
)
from app.schemas.chapter import (
    ChapterBlueprint,
    ChapterBlueprintStateTransition,
    ChapterDraft,
    ChapterGoal,
    ChapterWorkbenchState,
    ChapterStateTransition,
    CreateChapterGoalRequest,
    DecomposeScenesRequest,
    GenerateBlueprintsRequest,
    GenerateChapterSummaryRequest,
    GenerateDraftRequest,
    ManualEditBlueprintRequest,
    ManualEditDraftRequest,
    ManualEditSceneRequest,
    PublishedChapter,
    PublishRecord,
    ReviseDraftRequest,
    SceneStateTransition,
    SceneCard,
    SelectBlueprintRequest,
)
from app.schemas.continuity import ResolveContinuityPackRequest
from app.schemas.derived_update import DerivedUpdateBatchResult, RunDerivedUpdatesRequest
from app.services.agent_gateway import agent_gateway
from app.services.chapter_state_service import chapter_state_service
from app.services.chapter_summary_service import chapter_summary_service
from app.services.continuity_service import continuity_service
from app.services.derived_update_service import derived_update_service
from app.services.rulepack_service import rulepack_service
from app.services.workflow_run_service import workflow_run_service

logger = get_logger("workflow")



def _to_draft_schema(entity: ChapterDraftORM) -> ChapterDraft:
    metadata = dict(entity.draft_metadata or {})
    return ChapterDraft(
        id=entity.id,
        project_id=entity.project_id,
        blueprint_id=entity.blueprint_id,
        workflow_run_id=entity.workflow_run_id,
        trace_id=entity.trace_id,
        content=entity.content,
        status=entity.status,
        metadata=metadata,
        parent_draft_id=metadata.get("parent_draft_id"),
        revision_no=int(metadata.get("revision_no") or 1),
        revision_reason=metadata.get("revision_reason"),
        source_gate_review_ids=list(metadata.get("source_gate_review_ids") or []),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )



def _to_goal_schema(entity: ChapterGoalORM) -> ChapterGoal:
    return ChapterGoal.model_validate(entity).model_copy(update={"source_type": "workflow", "source_ref": entity.workflow_run_id})



def _to_blueprint_schema(entity: ChapterBlueprintORM) -> ChapterBlueprint:
    return ChapterBlueprint.model_validate(entity).model_copy(update={"source_type": "planner_agent", "source_ref": entity.chapter_goal_id})


def _build_blueprint_metadata(db: Session, blueprint: ChapterBlueprintORM) -> dict:
    rows = (
        db.query(ImmutableLogORM)
        .filter(
            ImmutableLogORM.project_id == blueprint.project_id,
            ImmutableLogORM.event_type == "chapter_blueprint_human_edited",
        )
        .order_by(ImmutableLogORM.created_at.desc())
        .all()
    )
    log_row = next((row for row in rows if (row.event_payload or {}).get("blueprint_id") == blueprint.id), None)
    if log_row is None:
        return {}
    payload = dict(log_row.event_payload or {})
    payload.setdefault("source_type", "human_edited")
    payload.setdefault("edited_at", log_row.created_at.isoformat())
    return payload



def _to_scene_schema(entity: SceneCardORM) -> SceneCard:
    return SceneCard.model_validate(entity).model_copy(update={"source_type": "planner_agent", "source_ref": entity.blueprint_id})


def _build_scene_metadata(db: Session, scene: SceneCardORM) -> dict:
    rows = (
        db.query(ImmutableLogORM)
        .filter(
            ImmutableLogORM.project_id == scene.project_id,
            ImmutableLogORM.event_type == "chapter_scene_human_edited",
        )
        .order_by(ImmutableLogORM.created_at.desc())
        .all()
    )
    log_row = next((row for row in rows if (row.event_payload or {}).get("scene_id") == scene.id), None)
    if log_row is None:
        return {}
    payload = dict(log_row.event_payload or {})
    payload.setdefault("source_type", "human_edited")
    payload.setdefault("edited_at", log_row.created_at.isoformat())
    return payload



def _to_published_chapter_schema(entity: PublishedChapterORM) -> PublishedChapter:
    return PublishedChapter.model_validate(entity).model_copy(update={"source_type": "publish_service", "source_ref": entity.changeset_id})



def _to_publish_record_schema(entity: PublishRecordORM) -> PublishRecord:
    return PublishRecord.model_validate(entity).model_copy(update={"source_type": "publish_service", "source_ref": entity.published_chapter_id})


class ChapterService:
    def get_scene(self, db: Session, project_id: str, scene_id: str) -> SceneCard:
        scene = db.get(SceneCardORM, scene_id)
        if scene is None or scene.project_id != project_id:
            raise NotFoundError("场景卡不存在")
        schema = _to_scene_schema(scene)
        metadata = _build_scene_metadata(db=db, scene=scene)
        return schema.model_copy(update={"extension_fields": {**schema.extension_fields, **metadata}})

    def get_blueprint(self, db: Session, project_id: str, blueprint_id: str) -> ChapterBlueprint:
        blueprint = db.get(ChapterBlueprintORM, blueprint_id)
        if blueprint is None or blueprint.project_id != project_id:
            raise NotFoundError("章节蓝图不存在")
        schema = _to_blueprint_schema(blueprint)
        metadata = _build_blueprint_metadata(db=db, blueprint=blueprint)
        return schema.model_copy(update={"extension_fields": {**schema.extension_fields, **metadata}})

    def get_draft(self, db: Session, project_id: str, draft_id: str) -> ChapterDraft:
        draft = db.get(ChapterDraftORM, draft_id)
        if draft is None or draft.project_id != project_id:
            raise NotFoundError("正文草稿不存在")
        return _to_draft_schema(draft)

    def create_goal(self, db: Session, request: CreateChapterGoalRequest) -> ChapterGoal:
        set_log_context(project_id=request.project_id, chapter_no=request.chapter_no, module="chapter_service", event="create_goal", status="started")
        scope = StepLogScope(
            logger_name="workflow",
            module="chapter_service",
            event="create_goal",
            message_started=f"开始创建第 {request.chapter_no} 章章节目标",
            start_fields={"project_id": request.project_id, "chapter_no": request.chapter_no},
        )
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在，无法创建章目标")
        existing_goal = (
            db.query(ChapterGoalORM)
            .filter(ChapterGoalORM.project_id == request.project_id, ChapterGoalORM.chapter_no == request.chapter_no)
            .first()
        )
        if existing_goal is not None:
            logger.warning(
                f"拒绝重复创建第 {request.chapter_no} 章章节目标",
                extra={
                    "extra_fields": {
                        "chapter_no": request.chapter_no,
                    }
                },
            )
            raise ConflictError(f"当前项目下第 {request.chapter_no} 章目标已存在，请不要重复创建；如需继续，请恢复已有工作流")
        continuity_pack = continuity_service.resolve_pack(
            db=db,
            request=ResolveContinuityPackRequest(
                project_id=request.project_id,
                target_chapter_no=request.chapter_no,
                workflow_run_id=request.workflow_run_id,
                trace_id=request.trace_id,
                previous_chapter_summary=request.previous_chapter_summary,
                unresolved_open_loops=request.unresolved_open_loops,
                recent_limit=3,
            ),
            commit=False,
        )
        genre_context = rulepack_service.resolve_context(db=db, project_id=request.project_id)
        resolved_previous_summary = continuity_pack.previous_chapter_summary
        unresolved_loops = list(continuity_pack.unresolved_open_loops or [])
        if not unresolved_loops:
            unresolved_loops = [
                item.loop_name
                for item in db.query(OpenLoopCardORM)
                .filter(
                    OpenLoopCardORM.project_id == request.project_id,
                    OpenLoopCardORM.is_current_version.is_(True),
                    OpenLoopCardORM.is_canon_bound.is_(True),
                    OpenLoopCardORM.lifecycle_status == "active",
                    OpenLoopCardORM.status.in_(["open", "remind"]),
                )
                .order_by(OpenLoopCardORM.created_at.asc())
                .all()
            ]
        genre_banned_elements = []
        for item in list(genre_context.gate_constraints.banned_terms or []) + list(genre_context.gate_constraints.taboos or []):
            if item not in genre_banned_elements:
                genre_banned_elements.append(item)

        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or continuity_pack.workflow_run_id,
            trace_id=request.trace_id or continuity_pack.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            chapter_no=request.chapter_no,
            source_type="chapter_goal",
            current_step="chapter_goal_input",
            run_metadata={
                "current_volume_goal": request.current_volume_goal,
                "previous_chapter_summary": resolved_previous_summary,
                "unresolved_open_loops": unresolved_loops,
                "next_chapter_seed": continuity_pack.next_chapter_seed,
                "continuity_summary": continuity_pack.continuity_summary,
                "scene_ids": [],
                "source_type": "chapter_goal",
                "source_ref": None,
                "continuity_pack": continuity_pack.model_dump(mode="json"),
                "genre_id": genre_context.genre_id,
                "genre_name": genre_context.genre_name,
                "genre_rulepack_summary": genre_context.rulepack_summary,
            },
        )
        goal = ChapterGoalORM(
            project_id=request.project_id,
            chapter_no=request.chapter_no,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            current_volume_goal=request.current_volume_goal,
            structure_goal="推进主线并为下一章保留钩子",
            conflict_level="medium",
            info_reveal_level="balanced",
            required_elements=unresolved_loops,
            banned_elements=genre_banned_elements[:8],
        )
        db.add(goal)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise ConflictError(f"当前项目下第 {request.chapter_no} 章目标已存在，请不要重复创建；如需继续，请恢复已有工作流")
        project.current_chapter_no = max(project.current_chapter_no, request.chapter_no)
        workflow_run_service.update_progress(db=db, run=run, current_step="chapter_goal_created", source_ref=goal.id)
        db.commit()
        db.refresh(goal)
        scope.success(f"第 {request.chapter_no} 章章节目标创建完成", workflow_run_id=run.id, chapter_goal_id=goal.id, project_id=request.project_id, chapter_no=request.chapter_no)
        return _to_goal_schema(goal)

    def generate_blueprints(self, db: Session, request: GenerateBlueprintsRequest) -> list[ChapterBlueprint]:
        set_log_context(project_id=request.project_id, module="chapter_service", event="generate_blueprints", status="started")
        goal = db.get(ChapterGoalORM, request.chapter_goal_id)
        if goal is None:
            raise NotFoundError("章目标不存在")
        scope = StepLogScope(
            logger_name="workflow",
            module="chapter_service",
            event="generate_blueprints",
            message_started=f"开始生成第 {goal.chapter_no} 章蓝图候选",
            start_fields={"chapter_no": goal.chapter_no, "candidate_count": request.candidate_count},
        )
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or goal.workflow_run_id,
            trace_id=request.trace_id or goal.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            chapter_no=goal.chapter_no,
            source_type="chapter_goal",
            source_ref=goal.id,
            current_step="chapter_blueprint_generation",
        )
        continuity_pack = continuity_service.resolve_pack(
            db=db,
            request=ResolveContinuityPackRequest(
                project_id=request.project_id,
                target_chapter_no=goal.chapter_no,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                previous_chapter_summary=(run.run_metadata or {}).get("previous_chapter_summary") if run is not None else None,
                unresolved_open_loops=list(goal.required_elements or []),
                recent_limit=3,
            ),
            commit=False,
        )
        result = agent_gateway.generate_blueprints(
            db=db,
            context={
                "project_id": request.project_id,
                "genre_name": project.genre_id or "default",
                "candidate_count": request.candidate_count,
                "goal": {
                    "chapter_no": goal.chapter_no,
                    "current_volume_goal": goal.current_volume_goal,
                    "structure_goal": goal.structure_goal,
                    "required_elements": goal.required_elements,
                    "banned_elements": goal.banned_elements,
                },
                "open_loops": continuity_pack.unresolved_open_loops or goal.required_elements,
                "previous_chapter_summary": continuity_pack.previous_chapter_summary,
                "next_chapter_seed": continuity_pack.next_chapter_seed,
                "continuity_summary": continuity_pack.continuity_summary,
                "scene_ids": [],
                "source_type": "chapter_goal",
                "source_ref": goal.id,
                "recent_chapter_summaries": [item.model_dump(mode="json") for item in continuity_pack.recent_chapter_summaries],
                "canon_summary": continuity_pack.canon_summary.model_dump(mode="json") if continuity_pack.canon_summary is not None else None,
                "continuity_pack_json": continuity_pack.model_dump(mode="json"),
            },
            audit_context={
                "project_id": request.project_id,
                "workflow_name": "chapter_cycle_workflow_v1",
                "workflow_run_id": run.id,
                "trace_id": run.trace_id,
                "chapter_goal_id": request.chapter_goal_id,
                "candidate_count": request.candidate_count,
            },
        )
        # 新一轮候选生成前，清空旧的 selected 标记，避免保留历史正式蓝图
        db.query(ChapterBlueprintORM).filter(ChapterBlueprintORM.project_id == request.project_id, ChapterBlueprintORM.chapter_goal_id == request.chapter_goal_id).update({ChapterBlueprintORM.selected: False}, synchronize_session=False)

        blueprints: list[ChapterBlueprint] = []
        for item in result.payload[: request.candidate_count]:
            entity = ChapterBlueprintORM(
                project_id=request.project_id,
                chapter_goal_id=request.chapter_goal_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                title_hint=item["title_hint"],
                summary=item["summary"],
                advances=item["advances"],
                risks=item["risks"],
                selected=False,
            )
            db.add(entity)
            db.flush()
            blueprints.append(_to_blueprint_schema(entity))
        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="blueprint_proposed",
            extra_metadata={"blueprint_count": len(blueprints), "selected_blueprint_id": None, "continuity_pack": continuity_pack.model_dump(mode="json"), "next_chapter_seed": continuity_pack.next_chapter_seed},
        )
        db.add(
            ImmutableLogORM(
                event_type="chapter_blueprints_generated",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "chapter_goal_id": request.chapter_goal_id,
                    "candidate_count": len(blueprints),
                    "blueprint_ids": [item.id for item in blueprints],
                },
            )
        )
        db.commit()
        scope.success(
            f"第 {goal.chapter_no} 章已生成 {len(blueprints)} 个候选蓝图",
            workflow_run_id=run.id,
            chapter_no=goal.chapter_no,
            chapter_goal_id=request.chapter_goal_id,
            candidate_count=len(blueprints),
            candidate_blueprint_ids=truncate_ids([item.id for item in blueprints]),
        )
        return blueprints

    def list_blueprints(self, db: Session, project_id: str, chapter_goal_id: str | None = None, selected_only: bool = False) -> list[ChapterBlueprint]:
        query = db.query(ChapterBlueprintORM).filter(ChapterBlueprintORM.project_id == project_id)
        if chapter_goal_id:
            query = query.filter(ChapterBlueprintORM.chapter_goal_id == chapter_goal_id)
        if selected_only:
            query = query.filter(ChapterBlueprintORM.selected.is_(True))
        items = query.order_by(ChapterBlueprintORM.created_at.asc()).all()
        return [self.get_blueprint(db=db, project_id=project_id, blueprint_id=item.id) for item in items]

    def manual_edit_blueprint(self, db: Session, blueprint_id: str, request: ManualEditBlueprintRequest) -> ChapterBlueprint:
        blueprint = db.get(ChapterBlueprintORM, blueprint_id)
        if blueprint is None or blueprint.project_id != request.project_id:
            raise NotFoundError("章节蓝图不存在")
        if not blueprint.selected:
            raise ConflictError("仅支持对已选定蓝图执行人工编辑")

        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or blueprint.workflow_run_id,
            trace_id=request.trace_id or blueprint.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="blueprint_human_edit",
            source_type="chapter_blueprint",
            source_ref=blueprint.id,
        )

        if request.title_hint is not None:
            blueprint.title_hint = request.title_hint.strip()
        if request.summary is not None:
            blueprint.summary = request.summary.strip()
        if request.advances is not None:
            blueprint.advances = list(request.advances)
        if request.risks is not None:
            blueprint.risks = list(request.risks)
        blueprint.workflow_run_id = run.id
        blueprint.trace_id = run.trace_id

        edited_by = (request.edited_by or "human_editor").strip()
        edited_at = datetime.now(timezone.utc)
        audit_metadata = {
            "edit_reason": request.edit_reason,
            "edited_at": edited_at.isoformat(),
            "source_type": "human_edited",
            "edited_by": edited_by,
            "source_ref": request.source_ref or blueprint.id,
        }
        db.add(
            ImmutableLogORM(
                event_type="chapter_blueprint_human_edited",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "blueprint_id": blueprint.id,
                    "trigger_type": "human_edit",
                    **audit_metadata,
                },
            )
        )
        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="blueprint_human_edited",
            source_ref=blueprint.id,
            status="running",
            extra_metadata={"selected_blueprint_id": blueprint.id, **audit_metadata},
        )
        db.commit()
        db.refresh(blueprint)
        schema = _to_blueprint_schema(blueprint)
        return schema.model_copy(update={"extension_fields": {**schema.extension_fields, **audit_metadata}})

    def get_chapter_workbench_state(self, db: Session, project_id: str, chapter_no: int) -> ChapterWorkbenchState:
        goal = (
            db.query(ChapterGoalORM)
            .filter(ChapterGoalORM.project_id == project_id, ChapterGoalORM.chapter_no == chapter_no)
            .first()
        )
        if goal is None:
            return ChapterWorkbenchState(
                project_id=project_id,
                chapter_no=chapter_no,
                recovery_stage="empty",
                recovery_hint=f"当前第 {chapter_no} 章暂无已创建目标，可先执行“创建目标”",
            )
        blueprints = (
            db.query(ChapterBlueprintORM)
            .filter(ChapterBlueprintORM.project_id == project_id, ChapterBlueprintORM.chapter_goal_id == goal.id)
            .order_by(ChapterBlueprintORM.created_at.asc())
            .all()
        )
        blueprint_schemas = [_to_blueprint_schema(item) for item in blueprints]
        selected_blueprint = next((item for item in blueprints if item.selected), None)
        selected_blueprint_id = selected_blueprint.id if selected_blueprint is not None else None
        scene_ids: list[str] = []
        latest_draft = None
        if selected_blueprint_id:
            scenes = (
                db.query(SceneCardORM)
                .filter(SceneCardORM.project_id == project_id, SceneCardORM.blueprint_id == selected_blueprint_id)
                .order_by(SceneCardORM.created_at.asc())
                .all()
            )
            scene_ids = [item.id for item in scenes]
            latest_draft_entity = (
                db.query(ChapterDraftORM)
                .filter(ChapterDraftORM.project_id == project_id, ChapterDraftORM.blueprint_id == selected_blueprint_id)
                .order_by(ChapterDraftORM.created_at.desc())
                .first()
            )
            if latest_draft_entity is not None:
                latest_draft = _to_draft_schema(latest_draft_entity)
        recovery_stage = "goal"
        recovery_hint = "当前章目标已存在，可继续生成蓝图候选"
        if selected_blueprint_id:
            recovery_stage = "blueprint_selected"
            recovery_hint = "当前章已存在已选蓝图，可继续场景拆解或草稿生成"
        if scene_ids:
            recovery_stage = "scenes_ready"
            recovery_hint = "当前章已存在场景拆解结果，可继续草稿生成"
        if latest_draft is not None:
            recovery_stage = "draft_ready"
            recovery_hint = "当前章已存在草稿，可继续修订或进入 Gate"
        return ChapterWorkbenchState(
            project_id=project_id,
            chapter_no=chapter_no,
            goal_id=goal.id,
            blueprint_candidates=blueprint_schemas,
            selected_blueprint_id=selected_blueprint_id,
            scene_ids=scene_ids,
            latest_draft=latest_draft,
            recovery_stage=recovery_stage,
            recovery_hint=recovery_hint,
        )

    def select_blueprint(self, db: Session, request: SelectBlueprintRequest) -> ChapterBlueprint:
        set_log_context(project_id=request.project_id, module="chapter_service", event="select_blueprint", status="started")
        scope = StepLogScope(
            logger_name="workflow",
            module="chapter_service",
            event="select_blueprint",
            message_started="开始确认章节蓝图",
            start_fields={"project_id": request.project_id, "blueprint_id": request.blueprint_id},
        )
        blueprint = db.get(ChapterBlueprintORM, request.blueprint_id)
        if blueprint is None or blueprint.project_id != request.project_id:
            raise NotFoundError("候选章蓝图不存在")
        if not request.selected_by or not request.selected_by.strip():
            raise ValidationError("selected_by 不能为空")
        goal = db.get(ChapterGoalORM, blueprint.chapter_goal_id)
        if goal is None:
            raise NotFoundError("章目标不存在")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or blueprint.workflow_run_id or goal.workflow_run_id,
            trace_id=request.trace_id or blueprint.trace_id or goal.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            chapter_no=goal.chapter_no,
            source_type="chapter_goal",
            source_ref=goal.id,
            current_step="blueprint_selection",
        )
        currently_selected = (
            db.query(ChapterBlueprintORM)
            .filter(
                ChapterBlueprintORM.project_id == request.project_id,
                ChapterBlueprintORM.chapter_goal_id == blueprint.chapter_goal_id,
                ChapterBlueprintORM.selected.is_(True),
            )
            .first()
        )
        if currently_selected is not None and currently_selected.id != blueprint.id:
            downstream_scene_exists = db.query(SceneCardORM).filter(SceneCardORM.project_id == request.project_id, SceneCardORM.blueprint_id == currently_selected.id).first() is not None
            downstream_draft_exists = db.query(ChapterDraftORM).filter(ChapterDraftORM.project_id == request.project_id, ChapterDraftORM.blueprint_id == currently_selected.id).first() is not None
            if downstream_scene_exists or downstream_draft_exists:
                raise ConflictError("当前已选蓝图已产生场景或草稿，请先走回退/清理流程后再改选蓝图")
        db.query(ChapterBlueprintORM).filter(
            ChapterBlueprintORM.project_id == request.project_id,
            ChapterBlueprintORM.chapter_goal_id == blueprint.chapter_goal_id,
        ).update({ChapterBlueprintORM.selected: False}, synchronize_session=False)
        blueprint.selected = True
        blueprint.workflow_run_id = run.id
        blueprint.trace_id = run.trace_id
        db.flush()
        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="blueprint_selected",
            source_ref=blueprint.id,
            extra_metadata={
                "selected_blueprint_id": blueprint.id,
                "selected_by": request.selected_by.strip(),
                "selection_reason": request.selection_reason,
            },
        )
        db.add(
            ImmutableLogORM(
                event_type="chapter_blueprint_selected",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "chapter_goal_id": blueprint.chapter_goal_id,
                    "blueprint_id": blueprint.id,
                    "selected_by": request.selected_by.strip(),
                    "selection_reason": request.selection_reason,
                },
            )
        )
        db.commit()
        db.refresh(blueprint)
        scope.success(
            f"第 {goal.chapter_no} 章已选定正式蓝图",
            workflow_run_id=run.id,
            chapter_no=goal.chapter_no,
            blueprint_id=blueprint.id,
            selected_blueprint_id=blueprint.id,
        )
        return _to_blueprint_schema(blueprint)

    def decompose_scenes(self, db: Session, request: DecomposeScenesRequest) -> list[SceneCard]:
        set_log_context(project_id=request.project_id, module="chapter_service", event="decompose_scenes", status="started")
        scope = StepLogScope(
            logger_name="workflow",
            module="chapter_service",
            event="decompose_scenes",
            message_started="开始执行场景拆解",
            start_fields={"project_id": request.project_id, "blueprint_id": request.blueprint_id},
        )
        blueprint = db.get(ChapterBlueprintORM, request.blueprint_id)
        if blueprint is None:
            raise NotFoundError("章蓝图不存在")
        if not blueprint.selected:
            raise ConflictError("只能对已选定的正式章蓝图进行场景拆解")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or blueprint.workflow_run_id,
            trace_id=request.trace_id or blueprint.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="scene_decomposition",
            source_type="chapter_blueprint",
            source_ref=blueprint.id,
        )
        result = agent_gateway.decompose_scenes(
            db=db,
            context={
                "project_id": request.project_id,
                "blueprint": {
                    "title_hint": blueprint.title_hint,
                    "summary": blueprint.summary,
                    "advances": blueprint.advances,
                    "risks": blueprint.risks,
                },
            },
            audit_context={
                "project_id": request.project_id,
                "workflow_name": "chapter_cycle_workflow_v1",
                "workflow_run_id": run.id,
                "trace_id": run.trace_id,
                "blueprint_id": request.blueprint_id,
            },
        )
        scene_entities: list[SceneCardORM] = []
        for item in result.payload:
            entity = SceneCardORM(
                project_id=request.project_id,
                blueprint_id=request.blueprint_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                scene_goal=item["scene_goal"],
                participating_entities=item["participating_entities"],
                conflict_type=item["conflict_type"],
                emotional_curve=item["emotional_curve"],
                information_delta=item["information_delta"],
            )
            db.add(entity)
            scene_entities.append(entity)
        workflow_run_service.update_progress(db=db, run=run, current_step="scenes_ready", extra_metadata={"scene_count": len(scene_entities), "selected_blueprint_id": blueprint.id})
        db.commit()
        for entity in scene_entities:
            db.refresh(entity)
        chapter_no = db.get(ChapterGoalORM, blueprint.chapter_goal_id).chapter_no if blueprint.chapter_goal_id else None
        scope.success("场景拆解完成", workflow_run_id=run.id, project_id=request.project_id, blueprint_id=blueprint.id, chapter_no=chapter_no, scene_count=len(scene_entities))
        return [_to_scene_schema(item) for item in scene_entities]

    def manual_edit_scene(self, db: Session, scene_id: str, request: ManualEditSceneRequest) -> SceneCard:
        scene = db.get(SceneCardORM, scene_id)
        if scene is None or scene.project_id != request.project_id:
            raise NotFoundError("场景卡不存在")
        blueprint = db.get(ChapterBlueprintORM, scene.blueprint_id)
        if blueprint is None:
            raise NotFoundError("章节蓝图不存在")
        if not blueprint.selected:
            raise ConflictError("仅支持对已选定蓝图下的场景执行人工编辑")

        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or scene.workflow_run_id or blueprint.workflow_run_id,
            trace_id=request.trace_id or scene.trace_id or blueprint.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="scene_human_edit",
            source_type="scene_card",
            source_ref=scene.id,
        )

        if request.scene_goal is not None:
            scene.scene_goal = request.scene_goal.strip()
        if request.participating_entities is not None:
            scene.participating_entities = list(request.participating_entities)
        if request.conflict_type is not None:
            scene.conflict_type = request.conflict_type.strip()
        if request.emotional_curve is not None:
            scene.emotional_curve = request.emotional_curve.strip()
        if request.information_delta is not None:
            scene.information_delta = request.information_delta.strip()
        scene.workflow_run_id = run.id
        scene.trace_id = run.trace_id

        edited_by = (request.edited_by or "human_editor").strip()
        edited_at = datetime.now(timezone.utc)
        audit_metadata = {
            "edit_reason": request.edit_reason,
            "edited_at": edited_at.isoformat(),
            "source_type": "human_edited",
            "edited_by": edited_by,
            "source_ref": request.source_ref or scene.id,
        }
        db.add(
            ImmutableLogORM(
                event_type="chapter_scene_human_edited",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "scene_id": scene.id,
                    "blueprint_id": scene.blueprint_id,
                    "trigger_type": "human_edit",
                    **audit_metadata,
                },
            )
        )
        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="scene_human_edited",
            source_ref=scene.id,
            status="running",
            extra_metadata={
                "selected_blueprint_id": scene.blueprint_id,
                "last_edited_scene_id": scene.id,
                **audit_metadata,
            },
        )
        db.commit()
        db.refresh(scene)
        schema = _to_scene_schema(scene)
        return schema.model_copy(update={"extension_fields": {**schema.extension_fields, **audit_metadata}})

    def generate_draft(self, db: Session, request: GenerateDraftRequest) -> ChapterDraft:
        set_log_context(project_id=request.project_id, module="chapter_service", event="generate_draft", status="started")
        blueprint = db.get(ChapterBlueprintORM, request.blueprint_id)
        if blueprint is None:
            raise NotFoundError("章蓝图不存在")
        if not blueprint.selected:
            raise ConflictError("只能基于已选定的正式章蓝图生成正文草稿")
        goal = db.get(ChapterGoalORM, blueprint.chapter_goal_id)
        scope = StepLogScope(
            logger_name="workflow",
            module="chapter_service",
            event="generate_draft",
            message_started=f"开始生成第 {goal.chapter_no if goal is not None else '?'} 章正文草稿",
            start_fields={"project_id": request.project_id, "blueprint_id": request.blueprint_id},
        )
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or blueprint.workflow_run_id,
            trace_id=request.trace_id or blueprint.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="draft_generation",
            source_type="chapter_blueprint",
            source_ref=blueprint.id,
        )
        if request.scene_ids:
            scene_entities = [
                item
                for item in db.query(SceneCardORM)
                .filter(SceneCardORM.project_id == request.project_id, SceneCardORM.id.in_(request.scene_ids))
                .order_by(SceneCardORM.created_at.asc())
                .all()
            ]
        else:
            scene_entities = [
                item
                for item in db.query(SceneCardORM)
                .filter(SceneCardORM.project_id == request.project_id, SceneCardORM.blueprint_id == request.blueprint_id)
                .order_by(SceneCardORM.created_at.asc())
                .all()
            ]
        if not scene_entities:
            raise ConflictError("当前章蓝图尚未拆解出 SceneCard，禁止直接生成正文草稿；请先完成场景拆解")
        open_loops = [
            item.loop_name
            for item in db.query(OpenLoopCardORM)
            .filter(
                OpenLoopCardORM.project_id == request.project_id,
                OpenLoopCardORM.is_current_version.is_(True),
                OpenLoopCardORM.is_canon_bound.is_(True),
                OpenLoopCardORM.lifecycle_status == "active",
            )
            .order_by(OpenLoopCardORM.created_at.asc())
            .limit(3)
            .all()
        ]
        latest_snapshot = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == request.project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        continuity_pack = continuity_service.resolve_pack(
            db=db,
            request=ResolveContinuityPackRequest(
                project_id=request.project_id,
                target_chapter_no=goal.chapter_no if goal is not None else (run.chapter_no or 1),
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                recent_limit=3,
            ),
            commit=False,
        )
        result = agent_gateway.generate_draft(
            db=db,
            context={
                "project_id": request.project_id,
                "blueprint": {"title_hint": blueprint.title_hint, "summary": blueprint.summary},
                "scenes": [
                    {
                        "scene_goal": item.scene_goal,
                        "participating_entities": item.participating_entities,
                        "conflict_type": item.conflict_type,
                        "emotional_curve": item.emotional_curve,
                        "information_delta": item.information_delta,
                    }
                    for item in scene_entities
                ],
                "open_loops": continuity_pack.unresolved_open_loops or open_loops,
                "previous_chapter_summary": continuity_pack.previous_chapter_summary,
                "next_chapter_seed": continuity_pack.next_chapter_seed,
                "continuity_summary": continuity_pack.continuity_summary,
                "scene_ids": [item.id for item in scene_entities],
                "source_type": "writer_agent",
                "source_ref": blueprint.id,
                "recent_chapter_summaries": [item.model_dump(mode="json") for item in continuity_pack.recent_chapter_summaries],
                "canon_summary": continuity_pack.canon_summary.model_dump(mode="json") if continuity_pack.canon_summary is not None else {
                    "version_no": getattr(latest_snapshot, "version_no", 0),
                    "character_count": len(getattr(latest_snapshot, "character_cards", []) or []),
                    "rule_count": len(getattr(latest_snapshot, "rule_cards", []) or []),
                    "open_loop_count": len(getattr(latest_snapshot, "open_loops", []) or []),
                },
            },
            audit_context={
                "project_id": request.project_id,
                "workflow_name": "chapter_cycle_workflow_v1",
                "workflow_run_id": run.id,
                "trace_id": run.trace_id,
                "blueprint_id": request.blueprint_id,
                "scene_ids": request.scene_ids,
            },
        )
        payload = result.payload
        metadata = dict(payload.get("metadata") or {})
        metadata.update(
            {
                "configured_provider": result.configured_provider,
                "active_provider": result.active_provider,
                "fallback_used": result.fallback_used,
                "latency_ms": result.latency_ms,
                "call_status": result.call_status,
                "attempt_count": result.attempt_count,
                "error_type": result.error_type,
                "circuit_state_at_call": result.circuit_state_at_call,
                "rate_limited": result.rate_limited,
                "prompt_template_id": result.prompt_template_id,
                "prompt_template_key": result.prompt_template_key,
                "prompt_template_version": result.prompt_template_version,
                "prompt_scope_type": result.prompt_scope_type,
                "prompt_scope_key": result.prompt_scope_key,
                "prompt_provider_scope": result.prompt_provider_scope,
                "workflow_run_id": run.id,
                "trace_id": run.trace_id,
                "next_chapter_seed": continuity_pack.next_chapter_seed,
                "continuity_summary": continuity_pack.continuity_summary,
                "scene_ids": [item.id for item in scene_entities],
                "source_type": "writer_agent",
                "source_ref": blueprint.id,
            }
        )
        draft = ChapterDraftORM(
            project_id=request.project_id,
            blueprint_id=request.blueprint_id,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            content=str(payload.get("content") or ""),
            status="drafting",
            draft_metadata=metadata,
        )
        db.add(draft)
        db.flush()
        chapter_state_service.bootstrap_draft(
            db=db,
            draft=draft,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            metadata={"blueprint_id": blueprint.id, "scene_count": len(scene_entities)},
        )
        workflow_run_service.update_progress(db=db, run=run, current_step="draft_ready", source_ref=draft.id)
        db.commit()
        db.refresh(draft)
        scope.success(
            f"第 {goal.chapter_no if goal is not None else '?'} 章正文草稿生成完成",
            workflow_run_id=run.id,
            blueprint_id=blueprint.id,
            draft_id=draft.id,
            draft_length=len(draft.content or ""),
            provider=result.active_provider,
            model=result.model,
            fallback_used=result.fallback_used,
            latency_ms=result.latency_ms,
        )
        return _to_draft_schema(draft)


    def revise_draft(self, db: Session, request: ReviseDraftRequest) -> ChapterDraft:
        source_draft = db.get(ChapterDraftORM, request.draft_id)
        if source_draft is None or source_draft.project_id != request.project_id:
            raise NotFoundError("正文草稿不存在")
        if source_draft.status == "published":
            raise ConflictError("已发布草稿不允许生成修订版")
        blueprint = db.get(ChapterBlueprintORM, source_draft.blueprint_id)
        if blueprint is None:
            raise NotFoundError("章蓝图不存在")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or source_draft.workflow_run_id,
            trace_id=request.trace_id or source_draft.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            current_step="draft_revision",
            source_type="chapter_draft",
            source_ref=source_draft.id,
        )
        scene_entities = [
            item
            for item in db.query(SceneCardORM)
            .filter(SceneCardORM.project_id == request.project_id, SceneCardORM.blueprint_id == blueprint.id)
            .order_by(SceneCardORM.created_at.asc())
            .all()
        ]
        gate_review_ids = list(request.source_gate_review_ids)
        gate_reviews = []
        if gate_review_ids:
            gate_reviews = [
                item
                for item in db.query(GateReviewORM)
                .filter(GateReviewORM.project_id == request.project_id, GateReviewORM.id.in_(gate_review_ids))
                .order_by(GateReviewORM.created_at.asc())
                .all()
            ]
        if not gate_reviews:
            gate_reviews = [
                item
                for item in db.query(GateReviewORM)
                .filter(GateReviewORM.project_id == request.project_id, GateReviewORM.draft_id == source_draft.id)
                .order_by(GateReviewORM.created_at.desc())
                .limit(8)
                .all()
            ]
        latest_snapshot = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == request.project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        source_metadata = dict(source_draft.draft_metadata or {})
        revision_no = int(source_metadata.get("revision_no") or 1) + 1
        revision_instruction = (request.revision_instruction or "根据失败 Gate 结果修订正文，使其重新满足叙事、结构与发布前置要求").strip()
        gate_issue_payload = []
        for review in gate_reviews:
            for issue in list(review.issues or []):
                gate_issue_payload.append({
                    "gate_name": review.gate_name,
                    "pass_status": review.pass_status,
                    "severity": issue.get("severity", "S1"),
                    "message": issue.get("message"),
                    "summary": issue.get("summary"),
                    "suggestion": issue.get("suggestion"),
                })
        revision_task = {
            "task_type": "draft_revision",
            "source_draft_id": source_draft.id,
            "blueprint_id": blueprint.id,
            "revision_no": revision_no,
            "source_gate_review_ids": [review.id for review in gate_reviews],
            "revision_instruction": revision_instruction,
        }
        db.add(
            ImmutableLogORM(
                event_type="chapter_revision_task_created",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload=revision_task,
            )
        )
        result = agent_gateway.revise_draft(
            db=db,
            context={
                "project_id": request.project_id,
                "draft_id": source_draft.id,
                "blueprint": {"title_hint": blueprint.title_hint, "summary": blueprint.summary},
                "scenes": [
                    {
                        "scene_goal": item.scene_goal,
                        "participating_entities": item.participating_entities,
                        "conflict_type": item.conflict_type,
                        "emotional_curve": item.emotional_curve,
                        "information_delta": item.information_delta,
                    }
                    for item in scene_entities
                ],
                "content": source_draft.content,
                "gate_issues": gate_issue_payload,
                "revision_instruction": revision_instruction,
                "canon_summary": {
                    "version_no": getattr(latest_snapshot, "version_no", 0),
                    "character_count": len(getattr(latest_snapshot, "character_cards", []) or []),
                    "rule_count": len(getattr(latest_snapshot, "rule_cards", []) or []),
                    "open_loop_count": len(getattr(latest_snapshot, "open_loops", []) or []),
                },
            },
            audit_context={
                "project_id": request.project_id,
                "workflow_name": "chapter_cycle_workflow_v1",
                "workflow_run_id": run.id,
                "trace_id": run.trace_id,
                "draft_id": source_draft.id,
                "blueprint_id": blueprint.id,
            },
        )
        metadata = dict(result.payload.get("metadata") or {})
        metadata.update(
            {
                "configured_provider": result.configured_provider,
                "active_provider": result.active_provider,
                "fallback_used": result.fallback_used,
                "latency_ms": result.latency_ms,
                "call_status": result.call_status,
                "attempt_count": result.attempt_count,
                "error_type": result.error_type,
                "circuit_state_at_call": result.circuit_state_at_call,
                "rate_limited": result.rate_limited,
                "prompt_template_id": result.prompt_template_id,
                "prompt_template_key": result.prompt_template_key,
                "prompt_template_version": result.prompt_template_version,
                "prompt_scope_type": result.prompt_scope_type,
                "prompt_scope_key": result.prompt_scope_key,
                "prompt_provider_scope": result.prompt_provider_scope,
                "workflow_run_id": run.id,
                "trace_id": run.trace_id,
                "parent_draft_id": source_draft.id,
                "revision_no": revision_no,
                "revision_reason": revision_instruction,
                "source_gate_review_ids": [review.id for review in gate_reviews],
                "revised_by": request.revised_by or "system",
                "scene_ids": [item.id for item in scene_entities],
                "source_type": "revision_loop",
                "source_ref": source_draft.id,
            }
        )
        revised_draft = ChapterDraftORM(
            project_id=request.project_id,
            blueprint_id=blueprint.id,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            content=str(result.payload.get("content") or source_draft.content),
            status="drafting",
            draft_metadata=metadata,
        )
        db.add(revised_draft)
        db.flush()
        chapter_state_service.bootstrap_draft(
            db=db,
            draft=revised_draft,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            reason="基于 Gate 失败结果创建修订版草稿",
            metadata={
                "parent_draft_id": source_draft.id,
                "revision_no": revision_no,
                "source_gate_review_ids": [review.id for review in gate_reviews],
            },
        )
        db.add(
            ImmutableLogORM(
                event_type="chapter_draft_revised",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "source_draft_id": source_draft.id,
                    "revised_draft_id": revised_draft.id,
                    "revision_no": revision_no,
                    "source_gate_review_ids": [review.id for review in gate_reviews],
                    "revision_instruction": revision_instruction,
                },
            )
        )
        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="draft_revised",
            source_ref=revised_draft.id,
            status="running",
            extra_metadata={
                "source_draft_id": source_draft.id,
                "revised_draft_id": revised_draft.id,
                "revision_no": revision_no,
            },
        )
        db.commit()
        db.refresh(revised_draft)
        return _to_draft_schema(revised_draft)

    def manual_edit_draft(self, db: Session, draft_id: str, request: ManualEditDraftRequest) -> ChapterDraft:
        draft = db.get(ChapterDraftORM, draft_id)
        if draft is None or draft.project_id != request.project_id:
            raise NotFoundError("正文草稿不存在")
        if draft.status == "published":
            raise ConflictError("已发布草稿不允许人工编辑")

        draft.content = request.content
        metadata = dict(draft.draft_metadata or {})
        metadata.update(
            {
                "edit_reason": request.edit_reason,
                "edited_at": datetime.now(timezone.utc).isoformat(),
                "source_type": "human_edited",
                "edited_by": request.edited_by or "human_editor",
                "source_ref": request.source_ref or draft.id,
            }
        )
        draft.draft_metadata = metadata
        db.flush()

        chapter_state_service.transition(
            db=db,
            draft=draft,
            to_status=draft.status,
            trigger_type="human_edit",
            trigger_ref=request.edited_by or "human_editor",
            workflow_run_id=request.workflow_run_id or draft.workflow_run_id,
            trace_id=request.trace_id or draft.trace_id,
            reason=request.edit_reason,
            metadata={"source_type": "human_edited", "edited_by": request.edited_by or "human_editor"},
        )
        db.commit()
        db.refresh(draft)
        return _to_draft_schema(draft)

    def list_published_chapters(self, db: Session, project_id: str | None = None) -> list[PublishedChapter]:
        query = db.query(PublishedChapterORM)
        if project_id:
            query = query.filter(PublishedChapterORM.project_id == project_id)
        items = query.order_by(PublishedChapterORM.chapter_no.asc(), PublishedChapterORM.published_at.asc()).all()
        return [_to_published_chapter_schema(item) for item in items]

    def list_publish_records(self, db: Session, project_id: str | None = None) -> list[PublishRecord]:
        query = db.query(PublishRecordORM)
        if project_id:
            query = query.filter(PublishRecordORM.project_id == project_id)
        items = query.order_by(PublishRecordORM.created_at.desc()).all()
        return [_to_publish_record_schema(item) for item in items]

    def generate_published_chapter_summary(self, db: Session, request: GenerateChapterSummaryRequest):
        return chapter_summary_service.generate_for_published(db=db, request=request, commit=True)

    def get_published_chapter_summary(self, db: Session, project_id: str, published_chapter_id: str, force_regenerate: bool = False):
        return chapter_summary_service.get_published_summary(db=db, project_id=project_id, published_chapter_id=published_chapter_id, force_regenerate=force_regenerate)

    def get_latest_project_summary(self, db: Session, project_id: str, before_chapter_no: int | None = None):
        return chapter_summary_service.get_latest_project_summary(db=db, project_id=project_id, before_chapter_no=before_chapter_no)

    def get_continuity_pack(self, db: Session, project_id: str, target_chapter_no: int, workflow_run_id: str | None = None, trace_id: str | None = None, force_refresh: bool = False):
        return continuity_service.resolve_pack(
            db=db,
            request=ResolveContinuityPackRequest(
                project_id=project_id,
                target_chapter_no=target_chapter_no,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                force_refresh=force_refresh,
            ),
            commit=True,
        )

    def list_state_history(self, db: Session, draft_id: str, project_id: str | None = None) -> list[ChapterStateTransition]:
        return chapter_state_service.list_history(db=db, draft_id=draft_id, project_id=project_id)

    def list_blueprint_state_history(self, db: Session, blueprint_id: str, project_id: str | None = None) -> list[ChapterBlueprintStateTransition]:
        blueprint = db.get(ChapterBlueprintORM, blueprint_id)
        if blueprint is None:
            raise NotFoundError("章节蓝图不存在")
        if project_id and blueprint.project_id != project_id:
            raise NotFoundError("章节蓝图不存在")
        logs = (
            db.query(ImmutableLogORM)
            .filter(
                ImmutableLogORM.project_id == blueprint.project_id,
                ImmutableLogORM.event_type == "chapter_blueprint_human_edited",
            )
            .order_by(ImmutableLogORM.created_at.asc())
            .all()
        )
        rows = [row for row in logs if (row.event_payload or {}).get("blueprint_id") == blueprint_id]
        return [
            ChapterBlueprintStateTransition(
                id=str(row.id),
                project_id=blueprint.project_id,
                blueprint_id=blueprint_id,
                workflow_run_id=row.workflow_run_id,
                trace_id=row.trace_id,
                trigger_type=str((row.event_payload or {}).get("trigger_type") or "human_edit"),
                trigger_ref=(row.event_payload or {}).get("edited_by"),
                reason=(row.event_payload or {}).get("edit_reason"),
                transition_metadata=dict(row.event_payload or {}),
                created_at=row.created_at,
                updated_at=row.created_at,
            )
            for row in rows
        ]

    def list_scene_state_history(self, db: Session, scene_id: str, project_id: str | None = None) -> list[SceneStateTransition]:
        scene = db.get(SceneCardORM, scene_id)
        if scene is None:
            raise NotFoundError("场景卡不存在")
        if project_id and scene.project_id != project_id:
            raise NotFoundError("场景卡不存在")
        logs = (
            db.query(ImmutableLogORM)
            .filter(
                ImmutableLogORM.project_id == scene.project_id,
                ImmutableLogORM.event_type == "chapter_scene_human_edited",
            )
            .order_by(ImmutableLogORM.created_at.asc())
            .all()
        )
        rows = [row for row in logs if (row.event_payload or {}).get("scene_id") == scene_id]
        return [
            SceneStateTransition(
                id=str(row.id),
                project_id=scene.project_id,
                scene_id=scene_id,
                workflow_run_id=row.workflow_run_id,
                trace_id=row.trace_id,
                trigger_type=str((row.event_payload or {}).get("trigger_type") or "human_edit"),
                trigger_ref=(row.event_payload or {}).get("edited_by"),
                reason=(row.event_payload or {}).get("edit_reason"),
                transition_metadata=dict(row.event_payload or {}),
                created_at=row.created_at,
                updated_at=row.created_at,
            )
            for row in rows
        ]

    def run_post_publish_updates(self, db: Session, request: RunDerivedUpdatesRequest) -> DerivedUpdateBatchResult:
        return derived_update_service.run_post_publish_updates(db=db, request=request, commit=True)

    def get_post_publish_updates(self, db: Session, project_id: str, published_chapter_id: str) -> DerivedUpdateBatchResult | None:
        return derived_update_service.get_post_publish_updates(db=db, project_id=project_id, published_chapter_id=published_chapter_id)


chapter_service = ChapterService()
