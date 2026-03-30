from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import CanonSnapshotORM, ImmutableLogORM, ProjectORM, PublishedChapterORM
from app.schemas.continuity import CanonContextSummary, ContinuityPack, RecentChapterContext, ResolveContinuityPackRequest
from app.services.chapter_summary_service import chapter_summary_service
from app.services.workflow_run_service import workflow_run_service


class ContinuityService:
    def _build_canon_summary(self, *, snapshot: CanonSnapshotORM | None, published_count: int) -> CanonContextSummary | None:
        if snapshot is None:
            return None
        timeline_tail = []
        for item in list(snapshot.timeline_events or [])[-5:]:
            if isinstance(item, dict):
                timeline_tail.append(str(item.get("title") or item.get("summary") or item.get("event_type") or "timeline_event"))
            else:
                timeline_tail.append(str(item))
        summary = (
            f"Canon v{snapshot.version_no}：角色{len(snapshot.character_cards or [])}，规则{len(snapshot.rule_cards or [])}，"
            f"关系{len(snapshot.relationship_edges or [])}，未闭环{len(snapshot.open_loops or [])}，已发布章节{published_count}。"
        )
        return CanonContextSummary(
            snapshot_id=snapshot.id,
            version_no=snapshot.version_no,
            summary=summary,
            character_count=len(snapshot.character_cards or []),
            rule_count=len(snapshot.rule_cards or []),
            relationship_count=len(snapshot.relationship_edges or []),
            open_loop_count=len(snapshot.open_loops or []),
            published_chapter_count=published_count,
            timeline_tail=timeline_tail,
        )

    def resolve_pack(self, db: Session, request: ResolveContinuityPackRequest, *, commit: bool = True) -> ContinuityPack:
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在，无法解析 continuity pack")
        run = workflow_run_service.ensure_run(
            db=db,
            project_id=request.project_id,
            workflow_run_id=request.workflow_run_id,
            trace_id=request.trace_id,
            workflow_name="chapter_cycle_workflow_v1",
            chapter_no=request.target_chapter_no,
            source_type="continuity_pack",
            current_step="continuity_pack_resolution",
        )
        existing = dict(run.run_metadata or {}).get("continuity_pack")
        if existing and not request.force_refresh:
            try:
                pack = ContinuityPack.model_validate(existing)
                if pack.target_chapter_no == request.target_chapter_no:
                    return pack
            except Exception:
                pass

        published_query = (
            db.query(PublishedChapterORM)
            .filter(PublishedChapterORM.project_id == request.project_id, PublishedChapterORM.chapter_no < request.target_chapter_no)
            .order_by(PublishedChapterORM.chapter_no.desc(), PublishedChapterORM.created_at.desc())
        )
        recent_published = list(reversed(published_query.limit(request.recent_limit).all()))
        recent_summaries: list[RecentChapterContext] = []
        for item in recent_published:
            summary = chapter_summary_service.get_published_summary(db=db, project_id=request.project_id, published_chapter_id=item.id, force_regenerate=False)
            recent_summaries.append(
                RecentChapterContext(
                    published_chapter_id=item.id,
                    chapter_no=item.chapter_no,
                    title=item.title,
                    summary=summary.summary,
                    state_summary=summary.state_summary,
                    next_chapter_seed=summary.next_chapter_seed,
                    unresolved_open_loops=list(summary.unresolved_open_loops or []),
                    carry_over_constraints=list(summary.carry_over_constraints or []),
                )
            )

        latest_summary = recent_summaries[-1] if recent_summaries else None
        latest_snapshot = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == request.project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        published_count = db.query(PublishedChapterORM).filter(PublishedChapterORM.project_id == request.project_id).count()
        canon_summary = self._build_canon_summary(snapshot=latest_snapshot, published_count=published_count)

        previous_summary = (request.previous_chapter_summary or "").strip() or (latest_summary.state_summary if latest_summary else None) or (latest_summary.summary if latest_summary else None)
        unresolved_open_loops = [str(item) for item in list(request.unresolved_open_loops or []) if str(item).strip()]
        if not unresolved_open_loops:
            unresolved_open_loops = list(latest_summary.unresolved_open_loops or []) if latest_summary else []
        if not unresolved_open_loops and latest_snapshot is not None:
            for item in list(latest_snapshot.open_loops or []):
                if isinstance(item, dict):
                    unresolved_open_loops.append(str(item.get("loop_name") or item.get("name") or item.get("summary") or "未命名伏笔"))
                else:
                    unresolved_open_loops.append(str(item))
        unresolved_open_loops = [item for item in unresolved_open_loops if item][:8]

        carry_over_constraints = list(latest_summary.carry_over_constraints or []) if latest_summary else []
        if not carry_over_constraints:
            carry_over_constraints = [f"继续处理：{item}" for item in unresolved_open_loops[:3]]
        next_chapter_seed = (latest_summary.next_chapter_seed if latest_summary else None) or (f"下一章承接：{'；'.join(unresolved_open_loops[:3])}" if unresolved_open_loops else "继续推进当前卷目标并制造新冲突。")

        warnings: list[str] = []
        if latest_snapshot is None:
            warnings.append("当前项目尚无 Canon Snapshot，连续性输入仅基于已发布章节摘要。")
        if latest_summary is None:
            warnings.append("上一章摘要缺失，本章连续性输入将退化为 Canon 与 open loops。")

        continuity_summary_parts = []
        if previous_summary:
            continuity_summary_parts.append(f"上章状态：{previous_summary}")
        if next_chapter_seed:
            continuity_summary_parts.append(f"下一章种子：{next_chapter_seed}")
        if unresolved_open_loops:
            continuity_summary_parts.append(f"待承接线索：{'；'.join(unresolved_open_loops[:3])}")
        if canon_summary is not None:
            continuity_summary_parts.append(canon_summary.summary)
        continuity_summary = " | ".join(continuity_summary_parts) if continuity_summary_parts else "当前无可用连续性上下文。"

        pack = ContinuityPack(
            project_id=request.project_id,
            target_chapter_no=request.target_chapter_no,
            workflow_run_id=run.id,
            trace_id=run.trace_id,
            source_snapshot_id=latest_snapshot.id if latest_snapshot is not None else None,
            source_published_chapter_id=latest_summary.published_chapter_id if latest_summary is not None else None,
            previous_chapter_summary=previous_summary,
            next_chapter_seed=next_chapter_seed,
            unresolved_open_loops=unresolved_open_loops,
            carry_over_constraints=carry_over_constraints,
            recent_chapter_summaries=recent_summaries,
            canon_summary=canon_summary,
            continuity_summary=continuity_summary,
            warnings=warnings,
            generated_at=datetime.now(timezone.utc),
        )

        workflow_run_service.update_progress(
            db=db,
            run=run,
            current_step="continuity_pack_ready",
            extra_metadata={
                "continuity_pack": pack.model_dump(mode="json"),
                "previous_chapter_summary": pack.previous_chapter_summary,
                "unresolved_open_loops": pack.unresolved_open_loops,
                "next_chapter_seed": pack.next_chapter_seed,
                "continuity_summary": pack.continuity_summary,
                "canon_summary": pack.canon_summary.summary if pack.canon_summary is not None else None,
            },
        )
        db.add(
            ImmutableLogORM(
                event_type="continuity_pack_resolved",
                project_id=request.project_id,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                event_payload={
                    "target_chapter_no": request.target_chapter_no,
                    "source_snapshot_id": pack.source_snapshot_id,
                    "source_published_chapter_id": pack.source_published_chapter_id,
                    "next_chapter_seed": pack.next_chapter_seed,
                    "open_loop_count": len(pack.unresolved_open_loops),
                    "recent_summary_count": len(pack.recent_chapter_summaries),
                    "warnings": pack.warnings,
                },
            )
        )
        if commit:
            db.commit()
        else:
            db.flush()
        return pack


continuity_service = ContinuityService()
