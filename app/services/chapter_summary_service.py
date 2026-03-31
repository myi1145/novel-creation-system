from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_logging import StepLogScope
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.logging_context import set_log_context
from app.db.models import CanonSnapshotORM, ChapterBlueprintORM, ChapterGoalORM, ProjectORM, PublishedChapterORM, ImmutableLogORM, WorkflowRunORM
from app.schemas.chapter import ChapterSummary, GenerateChapterSummaryRequest
from app.services.agent_gateway import agent_gateway
from app.services.workflow_run_service import workflow_run_service

logger = get_logger("workflow")

class ChapterSummaryService:
    def _build_fallback(self, *, project_id: str, published: PublishedChapterORM, blueprint: ChapterBlueprintORM, goal: ChapterGoalORM, workflow_run_id: str | None, trace_id: str | None, open_loops: list[str]) -> ChapterSummary:
        generated_at = datetime.now(timezone.utc)
        summary = blueprint.summary or f"第{goal.chapter_no}章完成一次主线推进。"
        return ChapterSummary(
            project_id=project_id,
            published_chapter_id=published.id,
            draft_id=published.draft_id,
            blueprint_id=published.blueprint_id,
            chapter_goal_id=published.chapter_goal_id,
            chapter_no=published.chapter_no,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            summary=summary,
            state_summary=f"第{goal.chapter_no}章已发布，正史快照更新至 {published.snapshot_id}。",
            key_plot_points=[summary, f"发布标题：{published.title}"],
            canon_updates=[f"已应用 ChangeSet {published.changeset_id}"],
            unresolved_open_loops=open_loops[:5],
            carry_over_constraints=[f"下一章继续处理：{item}" for item in open_loops[:3]],
            next_chapter_seed=f"下一章继续围绕：{'；'.join(open_loops[:3]) if open_loops else '当前卷目标后续反应与新冲突'}",
            generated_by="fallback",
            generated_at=generated_at,
        )

    def _persist_summary(self, db: Session, published: PublishedChapterORM, summary: ChapterSummary) -> None:
        metadata = dict(published.publish_metadata or {})
        metadata["chapter_summary"] = summary.model_dump(mode="json")
        metadata["summary_generated_at"] = summary.generated_at.isoformat()
        metadata["next_chapter_seed"] = summary.next_chapter_seed
        published.publish_metadata = metadata
        db.flush()

    def generate_for_published(self, db: Session, request: GenerateChapterSummaryRequest, *, commit: bool = True) -> ChapterSummary:
        set_log_context(project_id=request.project_id, workflow_run_id=request.workflow_run_id, module="chapter_summary_service", event="summary.generate", status="started")
        scope = StepLogScope(
            logger_name="workflow",
            module="chapter_summary_service",
            event="summary.generate",
            message_started="开始生成章节摘要",
            start_fields={"project_id": request.project_id, "published_chapter_id": request.published_chapter_id, "workflow_run_id": request.workflow_run_id},
        )
        published = db.get(PublishedChapterORM, request.published_chapter_id)
        if published is None or published.project_id != request.project_id:
            raise NotFoundError("已发布章节不存在")
        existing = dict(published.publish_metadata or {}).get("chapter_summary")
        if existing and not request.force_regenerate:
            cached = ChapterSummary.model_validate(existing)
            scope.success("章节摘要生成完成")
            return cached
        project = db.get(ProjectORM, request.project_id)
        blueprint = db.get(ChapterBlueprintORM, published.blueprint_id)
        goal = db.get(ChapterGoalORM, published.chapter_goal_id)
        snapshot = db.get(CanonSnapshotORM, published.snapshot_id) if published.snapshot_id else None
        if project is None or blueprint is None or goal is None:
            raise NotFoundError("章节摘要生成所需上下文不完整")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id or published.workflow_run_id,
            trace_id=request.trace_id or published.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            chapter_no=published.chapter_no,
            source_type="chapter_summary",
            source_ref=published.id,
            current_step="chapter_summary_generation",
        )
        open_loops = list((snapshot.open_loops if snapshot is not None else []) or [])
        try:
            result = agent_gateway.summarize_chapter(
                db=db,
                context={
                    "project_id": request.project_id,
                    "genre_name": project.genre_id or "default",
                    "chapter_no": published.chapter_no,
                    "chapter_title": published.title,
                    "content": published.content,
                    "open_loops": open_loops,
                    "blueprint": {"title_hint": blueprint.title_hint, "summary": blueprint.summary, "advances": blueprint.advances, "risks": blueprint.risks},
                    "canon_summary_json": {
                        "version_no": snapshot.version_no if snapshot is not None else None,
                        "open_loops": open_loops[:5],
                        "timeline_events": list((snapshot.timeline_events if snapshot is not None else []) or [])[-5:],
                    },
                },
                audit_context={
                    "project_id": request.project_id,
                    "workflow_name": "chapter_cycle_workflow_v1",
                    "workflow_run_id": run.id,
                    "trace_id": run.trace_id,
                    "published_chapter_id": published.id,
                    "genre_id": project.genre_id,
                },
            )
            payload = result.payload if isinstance(result.payload, dict) else {}
            summary = ChapterSummary(
                project_id=request.project_id,
                published_chapter_id=published.id,
                draft_id=published.draft_id,
                blueprint_id=published.blueprint_id,
                chapter_goal_id=published.chapter_goal_id,
                chapter_no=published.chapter_no,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                summary=str(payload.get("summary") or blueprint.summary or f"第{published.chapter_no}章已发布。"),
                state_summary=str(payload.get("state_summary") or f"第{published.chapter_no}章已发布并更新正史。"),
                key_plot_points=[str(item) for item in list(payload.get("key_plot_points") or [])],
                canon_updates=[str(item) for item in list(payload.get("canon_updates") or [])],
                unresolved_open_loops=[str(item) for item in list(payload.get("unresolved_open_loops") or open_loops[:5])],
                carry_over_constraints=[str(item) for item in list(payload.get("carry_over_constraints") or [])],
                next_chapter_seed=str(payload.get("next_chapter_seed") or "继续推进当前卷目标与未收束线索。"),
                generated_by="agent",
                generated_at=datetime.now(timezone.utc),
            )
        except Exception:
            summary = self._build_fallback(project_id=request.project_id, published=published, blueprint=blueprint, goal=goal, workflow_run_id=run.id, trace_id=run.trace_id, open_loops=open_loops)
        self._persist_summary(db=db, published=published, summary=summary)
        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="chapter_summary_generated",
            extra_metadata={
                "latest_chapter_summary": summary.summary,
                "latest_next_chapter_seed": summary.next_chapter_seed,
                "latest_published_chapter_id": published.id,
            },
        )
        db.add(
            ImmutableLogORM(
                event_type="chapter_summary_generated",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "published_chapter_id": published.id,
                    "chapter_no": published.chapter_no,
                    "summary": summary.summary,
                    "state_summary": summary.state_summary,
                    "next_chapter_seed": summary.next_chapter_seed,
                },
            )
        )
        if commit:
            db.commit()
            db.refresh(published)
        else:
            db.flush()
        scope.success("章节摘要生成完成", workflow_run_id=run.id, published_chapter_id=published.id, chapter_no=published.chapter_no, summary=summary.summary, next_action="refresh_next_chapter_seed")
        return summary

    def get_published_summary(self, db: Session, *, project_id: str, published_chapter_id: str, force_regenerate: bool = False) -> ChapterSummary:
        return self.generate_for_published(
            db=db,
            request=GenerateChapterSummaryRequest(project_id=project_id, published_chapter_id=published_chapter_id, force_regenerate=force_regenerate),
            commit=True,
        )

    def get_latest_project_summary(self, db: Session, *, project_id: str, before_chapter_no: int | None = None) -> ChapterSummary | None:
        query = db.query(PublishedChapterORM).filter(PublishedChapterORM.project_id == project_id)
        if before_chapter_no is not None:
            query = query.filter(PublishedChapterORM.chapter_no < before_chapter_no)
        published = query.order_by(PublishedChapterORM.chapter_no.desc(), PublishedChapterORM.created_at.desc()).first()
        if published is None:
            return None
        existing = dict(published.publish_metadata or {}).get("chapter_summary")
        if existing:
            return ChapterSummary.model_validate(existing)
        return self.generate_for_published(db=db, request=GenerateChapterSummaryRequest(project_id=project_id, published_chapter_id=published.id), commit=True)

    def get_latest_previous_summary_text(self, db: Session, *, project_id: str, before_chapter_no: int | None = None) -> str | None:
        latest = self.get_latest_project_summary(db=db, project_id=project_id, before_chapter_no=before_chapter_no)
        if latest is None:
            return None
        return latest.state_summary or latest.summary


chapter_summary_service = ChapterSummaryService()
