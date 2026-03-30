from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import ChapterDraftORM, ChapterStateTransitionORM, ImmutableLogORM
from app.domain.enums import ChapterStatus
from app.schemas.chapter import ChapterStateTransition


_ALLOWED_TRANSITIONS: dict[str | None, set[str]] = {
    None: {ChapterStatus.DRAFTING.value},
    ChapterStatus.DRAFTING.value: {ChapterStatus.REVIEWING.value, ChapterStatus.FAILED.value},
    ChapterStatus.REVIEWING.value: {ChapterStatus.APPROVED.value, ChapterStatus.REVIEW_FAILED.value, ChapterStatus.FAILED.value},
    ChapterStatus.REVIEW_FAILED.value: {ChapterStatus.DRAFTING.value, ChapterStatus.REVIEWING.value, ChapterStatus.FAILED.value},
    ChapterStatus.APPROVED.value: {
        ChapterStatus.REVIEWING.value,
        ChapterStatus.CHANGESET_PROPOSED.value,
        ChapterStatus.FAILED.value,
    },
    ChapterStatus.CHANGESET_PROPOSED.value: {
        ChapterStatus.APPROVED.value,
        ChapterStatus.CHANGESET_APPROVED.value,
        ChapterStatus.FAILED.value,
    },
    ChapterStatus.CHANGESET_APPROVED.value: {
        ChapterStatus.APPROVED.value,
        ChapterStatus.CANON_APPLIED.value,
        ChapterStatus.FAILED.value,
    },
    ChapterStatus.CANON_APPLIED.value: {
        ChapterStatus.PUBLISH_PENDING.value,
        ChapterStatus.PUBLISH_FAILED.value,
        ChapterStatus.FAILED.value,
    },
    ChapterStatus.PUBLISH_PENDING.value: {
        ChapterStatus.PUBLISHED.value,
        ChapterStatus.PUBLISH_FAILED.value,
        ChapterStatus.FAILED.value,
    },
    ChapterStatus.PUBLISH_FAILED.value: {
        ChapterStatus.CANON_APPLIED.value,
        ChapterStatus.PUBLISH_PENDING.value,
        ChapterStatus.FAILED.value,
    },
    ChapterStatus.PUBLISHED.value: set(),
    ChapterStatus.FAILED.value: {
        ChapterStatus.DRAFTING.value,
        ChapterStatus.REVIEWING.value,
        ChapterStatus.CANON_APPLIED.value,
        ChapterStatus.PUBLISH_PENDING.value,
    },
}


class ChapterStateService:
    def bootstrap_draft(
        self,
        db: Session,
        draft: ChapterDraftORM,
        *,
        workflow_run_id: str | None = None,
        trace_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChapterStateTransitionORM:
        return self.transition(
            db=db,
            draft=draft,
            to_status=ChapterStatus.DRAFTING.value,
            trigger_type="draft_created",
            trigger_ref=draft.id,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            reason=reason or "正文草稿已创建",
            metadata=metadata,
            from_status_override=None,
        )

    def transition(
        self,
        db: Session,
        draft: ChapterDraftORM,
        *,
        to_status: str,
        trigger_type: str,
        trigger_ref: str | None = None,
        workflow_run_id: str | None = None,
        trace_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        allow_noop: bool = True,
        from_status_override: str | None | object = ...,
    ) -> ChapterStateTransitionORM:
        current_status = draft.status if from_status_override is ... else from_status_override
        if current_status == to_status and allow_noop:
            return self._record_transition(
                db=db,
                draft=draft,
                from_status=current_status,
                to_status=to_status,
                trigger_type=trigger_type,
                trigger_ref=trigger_ref,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                reason=reason,
                metadata={**(metadata or {}), "noop": True},
            )
        allowed = _ALLOWED_TRANSITIONS.get(current_status, set())
        if to_status not in allowed:
            raise ConflictError(f"章节状态不允许从 {current_status or 'none'} 迁移到 {to_status}")
        draft.status = to_status
        return self._record_transition(
            db=db,
            draft=draft,
            from_status=current_status,
            to_status=to_status,
            trigger_type=trigger_type,
            trigger_ref=trigger_ref,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            reason=reason,
            metadata=metadata,
        )

    def list_history(self, db: Session, draft_id: str, project_id: str | None = None) -> list[ChapterStateTransition]:
        draft = db.get(ChapterDraftORM, draft_id)
        if draft is None:
            raise NotFoundError("正文草稿不存在")
        if project_id and draft.project_id != project_id:
            raise NotFoundError("正文草稿不存在")
        rows = (
            db.query(ChapterStateTransitionORM)
            .filter(ChapterStateTransitionORM.draft_id == draft_id)
            .order_by(ChapterStateTransitionORM.created_at.asc())
            .all()
        )
        return [ChapterStateTransition.model_validate(row) for row in rows]

    def transition_by_draft_id(
        self,
        db: Session,
        draft_id: str,
        *,
        to_status: str,
        trigger_type: str,
        trigger_ref: str | None = None,
        workflow_run_id: str | None = None,
        trace_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        allow_noop: bool = True,
    ) -> ChapterStateTransitionORM:
        draft = db.get(ChapterDraftORM, draft_id)
        if draft is None:
            raise NotFoundError("正文草稿不存在")
        return self.transition(
            db=db,
            draft=draft,
            to_status=to_status,
            trigger_type=trigger_type,
            trigger_ref=trigger_ref,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            reason=reason,
            metadata=metadata,
            allow_noop=allow_noop,
        )

    def _record_transition(
        self,
        db: Session,
        *,
        draft: ChapterDraftORM,
        from_status: str | None,
        to_status: str,
        trigger_type: str,
        trigger_ref: str | None,
        workflow_run_id: str | None,
        trace_id: str | None,
        reason: str | None,
        metadata: dict[str, Any] | None,
    ) -> ChapterStateTransitionORM:
        transition = ChapterStateTransitionORM(
            project_id=draft.project_id,
            draft_id=draft.id,
            workflow_run_id=workflow_run_id or draft.workflow_run_id,
            trace_id=trace_id or draft.trace_id,
            from_status=from_status,
            to_status=to_status,
            trigger_type=trigger_type,
            trigger_ref=trigger_ref,
            reason=reason,
            transition_metadata=metadata or {},
        )
        db.add(transition)
        db.flush()
        db.add(
            ImmutableLogORM(
                event_type="chapter_status_changed",
                project_id=draft.project_id,
                workflow_run_id=transition.workflow_run_id,
                trace_id=transition.trace_id,
                event_payload={
                    "draft_id": draft.id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "trigger_type": trigger_type,
                    "trigger_ref": trigger_ref,
                    "reason": reason,
                    "metadata": metadata or {},
                },
            )
        )
        return transition


chapter_state_service = ChapterStateService()
