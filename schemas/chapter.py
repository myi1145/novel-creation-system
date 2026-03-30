from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import ChapterStatus
from app.schemas.common import IdentifiedModel
from app.schemas.derived_update import DerivedUpdateBatchResult


class CreateChapterGoalRequest(BaseModel):
    project_id: str
    chapter_no: int
    current_volume_goal: str
    previous_chapter_summary: str | None = None
    unresolved_open_loops: list[str] = Field(default_factory=list)
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ChapterGoal(IdentifiedModel):
    project_id: str
    chapter_no: int
    workflow_run_id: str | None = None
    trace_id: str | None = None
    current_volume_goal: str
    structure_goal: str
    conflict_level: str
    info_reveal_level: str
    required_elements: list[str] = Field(default_factory=list)
    banned_elements: list[str] = Field(default_factory=list)


class GenerateBlueprintsRequest(BaseModel):
    project_id: str
    chapter_goal_id: str
    candidate_count: int = Field(default=3, ge=1, le=7)
    workflow_run_id: str | None = None
    trace_id: str | None = None


class SelectBlueprintRequest(BaseModel):
    project_id: str
    blueprint_id: str
    selected_by: str
    selection_reason: str | None = None
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ChapterBlueprint(IdentifiedModel):
    project_id: str
    chapter_goal_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    title_hint: str
    summary: str
    advances: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    selected: bool = False


class DecomposeScenesRequest(BaseModel):
    project_id: str
    blueprint_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None


class SceneCard(IdentifiedModel):
    project_id: str
    blueprint_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    scene_goal: str
    participating_entities: list[str] = Field(default_factory=list)
    conflict_type: str
    emotional_curve: str
    information_delta: str


class GenerateDraftRequest(BaseModel):
    project_id: str
    blueprint_id: str
    scene_ids: list[str] = Field(default_factory=list)
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ReviseDraftRequest(BaseModel):
    project_id: str
    draft_id: str
    revision_instruction: str | None = None
    source_gate_review_ids: list[str] = Field(default_factory=list)
    revised_by: str | None = None
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ChapterDraft(IdentifiedModel):
    project_id: str
    blueprint_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    content: str
    status: ChapterStatus = ChapterStatus.DRAFTING
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_draft_id: str | None = None
    revision_no: int = 1
    revision_reason: str | None = None
    source_gate_review_ids: list[str] = Field(default_factory=list)


class ChapterStateTransition(IdentifiedModel):
    project_id: str
    draft_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    from_status: ChapterStatus | None = None
    to_status: ChapterStatus
    trigger_type: str
    trigger_ref: str | None = None
    reason: str | None = None
    transition_metadata: dict[str, Any] = Field(default_factory=dict)


class GenerateChapterSummaryRequest(BaseModel):
    project_id: str
    published_chapter_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    force_regenerate: bool = False


class ChapterSummary(BaseModel):
    project_id: str
    published_chapter_id: str
    draft_id: str
    blueprint_id: str
    chapter_goal_id: str
    chapter_no: int
    workflow_run_id: str | None = None
    trace_id: str | None = None
    summary: str
    state_summary: str
    key_plot_points: list[str] = Field(default_factory=list)
    canon_updates: list[str] = Field(default_factory=list)
    unresolved_open_loops: list[str] = Field(default_factory=list)
    carry_over_constraints: list[str] = Field(default_factory=list)
    next_chapter_seed: str
    generated_by: str
    generated_at: datetime


class PublishDraftRequest(BaseModel):
    project_id: str
    draft_id: str
    published_by: str
    publish_title: str | None = None
    notes: str | None = None
    workflow_run_id: str | None = None
    trace_id: str | None = None


class PublishedChapter(IdentifiedModel):
    project_id: str
    draft_id: str
    blueprint_id: str
    chapter_goal_id: str
    chapter_no: int
    workflow_run_id: str | None = None
    trace_id: str | None = None
    title: str
    content: str
    status: ChapterStatus = ChapterStatus.PUBLISHED
    snapshot_id: str
    changeset_id: str
    publish_metadata: dict[str, Any] = Field(default_factory=dict)
    published_at: datetime


class PublishRecord(IdentifiedModel):
    project_id: str
    published_chapter_id: str
    draft_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    snapshot_id: str
    changeset_id: str
    publish_gate_review_id: str | None = None
    published_by: str
    publish_status: str
    notes: str | None = None


class PublishResult(BaseModel):
    published_chapter: PublishedChapter
    publish_record: PublishRecord
    chapter_summary: ChapterSummary | None = None
    derived_update_result: DerivedUpdateBatchResult | None = None
