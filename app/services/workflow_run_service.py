from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import AgentCallLogORM, ChapterStateTransitionORM, ChangeSetORM, GateReviewORM, ImmutableLogORM, ProjectORM, PublishRecordORM, WorkflowRunORM
from app.schemas.workflow import WorkflowRun, WorkflowRunDetail, WorkflowRunSummary, WorkflowRunTraceNode



def _new_trace_id() -> str:
    return str(uuid4())


class WorkflowRunService:
    def _get_run_or_raise(self, db: Session, workflow_run_id: str) -> WorkflowRunORM:
        run = db.get(WorkflowRunORM, workflow_run_id)
        if run is None:
            raise NotFoundError("工作流运行记录不存在")
        return run

    def _append_control_event(self, run: WorkflowRunORM, *, action: str, operator: str, reason: str | None = None, notes: str | None = None, step: str | None = None, previous_status: str | None = None, next_status: str | None = None) -> None:
        metadata = dict(run.run_metadata or {})
        events = list(metadata.get("control_events") or [])
        events.append({
            "action": action,
            "operator": operator,
            "reason": reason,
            "notes": notes,
            "step": step or run.current_step,
            "previous_status": previous_status,
            "next_status": next_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        metadata["control_events"] = events[-50:]
        run.run_metadata = metadata

    def _log_control_event(self, db: Session, run: WorkflowRunORM, *, event_type: str, payload: dict) -> None:
        db.add(
            ImmutableLogORM(
                event_type=event_type,
                workflow_run_id=run.id,
                trace_id=run.trace_id,
                project_id=run.project_id,
                event_payload=payload,
            )
        )

    def ensure_run(
        self,
        db: Session,
        project_id: str,
        workflow_run_id: str | None,
        trace_id: str | None,
        workflow_name: str = "chapter_cycle_workflow_v1",
        chapter_no: int | None = None,
        source_type: str | None = None,
        source_ref: str | None = None,
        current_step: str = "chapter_goal_input",
        run_metadata: dict | None = None,
    ) -> WorkflowRunORM:
        project = db.get(ProjectORM, project_id)
        if project is None:
            raise NotFoundError("项目不存在，无法创建工作流运行记录")
        if workflow_run_id:
            run = db.get(WorkflowRunORM, workflow_run_id)
            if run is None or run.project_id != project_id:
                raise NotFoundError("workflow_run_id 不存在")
            if trace_id and run.trace_id != trace_id:
                raise ConflictError("trace_id 与 workflow_run_id 不匹配")
            if chapter_no is not None and run.chapter_no is None:
                run.chapter_no = chapter_no
            if source_ref and not run.source_ref:
                run.source_ref = source_ref
            if source_type and not run.source_type:
                run.source_type = source_type
            if workflow_name and not run.workflow_name:
                run.workflow_name = workflow_name
            if current_step:
                run.current_step = current_step
            if run_metadata:
                run.run_metadata = {**(run.run_metadata or {}), **run_metadata}
            db.flush()
            return run
        run = WorkflowRunORM(
            project_id=project_id,
            workflow_name=workflow_name,
            trace_id=trace_id or _new_trace_id(),
            chapter_no=chapter_no,
            source_type=source_type,
            source_ref=source_ref,
            status="running",
            current_step=current_step,
            run_metadata=run_metadata or {},
        )
        db.add(run)
        db.flush()
        return run

    def update_progress(
        self,
        db: Session,
        run: WorkflowRunORM | str | None,
        *,
        current_step: str | None = None,
        status: str | None = None,
        source_ref: str | None = None,
        complete: bool = False,
        extra_metadata: dict | None = None,
    ) -> WorkflowRunORM | None:
        if run is None:
            return None
        if isinstance(run, str):
            run = db.get(WorkflowRunORM, run)
        if run is None:
            return None
        if current_step:
            run.current_step = current_step
        if status:
            run.status = status
        if source_ref:
            run.source_ref = source_ref
        if extra_metadata:
            run.run_metadata = {**(run.run_metadata or {}), **extra_metadata}
        if complete:
            run.status = status or "completed"
            run.completed_at = datetime.now(timezone.utc)
        db.flush()
        return run

    def mark_attention(self, db: Session, run: WorkflowRunORM | str | None, *, current_step: str, reason: str, extra_metadata: dict | None = None) -> WorkflowRunORM | None:
        metadata = {"attention_reason": reason}
        if extra_metadata:
            metadata.update(extra_metadata)
        return self.update_progress(db=db, run=run, current_step=current_step, status="attention_required", extra_metadata=metadata)

    def fail_run(self, db: Session, run: WorkflowRunORM | str | None, *, current_step: str, reason: str, extra_metadata: dict | None = None) -> WorkflowRunORM | None:
        metadata = {"failure_reason": reason}
        if extra_metadata:
            metadata.update(extra_metadata)
        return self.update_progress(db=db, run=run, current_step=current_step, status="failed", extra_metadata=metadata)

    def pause_run(
        self,
        db: Session,
        workflow_run_id: str,
        *,
        paused_by: str,
        reason: str,
        pause_at_step: str | None = None,
        notes: str | None = None,
    ) -> WorkflowRunORM:
        run = self._get_run_or_raise(db=db, workflow_run_id=workflow_run_id)
        if run.status == "completed":
            raise ConflictError("已完成的工作流不能暂停")
        if run.status == "paused":
            raise ConflictError("工作流已经处于暂停状态")
        previous_status = run.status
        if pause_at_step:
            run.current_step = pause_at_step
        metadata = dict(run.run_metadata or {})
        metadata.update({
            "control_mode": "paused",
            "paused_by": paused_by.strip(),
            "pause_reason": reason.strip(),
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "resume_required": True,
            "pause_notes": notes,
        })
        run.run_metadata = metadata
        run.status = "paused"
        self._append_control_event(run, action="pause", operator=paused_by.strip(), reason=reason.strip(), notes=notes, step=run.current_step, previous_status=previous_status, next_status="paused")
        self._log_control_event(db=db, run=run, event_type="workflow_run_paused", payload={"paused_by": paused_by.strip(), "reason": reason.strip(), "notes": notes, "current_step": run.current_step, "previous_status": previous_status})
        db.flush()
        return run

    def resume_run(
        self,
        db: Session,
        workflow_run_id: str,
        *,
        resumed_by: str,
        resume_from_step: str | None = None,
        notes: str | None = None,
    ) -> WorkflowRunORM:
        run = self._get_run_or_raise(db=db, workflow_run_id=workflow_run_id)
        if run.status != "paused":
            raise ConflictError(f"当前运行不是可恢复状态（status={run.status}），仅 paused 状态允许 resume")
        previous_status = run.status
        if resume_from_step:
            run.current_step = resume_from_step
        metadata = dict(run.run_metadata or {})
        metadata.update({
            "control_mode": "auto",
            "resume_required": False,
            "last_resumed_by": resumed_by.strip(),
            "last_resumed_at": datetime.now(timezone.utc).isoformat(),
            "resume_notes": notes,
            "resume_from_step": resume_from_step or run.current_step,
        })
        run.run_metadata = metadata
        run.status = "running"
        self._append_control_event(run, action="resume", operator=resumed_by.strip(), notes=notes, step=run.current_step, previous_status=previous_status, next_status="running")
        self._log_control_event(db=db, run=run, event_type="workflow_run_resumed", payload={"resumed_by": resumed_by.strip(), "notes": notes, "resume_from_step": resume_from_step or run.current_step, "previous_status": previous_status})
        db.flush()
        return run

    def request_manual_takeover(
        self,
        db: Session,
        workflow_run_id: str,
        *,
        requested_by: str,
        reason: str,
        take_over_step: str | None = None,
        handoff_notes: str | None = None,
    ) -> WorkflowRunORM:
        run = self._get_run_or_raise(db=db, workflow_run_id=workflow_run_id)
        if run.status == "completed":
            raise ConflictError("已完成的工作流不能再进入人工接管")
        if run.status == "manual_review" and (run.run_metadata or {}).get("manual_takeover_active"):
            raise ConflictError("工作流已处于人工接管状态")
        previous_status = run.status
        if take_over_step:
            run.current_step = take_over_step
        metadata = dict(run.run_metadata or {})
        metadata.update({
            "control_mode": "manual",
            "manual_takeover_active": True,
            "manual_review_required": True,
            "manual_takeover_requested_by": requested_by.strip(),
            "manual_takeover_reason": reason.strip(),
            "manual_takeover_at": datetime.now(timezone.utc).isoformat(),
            "manual_takeover_notes": handoff_notes,
        })
        run.run_metadata = metadata
        run.status = "manual_review"
        self._append_control_event(run, action="manual_takeover", operator=requested_by.strip(), reason=reason.strip(), notes=handoff_notes, step=run.current_step, previous_status=previous_status, next_status="manual_review")
        self._log_control_event(db=db, run=run, event_type="workflow_run_manual_takeover_requested", payload={"requested_by": requested_by.strip(), "reason": reason.strip(), "handoff_notes": handoff_notes, "current_step": run.current_step, "previous_status": previous_status})
        db.flush()
        return run

    def mark_human_reviewed(
        self,
        db: Session,
        workflow_run_id: str,
        *,
        reviewed_by: str,
        review_notes: str,
        next_action: str | None = None,
        resume_run: bool = False,
        resume_from_step: str | None = None,
    ) -> WorkflowRunORM:
        run = self._get_run_or_raise(db=db, workflow_run_id=workflow_run_id)
        previous_status = run.status
        if previous_status not in {"manual_review", "attention_required", "failed", "paused"}:
            raise ConflictError(f"当前步骤状态不允许执行人工审阅确认（status={previous_status}）")
        if resume_from_step:
            run.current_step = resume_from_step
        metadata = dict(run.run_metadata or {})
        metadata.update({
            "manual_takeover_active": False,
            "manual_review_required": False,
            "last_human_reviewed_by": reviewed_by.strip(),
            "last_human_reviewed_at": datetime.now(timezone.utc).isoformat(),
            "last_human_review_notes": review_notes.strip(),
            "last_human_review_next_action": next_action,
            "control_mode": "auto" if resume_run else metadata.get("control_mode", "manual"),
        })
        run.run_metadata = metadata
        run.status = "running" if resume_run else "attention_required"
        self._append_control_event(run, action="mark_human_reviewed", operator=reviewed_by.strip(), reason=next_action, notes=review_notes.strip(), step=run.current_step, previous_status=previous_status, next_status=run.status)
        self._log_control_event(db=db, run=run, event_type="workflow_run_human_reviewed", payload={"reviewed_by": reviewed_by.strip(), "review_notes": review_notes.strip(), "next_action": next_action, "resume_run": resume_run, "resume_from_step": resume_from_step or run.current_step, "previous_status": previous_status})
        db.flush()
        return run

    def manual_continue(
        self,
        db: Session,
        workflow_run_id: str,
        *,
        continued_by: str,
        reason: str,
        continue_from_step: str | None = None,
        notes: str | None = None,
    ) -> WorkflowRunORM:
        run = self._get_run_or_raise(db=db, workflow_run_id=workflow_run_id)
        previous_status = run.status
        if previous_status not in {"attention_required", "failed", "manual_review"}:
            raise ConflictError(f"当前运行不是可恢复状态（status={previous_status}），仅 attention_required / failed / manual_review 允许 manual-continue")
        if continue_from_step:
            run.current_step = continue_from_step
        metadata = dict(run.run_metadata or {})
        metadata.update({
            "control_mode": "auto",
            "manual_takeover_active": False,
            "manual_review_required": False,
            "last_manual_continue_by": continued_by.strip(),
            "last_manual_continue_at": datetime.now(timezone.utc).isoformat(),
            "last_manual_continue_reason": reason.strip(),
            "last_manual_continue_notes": notes,
            "continue_from_step": continue_from_step or run.current_step,
        })
        run.run_metadata = metadata
        run.status = "running"
        self._append_control_event(run, action="manual_continue", operator=continued_by.strip(), reason=reason.strip(), notes=notes, step=run.current_step, previous_status=previous_status, next_status="running")
        self._log_control_event(db=db, run=run, event_type="workflow_run_manual_continued", payload={"continued_by": continued_by.strip(), "reason": reason.strip(), "notes": notes, "continue_from_step": continue_from_step or run.current_step, "previous_status": previous_status})
        db.flush()
        return run

    def list_runs(self, db: Session, project_id: str | None = None, limit: int = 50) -> list[WorkflowRunSummary]:
        query = db.query(WorkflowRunORM)
        if project_id:
            query = query.filter(WorkflowRunORM.project_id == project_id)
        rows = query.order_by(WorkflowRunORM.created_at.desc()).limit(max(1, min(limit, 200))).all()
        items: list[WorkflowRunSummary] = []
        for row in rows:
            items.append(
                WorkflowRunSummary(
                    workflow_run_id=row.id,
                    trace_id=row.trace_id,
                    project_id=row.project_id,
                    workflow_name=row.workflow_name,
                    status=row.status,
                    current_step=row.current_step,
                    chapter_no=row.chapter_no,
                    started_at=row.started_at,
                    completed_at=row.completed_at,
                    agent_call_count=db.query(AgentCallLogORM).filter(AgentCallLogORM.workflow_run_id == row.id).count(),
                    gate_review_count=db.query(GateReviewORM).filter(GateReviewORM.workflow_run_id == row.id).count(),
                    changeset_count=db.query(ChangeSetORM).filter(ChangeSetORM.workflow_run_id == row.id).count(),
                    published_count=db.query(PublishRecordORM).filter(PublishRecordORM.workflow_run_id == row.id).count(),
                )
            )
        return items

    def get_run_detail(self, db: Session, workflow_run_id: str) -> WorkflowRunDetail:
        run = db.get(WorkflowRunORM, workflow_run_id)
        if run is None:
            raise NotFoundError("工作流运行记录不存在")
        nodes: list[WorkflowRunTraceNode] = []
        for row in db.query(AgentCallLogORM).filter(AgentCallLogORM.workflow_run_id == workflow_run_id).order_by(AgentCallLogORM.created_at.asc()).all():
            nodes.append(WorkflowRunTraceNode(node_type="agent_call", node_id=row.id, created_at=row.created_at, payload={"agent_type": row.agent_type, "action_name": row.action_name, "call_status": row.call_status, "provider": row.active_provider}))
        for row in db.query(ChapterStateTransitionORM).filter(ChapterStateTransitionORM.workflow_run_id == workflow_run_id).order_by(ChapterStateTransitionORM.created_at.asc()).all():
            nodes.append(WorkflowRunTraceNode(node_type="chapter_state_transition", node_id=row.id, created_at=row.created_at, payload={"draft_id": row.draft_id, "from_status": row.from_status, "to_status": row.to_status, "trigger_type": row.trigger_type, "reason": row.reason}))
        for row in db.query(GateReviewORM).filter(GateReviewORM.workflow_run_id == workflow_run_id).order_by(GateReviewORM.created_at.asc()).all():
            nodes.append(WorkflowRunTraceNode(node_type="gate_review", node_id=row.id, created_at=row.created_at, payload={"gate_name": row.gate_name, "pass_status": row.pass_status, "highest_severity": row.highest_severity}))
        for row in db.query(ChangeSetORM).filter(ChangeSetORM.workflow_run_id == workflow_run_id).order_by(ChangeSetORM.created_at.asc()).all():
            nodes.append(WorkflowRunTraceNode(node_type="changeset", node_id=row.id, created_at=row.created_at, payload={"status": row.status, "source_type": row.source_type, "source_ref": row.source_ref, "result_snapshot_id": row.result_snapshot_id}))
        for row in db.query(PublishRecordORM).filter(PublishRecordORM.workflow_run_id == workflow_run_id).order_by(PublishRecordORM.created_at.asc()).all():
            nodes.append(WorkflowRunTraceNode(node_type="publish_record", node_id=row.id, created_at=row.created_at, payload={"published_chapter_id": row.published_chapter_id, "publish_status": row.publish_status, "snapshot_id": row.snapshot_id}))
        for row in db.query(ImmutableLogORM).filter(ImmutableLogORM.workflow_run_id == workflow_run_id, ImmutableLogORM.event_type.like("workflow_run_%")).order_by(ImmutableLogORM.created_at.asc()).all():
            nodes.append(WorkflowRunTraceNode(node_type="workflow_control", node_id=str(row.id), created_at=row.created_at, payload={"event_type": row.event_type, **(row.event_payload or {})}))
        nodes.sort(key=lambda item: item.created_at or datetime.now(timezone.utc))
        return WorkflowRunDetail(run=WorkflowRun.model_validate(run), nodes=nodes)


workflow_run_service = WorkflowRunService()
