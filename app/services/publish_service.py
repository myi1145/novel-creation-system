from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.business_logging import StepLogScope
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.logging_context import set_log_context
from app.db.models import (
    ChapterBlueprintORM,
    ChapterDraftORM,
    ChapterGoalORM,
    ChangeSetORM,
    ImmutableLogORM,
    ProjectORM,
    PublishedChapterORM,
    PublishRecordORM,
)
from app.domain.enums import ChapterStatus, ChangeSetStatus, GateName
from app.schemas.chapter import GenerateChapterSummaryRequest, PublishDraftRequest, PublishResult, PublishedChapter, PublishRecord
from app.schemas.derived_update import RunDerivedUpdatesRequest
from app.services.chapter_state_service import chapter_state_service
from app.services.chapter_summary_service import chapter_summary_service
from app.services.derived_update_service import derived_update_service
from app.services.gate_service import gate_service
from app.services.quality_delta_service import QualityDeltaContext, quality_delta_service
from app.services.workflow_run_service import workflow_run_service

logger = get_logger("workflow")

class PublishService:
    REQUIRED_PUBLISH_GATES = [GateName.SCHEMA.value, GateName.CANON.value, GateName.NARRATIVE.value, GateName.PUBLISH.value]

    def publish_draft(self, db: Session, request: PublishDraftRequest) -> PublishResult:
        set_log_context(project_id=request.project_id, workflow_run_id=request.workflow_run_id, module="publish_service", event="publish", status="started")
        scope = StepLogScope(
            logger_name="workflow",
            module="publish_service",
            event="publish",
            message_started="开始发布章节",
            start_fields={"project_id": request.project_id, "draft_id": request.draft_id, "workflow_run_id": request.workflow_run_id},
        )
        draft = db.get(ChapterDraftORM, request.draft_id)
        if draft is None or draft.project_id != request.project_id:
            raise NotFoundError("正文草稿不存在")
        if draft.status == ChapterStatus.PUBLISHED.value:
            existing_published = db.query(PublishedChapterORM).filter(PublishedChapterORM.project_id == request.project_id, PublishedChapterORM.draft_id == draft.id).first()
            if existing_published is None:
                raise ConflictError("草稿状态为 published，但未找到对应已发布章节，请联系管理员排查数据一致性")
            existing_record = (
                db.query(PublishRecordORM)
                .filter(
                    PublishRecordORM.project_id == request.project_id,
                    PublishRecordORM.draft_id == draft.id,
                    PublishRecordORM.published_chapter_id == existing_published.id,
                )
                .order_by(PublishRecordORM.created_at.desc())
                .first()
            )
            if existing_record is None:
                raise ConflictError("草稿状态为 published，但未找到对应发布记录，请联系管理员排查数据一致性")
            chapter_summary = chapter_summary_service.get_published_summary(
                db=db,
                project_id=request.project_id,
                published_chapter_id=existing_published.id,
                force_regenerate=False,
            )
            derived_update_result = derived_update_service.get_post_publish_updates(
                db=db,
                project_id=request.project_id,
                published_chapter_id=existing_published.id,
            )
            scope.success(f"草稿已发布，返回既有发布结果（幂等命中）")
            existing_delta_payload = dict(existing_published.publish_metadata or {}).get("quality_delta_report")
            existing_seed_payload = dict(existing_published.publish_metadata or {}).get("seed_consumption_report")
            from app.schemas.chapter import SeedConsumptionReport

            return PublishResult(
                success=True,
                publish_status="published",
                idempotent_hit=True,
                published_chapter=PublishedChapter.model_validate(existing_published),
                publish_record=PublishRecord.model_validate(existing_record),
                delta_report=(None if not existing_delta_payload else existing_delta_payload),
                seed_consumption_report=(None if not existing_seed_payload else SeedConsumptionReport.model_validate(existing_seed_payload)),
                chapter_summary=chapter_summary,
                derived_update_result=derived_update_result,
            )
        if draft.status not in {ChapterStatus.CANON_APPLIED.value, ChapterStatus.PUBLISH_FAILED.value}:
            raise ConflictError(f"当前草稿状态为 {draft.status}，不允许进入发布阶段")
        if not request.published_by or not request.published_by.strip():
            raise ValidationError("published_by 不能为空")
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在")
        blueprint = db.get(ChapterBlueprintORM, draft.blueprint_id)
        if blueprint is None:
            raise ConflictError("草稿缺少对应蓝图")
        goal = db.get(ChapterGoalORM, blueprint.chapter_goal_id)
        if goal is None:
            raise ConflictError("草稿缺少对应章目标")
        changeset = (
            db.query(ChangeSetORM)
            .filter(
                ChangeSetORM.project_id == request.project_id,
                ChangeSetORM.source_ref == draft.id,
                ChangeSetORM.status == ChangeSetStatus.APPLIED.value,
            )
            .order_by(ChangeSetORM.applied_at.desc())
            .first()
        )
        if changeset is None or not changeset.result_snapshot_id:
            raise ConflictError("发布前必须存在已 applied 的 ChangeSet，并绑定 result_snapshot_id")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or draft.workflow_run_id or goal.workflow_run_id,
            trace_id=request.trace_id or draft.trace_id or goal.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            chapter_no=goal.chapter_no,
            source_type="chapter_publish",
            source_ref=draft.id,
            current_step="publish_pending",
        )
        chapter_state_service.transition(
            db=db,
            draft=draft,
            to_status=ChapterStatus.PUBLISH_PENDING.value,
            trigger_type="publish_started",
            trigger_ref=draft.id,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            reason="进入发布阶段",
            metadata={"changeset_id": changeset.id, "snapshot_id": changeset.result_snapshot_id},
        )
        try:
            publish_gate_review = gate_service.run_single_gate(
                db=db,
                project_id=request.project_id,
                draft_id=draft.id,
                gate_name=GateName.PUBLISH.value,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
            )
            if publish_gate_review.pass_status == "failed":
                chapter_state_service.transition(
                    db=db,
                    draft=draft,
                    to_status=ChapterStatus.PUBLISH_FAILED.value,
                    trigger_type="publish_gate_failed",
                    trigger_ref=publish_gate_review.id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                    reason="发布 Gate 未通过",
                    metadata={
                        "highest_severity": publish_gate_review.highest_severity,
                        "rollback_recommended": True,
                        "rollback_changeset_id": changeset.id,
                    },
                )
                workflow_run_service.mark_attention(
                    db=db,
                    run=run,
                    current_step="publish_gate_failed",
                    reason="发布 Gate 未通过",
                    extra_metadata={
                        "rollback_recommended": True,
                        "rollback_changeset_id": changeset.id,
                        "publish_gate_review_id": publish_gate_review.id,
                    },
                )
                db.commit()
                raise ConflictError("publish_gate 未通过，草稿不能发布")
            self._ensure_required_gates(db=db, project_id=request.project_id, draft_id=draft.id)
            latest_reviews = self._list_latest_gate_reviews(db=db, project_id=request.project_id, draft_id=draft.id)
            unresolved_critical_issues_count = quality_delta_service.count_unresolved_critical_issues(latest_reviews)
            narrative_seed_report = self._extract_seed_consumption_report(latest_reviews)
            delta_report = quality_delta_service.evaluate(
                QualityDeltaContext(
                    draft_text=draft.content or "",
                    candidate_published_text=draft.content or "",
                    unresolved_critical_issues_count=unresolved_critical_issues_count,
                )
            )
            if delta_report.decision == "fail":
                raise ConflictError(f"发布质量增益检查未通过：{delta_report.summary}")
            title = request.publish_title or blueprint.title_hint or f"第{goal.chapter_no}章"
            published_chapter = PublishedChapterORM(
                project_id=request.project_id,
                draft_id=draft.id,
                blueprint_id=blueprint.id,
                chapter_goal_id=goal.id,
                chapter_no=goal.chapter_no,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                title=title,
                content=draft.content,
                status=ChapterStatus.PUBLISHED.value,
                snapshot_id=changeset.result_snapshot_id,
                changeset_id=changeset.id,
                publish_metadata={
                    "blueprint_title_hint": blueprint.title_hint,
                    "goal_structure": goal.structure_goal,
                    "draft_metadata": draft.draft_metadata,
                    "workflow_run_id": run.id,
                    "trace_id": run.trace_id,
                    "quality_delta_report": delta_report.model_dump(mode="json"),
                    "seed_consumption_report": (narrative_seed_report.model_dump(mode="json") if narrative_seed_report is not None else None),
                },
            )
            db.add(published_chapter)
            db.flush()
            publish_record = PublishRecordORM(
                project_id=request.project_id,
                published_chapter_id=published_chapter.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                draft_id=draft.id,
                snapshot_id=changeset.result_snapshot_id,
                changeset_id=changeset.id,
                publish_gate_review_id=publish_gate_review.id,
                published_by=request.published_by.strip(),
                publish_status="published",
                notes=request.notes,
            )
            db.add(publish_record)
            chapter_state_service.transition(
                db=db,
                draft=draft,
                to_status=ChapterStatus.PUBLISHED.value,
                trigger_type="publish_completed",
                trigger_ref=published_chapter.id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                reason="章节已正式发布",
                metadata={"publish_record_id": publish_record.id, "snapshot_id": changeset.result_snapshot_id},
            )
            project.current_chapter_no = max(project.current_chapter_no, goal.chapter_no)
            chapter_summary = chapter_summary_service.generate_for_published(
                db=db,
                request=GenerateChapterSummaryRequest(
                    project_id=request.project_id,
                    published_chapter_id=published_chapter.id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                ),
                commit=False,
            )
            derived_update_result = derived_update_service.run_post_publish_updates(
                db=db,
                request=RunDerivedUpdatesRequest(
                    project_id=request.project_id,
                    published_chapter_id=published_chapter.id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                ),
                commit=False,
            )
            workflow_run_service.update_progress(
                db=db,
                run=run,
                current_step="published",
                status="completed",
                complete=True,
                source_ref=published_chapter.id,
                extra_metadata={
                    "latest_chapter_summary": chapter_summary.summary,
                    "latest_next_chapter_seed": chapter_summary.next_chapter_seed,
                    "derived_update_status": derived_update_result.status,
                    "derived_update_task_count": len(derived_update_result.tasks),
                },
            )
            db.add(
                ImmutableLogORM(
                    event_type="chapter_published",
                    project_id=request.project_id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                    event_payload={
                        "draft_id": draft.id,
                        "published_chapter_id": published_chapter.id,
                        "chapter_no": goal.chapter_no,
                        "snapshot_id": changeset.result_snapshot_id,
                        "changeset_id": changeset.id,
                        "published_by": request.published_by.strip(),
                        "quality_delta_report": delta_report.model_dump(mode="json"),
                        "seed_consumption_report": (
                            narrative_seed_report.model_dump(mode="json") if narrative_seed_report is not None else None
                        ),
                    },
                )
            )
            db.commit()
            db.refresh(published_chapter)
            db.refresh(publish_record)
            scope.success(f"第 {goal.chapter_no} 章发布完成")
            return PublishResult(
                success=True,
                publish_status="published",
                idempotent_hit=False,
                published_chapter=PublishedChapter.model_validate(published_chapter),
                publish_record=PublishRecord.model_validate(publish_record),
                delta_report=delta_report,
                seed_consumption_report=narrative_seed_report,
                chapter_summary=chapter_summary,
                derived_update_result=derived_update_result,
            )
        except Exception as exc:
            db.rollback()
            draft = db.get(ChapterDraftORM, request.draft_id)
            if draft is not None and draft.project_id == request.project_id and draft.status != ChapterStatus.PUBLISHED.value:
                current_run = workflow_run_service.ensure_run(
                    db=db,
                    project_id=request.project_id,
                    workflow_run_id=run.id,
                    trace_id=run.trace_id,
                    workflow_name="chapter_cycle_workflow_v1",
                    chapter_no=goal.chapter_no,
                    source_type="chapter_publish",
                    source_ref=draft.id,
                    current_step="publish_failed",
                )
                if draft.status != ChapterStatus.PUBLISH_FAILED.value:
                    chapter_state_service.transition(
                        db=db,
                        draft=draft,
                        to_status=ChapterStatus.PUBLISH_FAILED.value,
                        trigger_type="publish_exception",
                        trigger_ref=draft.id,
                        workflow_run_id=current_run.id,
                        trace_id=current_run.trace_id,
                        reason="发布阶段发生异常，进入可重试失败状态",
                        metadata={"error": str(exc)},
                    )
                workflow_run_service.mark_attention(
                    db=db,
                    run=current_run,
                    current_step="publish_failed",
                    reason="发布阶段发生异常",
                    extra_metadata={"error": str(exc)},
                )
                db.commit()
            scope.failure("章节发布失败", exc, workflow_run_id=run.id, draft_id=request.draft_id)
            raise

    def _ensure_required_gates(self, db: Session, project_id: str, draft_id: str) -> None:
        reviews = self._query_gate_reviews(db=db, project_id=project_id, draft_id=draft_id, passed_only=True)
        passed_gate_names = {review.gate_name for review in reviews}
        missing = [gate for gate in self.REQUIRED_PUBLISH_GATES if gate not in passed_gate_names]
        if missing:
            raise ConflictError(f"发布前 Gate 条件未满足，缺少通过的 Gate: {', '.join(missing)}")

    def _query_gate_reviews(self, db: Session, *, project_id: str, draft_id: str, passed_only: bool = False) -> list:
        from app.db.models import GateReviewORM

        query = db.query(GateReviewORM).filter(
            GateReviewORM.project_id == project_id,
            GateReviewORM.draft_id == draft_id,
        )
        if passed_only:
            query = query.filter(GateReviewORM.passed.is_(True))
        return query.order_by(GateReviewORM.created_at.desc()).all()

    def _list_latest_gate_reviews(self, db: Session, *, project_id: str, draft_id: str) -> list[dict]:
        latest_by_gate: dict[str, dict] = {}
        for review in self._query_gate_reviews(db=db, project_id=project_id, draft_id=draft_id, passed_only=False):
            if review.gate_name in latest_by_gate:
                continue
            latest_by_gate[review.gate_name] = {
                "gate_name": review.gate_name,
                "pass_status": review.pass_status,
                "issues": list(review.issues or []),
            }
        return list(latest_by_gate.values())

    def _extract_seed_consumption_report(self, latest_reviews: list[dict]):
        from app.schemas.chapter import SeedConsumptionReport

        for review in latest_reviews:
            if review.get("gate_name") != GateName.NARRATIVE.value:
                continue
            for issue in list(review.get("issues") or []):
                if not isinstance(issue, dict):
                    continue
                metadata = issue.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                payload = metadata.get("seed_consumption_report")
                if isinstance(payload, dict):
                    return SeedConsumptionReport.model_validate(payload)
        return None


publish_service = PublishService()
