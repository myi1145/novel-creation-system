from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
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
from app.services.workflow_run_service import workflow_run_service


class PublishService:
    REQUIRED_PUBLISH_GATES = [GateName.SCHEMA.value, GateName.CANON.value, GateName.NARRATIVE.value, GateName.PUBLISH.value]

    def publish_draft(self, db: Session, request: PublishDraftRequest) -> PublishResult:
        draft = db.get(ChapterDraftORM, request.draft_id)
        if draft is None or draft.project_id != request.project_id:
            raise NotFoundError("正文草稿不存在")
        if draft.status == ChapterStatus.PUBLISHED.value:
            raise ConflictError("该草稿已经发布")
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
                    },
                )
            )
            db.commit()
            db.refresh(published_chapter)
            db.refresh(publish_record)
            return PublishResult(
                published_chapter=PublishedChapter.model_validate(published_chapter),
                publish_record=PublishRecord.model_validate(publish_record),
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
            raise

    def _ensure_required_gates(self, db: Session, project_id: str, draft_id: str) -> None:
        from app.db.models import GateReviewORM

        reviews = (
            db.query(GateReviewORM)
            .filter(
                GateReviewORM.project_id == project_id,
                GateReviewORM.draft_id == draft_id,
                GateReviewORM.passed.is_(True),
            )
            .order_by(GateReviewORM.created_at.desc())
            .all()
        )
        passed_gate_names = {review.gate_name for review in reviews}
        missing = [gate for gate in self.REQUIRED_PUBLISH_GATES if gate not in passed_gate_names]
        if missing:
            raise ConflictError(f"发布前 Gate 条件未满足，缺少通过的 Gate: {', '.join(missing)}")


publish_service = PublishService()
