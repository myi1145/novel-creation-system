from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import GateName
from app.schemas.chapter import ChapterBlueprint, ChapterDraft, ChapterGoal, ChapterSummary, PublishResult, SceneCard
from app.schemas.continuity import ContinuityPack
from app.schemas.derived_update import DEFAULT_DERIVED_UPDATE_TASKS, DerivedUpdateBatchResult, RunDerivedUpdatesRequest
from app.schemas.changeset import ChangeSet, ChangeSetProposal
from app.schemas.gate import GateReviewResult


class WorkflowRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    workflow_name: str
    trace_id: str
    chapter_no: int | None = None
    source_type: str | None = None
    source_ref: str | None = None
    status: str
    current_step: str
    run_metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowRunSummary(BaseModel):
    workflow_run_id: str
    trace_id: str
    project_id: str
    workflow_name: str
    status: str
    current_step: str
    chapter_no: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
    agent_call_count: int = 0
    gate_review_count: int = 0
    changeset_count: int = 0
    published_count: int = 0


class WorkflowRunTraceNode(BaseModel):
    node_type: str
    node_id: str
    created_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunDetail(BaseModel):
    run: WorkflowRun
    nodes: list[WorkflowRunTraceNode] = Field(default_factory=list)


class DiagnosticIssue(BaseModel):
    issue_type: str
    severity: str
    message: str
    related_id: str | None = None
    related_type: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowDiagnosticsOverview(BaseModel):
    project_id: str | None = None
    workflow_run_id: str | None = None
    generated_at: datetime
    health_status: str
    counts: dict[str, int] = Field(default_factory=dict)
    provider_governance: dict[str, Any] = Field(default_factory=dict)
    recent_run_statuses: list[dict[str, Any]] = Field(default_factory=list)
    recent_issues: list[DiagnosticIssue] = Field(default_factory=list)


class WorkflowRunDiagnostics(BaseModel):
    run: WorkflowRun
    health_status: str
    summary: dict[str, Any] = Field(default_factory=dict)
    recent_issues: list[DiagnosticIssue] = Field(default_factory=list)
    nodes: list[WorkflowRunTraceNode] = Field(default_factory=list)


class WorkflowRunControlResult(BaseModel):
    run: WorkflowRun
    control_action: str
    message: str
    generated_at: datetime


class PauseWorkflowRunRequest(BaseModel):
    workflow_run_id: str
    paused_by: str
    reason: str
    pause_at_step: str | None = None
    notes: str | None = None


class ResumeWorkflowRunRequest(BaseModel):
    workflow_run_id: str
    resumed_by: str
    resume_from_step: str | None = None
    notes: str | None = None


class ManualTakeoverRequest(BaseModel):
    workflow_run_id: str
    requested_by: str
    reason: str
    take_over_step: str | None = None
    handoff_notes: str | None = None


class MarkHumanReviewedRequest(BaseModel):
    workflow_run_id: str
    reviewed_by: str
    review_notes: str
    next_action: str | None = None
    resume_run: bool = False
    resume_from_step: str | None = None


class ManualContinueWorkflowRunRequest(BaseModel):
    workflow_run_id: str
    continued_by: str
    reason: str
    continue_from_step: str | None = None
    notes: str | None = None


class ExecuteChapterCycleRequest(BaseModel):
    project_id: str
    chapter_no: int | None = None
    current_volume_goal: str | None = None
    previous_chapter_summary: str | None = None
    unresolved_open_loops: list[str] = Field(default_factory=list)
    auto_resolve_continuity: bool = True
    continuity_recent_limit: int = Field(default=3, ge=1, le=5)
    chapter_goal_id: str | None = None
    candidate_count: int = Field(default=3, ge=1, le=7)
    selected_blueprint_id: str | None = None
    selected_by: str | None = None
    selection_reason: str | None = None
    auto_run_gates: bool = True
    review_gate_names: list[GateName] = Field(default_factory=lambda: [GateName.SCHEMA, GateName.CANON, GateName.NARRATIVE, GateName.STYLE])
    auto_revise_on_gate_failure: bool = False
    revision_instruction: str | None = None
    revised_by: str | None = None
    max_revision_rounds: int = Field(default=1, ge=0, le=3)
    auto_propose_changeset: bool = False
    auto_generate_changeset_proposal: bool = True
    changeset_rationale: str | None = None
    patch_operations: list[dict[str, Any]] = Field(default_factory=list)
    auto_approve_changeset: bool = False
    approved_by: str | None = None
    auto_apply_changeset: bool = False
    auto_publish: bool = False
    auto_generate_chapter_summary: bool = True
    auto_run_post_publish_updates: bool = True
    post_publish_task_names: list[str] = Field(default_factory=lambda: list(DEFAULT_DERIVED_UPDATE_TASKS))
    published_by: str | None = None
    publish_title: str | None = None
    notes: str | None = None
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ExecuteChapterCycleResult(BaseModel):
    run: WorkflowRun
    stage_status: str
    next_action: str | None = None
    continuity_pack: ContinuityPack | None = None
    goal: ChapterGoal | None = None
    blueprints: list[ChapterBlueprint] = Field(default_factory=list)
    selected_blueprint: ChapterBlueprint | None = None
    scenes: list[SceneCard] = Field(default_factory=list)
    draft: ChapterDraft | None = None
    gate_results: list[GateReviewResult] = Field(default_factory=list)
    changeset_proposal: ChangeSetProposal | None = None
    changeset: ChangeSet | None = None
    publish_result: PublishResult | None = None
    chapter_summary: ChapterSummary | None = None
    derived_update_result: DerivedUpdateBatchResult | None = None


class ExecuteChapterSequenceRequest(BaseModel):
    project_id: str
    start_chapter_no: int = Field(ge=1)
    chapter_count: int = Field(default=3, ge=1, le=20)
    current_volume_goal: str
    previous_chapter_summary: str | None = None
    unresolved_open_loops: list[str] = Field(default_factory=list)
    stop_on_attention: bool = True
    stop_on_failure: bool = True
    advance_only_on_completed: bool = True
    testing_auto_select_first_blueprint: bool = False
    testing_selected_by: str | None = None
    testing_selection_reason: str | None = None
    auto_resolve_continuity: bool = True
    continuity_recent_limit: int = Field(default=3, ge=1, le=5)
    candidate_count: int = Field(default=3, ge=1, le=7)
    auto_run_gates: bool = True
    review_gate_names: list[GateName] = Field(default_factory=lambda: [GateName.SCHEMA, GateName.CANON, GateName.NARRATIVE, GateName.STYLE])
    auto_revise_on_gate_failure: bool = False
    revision_instruction: str | None = None
    revised_by: str | None = None
    max_revision_rounds: int = Field(default=1, ge=0, le=3)
    auto_propose_changeset: bool = False
    auto_generate_changeset_proposal: bool = True
    changeset_rationale: str | None = None
    auto_approve_changeset: bool = False
    approved_by: str | None = None
    auto_apply_changeset: bool = False
    auto_publish: bool = False
    auto_generate_chapter_summary: bool = True
    auto_run_post_publish_updates: bool = True
    post_publish_task_names: list[str] = Field(default_factory=lambda: list(DEFAULT_DERIVED_UPDATE_TASKS))
    published_by: str | None = None
    publish_title: str | None = None
    notes: str | None = None
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ChapterSequenceItemResult(BaseModel):
    chapter_no: int
    workflow_run_id: str
    trace_id: str
    stage_status: str
    status: str | None = None
    next_action: str | None = None
    chapter_goal_id: str | None = None
    selected_blueprint_id: str | None = None
    draft_id: str | None = None
    changeset_id: str | None = None
    result_snapshot_id: str | None = None
    published_chapter_id: str | None = None
    latest_summary: str | None = None
    latest_next_chapter_seed: str | None = None
    derived_update_status: str | None = None
    chapter_summary: ChapterSummary | None = None
    chapter_result: ExecuteChapterCycleResult


class ExecuteChapterSequenceResult(BaseModel):
    run: WorkflowRun
    stage_status: str
    batch_status: str | None = None
    next_action: str | None = None
    stop_reason: str | None = None
    processed_chapter_count: int = 0
    completed_chapter_count: int = 0
    failed_chapter_count: int = 0
    attention_chapter_count: int = 0
    requested_chapter_count: int = 0
    stopped_at_chapter_no: int | None = None
    summary_message: str | None = None
    chapter_results: list[ChapterSequenceItemResult] = Field(default_factory=list)


class ChapterSequenceGateStat(BaseModel):
    gate_name: str
    total_reviews: int = 0
    passed_reviews: int = 0
    failed_reviews: int = 0
    highest_severity_counts: dict[str, int] = Field(default_factory=dict)


class ChapterSequenceChapterReport(BaseModel):
    chapter_no: int
    workflow_run_id: str
    trace_id: str
    run_status: str
    current_step: str
    stage_status: str
    next_action: str | None = None
    published: bool = False
    published_chapter_id: str | None = None
    gate_review_count: int = 0
    failed_gate_count: int = 0
    failed_gate_names: list[str] = Field(default_factory=list)
    agent_call_count: int = 0
    failed_agent_call_count: int = 0
    revision_count: int = 0
    changeset_count: int = 0
    published_record_count: int = 0
    continuity_applied: bool = False
    summary_generated: bool = False
    derived_update_status: str | None = None
    notes: list[str] = Field(default_factory=list)


class ChapterSequenceAttentionItem(BaseModel):
    chapter_no: int
    severity: str
    reason: str
    next_action: str | None = None
    workflow_run_id: str | None = None
    related_type: str | None = None
    related_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ChapterSequenceAcceptanceCheck(BaseModel):
    check_name: str
    status: str
    message: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class ChapterSequenceBatchReport(BaseModel):
    run: WorkflowRun
    project_id: str
    generated_at: datetime
    start_chapter_no: int | None = None
    end_chapter_no: int | None = None
    stop_reason: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    chapter_reports: list[ChapterSequenceChapterReport] = Field(default_factory=list)
    gate_stats: list[ChapterSequenceGateStat] = Field(default_factory=list)
    attention_items: list[ChapterSequenceAttentionItem] = Field(default_factory=list)
    acceptance_checks: list[ChapterSequenceAcceptanceCheck] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
