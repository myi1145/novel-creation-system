from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import ChapterStatus
from app.schemas.common import IdentifiedModel
from app.schemas.creative_object import StructuredCreativeObject
from app.schemas.derived_update import DerivedUpdateBatchResult


_STATUS_TO_STAGE = {
    ChapterStatus.DRAFTING: "drafting",
    ChapterStatus.REVIEWING: "review",
    ChapterStatus.REVIEW_FAILED: "revision_required",
    ChapterStatus.APPROVED: "review_passed",
    ChapterStatus.CHANGESET_PROPOSED: "changeset_proposed",
    ChapterStatus.CHANGESET_APPROVED: "changeset_approved",
    ChapterStatus.CANON_APPLIED: "canon_applied",
    ChapterStatus.PUBLISH_FAILED: "publish_failed",
    ChapterStatus.PUBLISHED: "published",
    ChapterStatus.FAILED: "failed",
}


def _dedupe_ids(values: list[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _metadata_extension_fields(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "next_chapter_seed",
        "continuity_summary",
        "revision_reason",
        "revision_no",
        "selected_by",
        "selection_reason",
        "scene_ids",
        "prompt_template_key",
        "prompt_template_version",
        "call_status",
        "fallback_used",
    ]
    return {key: metadata.get(key) for key in keys if metadata.get(key) is not None}


class CreateChapterGoalRequest(BaseModel):
    project_id: str
    chapter_no: int
    current_volume_goal: str
    previous_chapter_summary: str | None = None
    unresolved_open_loops: list[str] = Field(default_factory=list)
    workflow_run_id: str | None = None
    trace_id: str | None = None


class ChapterGoal(StructuredCreativeObject):
    object_type: str = "chapter_goal"
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

    @model_validator(mode="after")
    def normalize_protocol(self) -> "ChapterGoal":
        self.lifecycle_stage = "goal_defined"
        self.source_type = self.source_type or "workflow"
        self.source_ref = self.source_ref or self.workflow_run_id
        self.related_object_ids = _dedupe_ids(self.related_object_ids)
        return self


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


class ChapterBlueprint(StructuredCreativeObject):
    object_type: str = "chapter_blueprint"
    project_id: str
    chapter_goal_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    title_hint: str
    summary: str
    advances: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    selected: bool = False

    @model_validator(mode="after")
    def normalize_protocol(self) -> "ChapterBlueprint":
        self.lifecycle_stage = "selected" if self.selected else "candidate"
        self.source_type = self.source_type or "planner_agent"
        self.source_ref = self.source_ref or self.chapter_goal_id
        self.related_object_ids = _dedupe_ids([*self.related_object_ids, self.chapter_goal_id])
        if self.selected and "formal_blueprint" not in self.tags:
            self.tags.append("formal_blueprint")
        return self


class DecomposeScenesRequest(BaseModel):
    project_id: str
    blueprint_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None


class SceneCard(StructuredCreativeObject):
    object_type: str = "scene_card"
    project_id: str
    blueprint_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    scene_goal: str
    participating_entities: list[str] = Field(default_factory=list)
    conflict_type: str
    emotional_curve: str
    information_delta: str

    @model_validator(mode="after")
    def normalize_protocol(self) -> "SceneCard":
        self.lifecycle_stage = "scene_decomposed"
        self.source_type = self.source_type or "planner_agent"
        self.source_ref = self.source_ref or self.blueprint_id
        self.related_object_ids = _dedupe_ids([*self.related_object_ids, self.blueprint_id])
        return self


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


class ChapterDraft(StructuredCreativeObject):
    object_type: str = "chapter_draft"
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

    @model_validator(mode="after")
    def normalize_protocol(self) -> "ChapterDraft":
        self.lifecycle_stage = _STATUS_TO_STAGE.get(self.status, str(self.status))
        metadata = dict(self.metadata or {})
        self.source_type = metadata.get("source_type") or self.source_type or "writer_agent"
        self.source_ref = metadata.get("source_ref") or self.parent_draft_id or self.blueprint_id
        self.related_object_ids = _dedupe_ids(
            [
                *self.related_object_ids,
                self.blueprint_id,
                self.parent_draft_id,
                *list(self.source_gate_review_ids or []),
                *list(metadata.get("scene_ids") or []),
            ]
        )
        self.extension_fields = {**self.extension_fields, **_metadata_extension_fields(metadata)}
        if self.revision_no > 1 and "revision" not in self.tags:
            self.tags.append("revision")
        return self


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


class PublishedChapter(StructuredCreativeObject):
    object_type: str = "published_chapter"
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

    @model_validator(mode="after")
    def normalize_protocol(self) -> "PublishedChapter":
        self.lifecycle_stage = "published"
        self.source_type = self.source_type or "publish_service"
        self.source_ref = self.source_ref or self.changeset_id
        self.related_object_ids = _dedupe_ids(
            [*self.related_object_ids, self.draft_id, self.blueprint_id, self.chapter_goal_id, self.snapshot_id, self.changeset_id]
        )
        if self.publish_metadata:
            self.extension_fields = {
                **self.extension_fields,
                **{
                    key: self.publish_metadata.get(key)
                    for key in ["next_chapter_seed", "post_publish_stage", "derived_update_status"]
                    if self.publish_metadata.get(key) is not None
                },
            }
        return self


class PublishRecord(StructuredCreativeObject):
    object_type: str = "publish_record"
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

    @model_validator(mode="after")
    def normalize_protocol(self) -> "PublishRecord":
        self.lifecycle_stage = self.publish_status
        self.source_type = self.source_type or "publish_service"
        self.source_ref = self.source_ref or self.published_chapter_id
        self.related_object_ids = _dedupe_ids(
            [*self.related_object_ids, self.published_chapter_id, self.draft_id, self.snapshot_id, self.changeset_id, self.publish_gate_review_id]
        )
        return self


class PublishResult(BaseModel):
    success: bool = True
    publish_status: str = "published"
    idempotent_hit: bool = False
    published_chapter: PublishedChapter
    publish_record: PublishRecord
    chapter_summary: ChapterSummary | None = None
    derived_update_result: DerivedUpdateBatchResult | None = None
