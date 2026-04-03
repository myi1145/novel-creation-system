from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import ChangeSetStatus, GateName
from app.schemas.common import IdentifiedModel


class ProposeChangeSetRequest(BaseModel):
    project_id: str
    source_type: str
    source_ref: str
    rationale: str
    patch_operations: list[dict[str, Any]] = Field(default_factory=list)
    workflow_run_id: str | None = None
    trace_id: str | None = None


class GenerateChangeSetProposalRequest(BaseModel):
    project_id: str
    draft_id: str | None = None
    rationale: str | None = None
    auto_create_changeset: bool = False
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ChangeSetEvidenceRef(BaseModel):
    source_type: str = "chapter_draft"
    source_ref: str | None = None
    excerpt: str | None = None
    note: str | None = None


class ChangeSetRewriteSuggestion(BaseModel):
    rewrite_issue_type: str
    target_excerpt: str
    target_location: str
    rewrite_goal: str
    rewrite_strategy: str
    expected_effect: str
    preserve_facts: list[str] = Field(default_factory=list)
    avoid_patterns: list[str] = Field(default_factory=list)


class ChangeSetProposal(BaseModel):
    project_id: str
    draft_id: str
    blueprint_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    proposal_summary: str
    rationale: str
    patch_operations: list[dict[str, Any]] = Field(default_factory=list)
    extracted_changes: list[str] = Field(default_factory=list)
    uncertain_items: list[str] = Field(default_factory=list)
    evidence_refs: list[ChangeSetEvidenceRef] = Field(default_factory=list)
    rewrite_suggestions: list[ChangeSetRewriteSuggestion] = Field(default_factory=list)
    affected_domains: list[str] = Field(default_factory=list)
    review_recommendation: str = "human_review"
    generated_by: str = "service"
    provider: str | None = None
    model: str | None = None
    changeset: "ChangeSet | None" = None




class RollbackChangeSetRequest(BaseModel):
    rolled_back_by: str
    reason: str
    workflow_run_id: str | None = None
    trace_id: str | None = None

class ChangeSet(IdentifiedModel):
    project_id: str
    source_type: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    source_ref: str
    rationale: str
    patch_operations: list[dict[str, Any]] = Field(default_factory=list)
    required_gate_names: list[GateName | str] = Field(default_factory=list)
    status: ChangeSetStatus = ChangeSetStatus.PROPOSED
    approved_by: str | None = None
    base_snapshot_id: str | None = None
    result_snapshot_id: str | None = None
    approved_at: datetime | None = None
    applied_at: datetime | None = None
    rolled_back_at: datetime | None = None
    rolled_back_by: str | None = None
    rollback_reason: str | None = None
    rollback_snapshot_id: str | None = None


class ChangeSetApplyRecoveryEvent(BaseModel):
    id: int
    event_type: str
    project_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    changeset_id: str | None = None
    created_at: datetime
    recovery_payload: dict[str, Any] = Field(default_factory=dict)


ChangeSetProposal.model_rebuild()
