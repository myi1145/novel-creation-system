from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import IdentifiedModel


class CreateCharacterCardRequest(BaseModel):
    project_id: str
    character_name: str
    role_tags: list[str] = Field(default_factory=list)
    current_state: dict[str, Any] = Field(default_factory=dict)
    bind_to_latest_canon: bool = False
    source_type: str = "human_seed"
    source_ref: str | None = None


class CharacterCard(IdentifiedModel):
    object_type: Literal["character_card"] = "character_card"
    logical_object_id: str
    predecessor_version_id: str | None = None
    project_id: str
    snapshot_id: str | None = None
    version_no: int = 1
    is_current_version: bool = True
    superseded_at: datetime | None = None
    retired_at: datetime | None = None
    lifecycle_status: str = "active"
    change_reason: str | None = None
    character_name: str
    role_tags: list[str] = Field(default_factory=list)
    current_state: dict[str, Any] = Field(default_factory=dict)
    source_type: str = "human_seed"
    source_ref: str | None = None
    is_canon_bound: bool = False


class UpdateCharacterCardRequest(BaseModel):
    project_id: str
    character_name: str | None = None
    role_tags: list[str] | None = None
    current_state: dict[str, Any] | None = None
    rationale: str
    source_ref: str
    bind_to_canon: bool | None = None


class CreateRuleCardRequest(BaseModel):
    project_id: str
    rule_name: str
    description: str
    severity: str = "hard"
    bind_to_latest_canon: bool = False
    source_type: str = "human_seed"
    source_ref: str | None = None


class RuleCard(IdentifiedModel):
    object_type: Literal["rule_card"] = "rule_card"
    logical_object_id: str
    predecessor_version_id: str | None = None
    project_id: str
    snapshot_id: str | None = None
    version_no: int = 1
    is_current_version: bool = True
    superseded_at: datetime | None = None
    retired_at: datetime | None = None
    lifecycle_status: str = "active"
    change_reason: str | None = None
    rule_name: str
    description: str
    severity: str = "hard"
    source_type: str = "human_seed"
    source_ref: str | None = None
    is_canon_bound: bool = False


class UpdateRuleCardRequest(BaseModel):
    project_id: str
    rule_name: str | None = None
    description: str | None = None
    severity: str | None = None
    rationale: str
    source_ref: str
    bind_to_canon: bool | None = None


class CreateOpenLoopCardRequest(BaseModel):
    project_id: str
    loop_name: str
    status: str = "open"
    bind_to_latest_canon: bool = False
    source_type: str = "human_seed"
    source_ref: str | None = None


class OpenLoopCard(IdentifiedModel):
    object_type: Literal["open_loop_card"] = "open_loop_card"
    logical_object_id: str
    predecessor_version_id: str | None = None
    project_id: str
    snapshot_id: str | None = None
    version_no: int = 1
    is_current_version: bool = True
    superseded_at: datetime | None = None
    retired_at: datetime | None = None
    lifecycle_status: str = "active"
    change_reason: str | None = None
    loop_name: str
    status: str = "open"
    source_type: str = "human_seed"
    source_ref: str | None = None
    is_canon_bound: bool = False


class UpdateOpenLoopCardRequest(BaseModel):
    project_id: str
    loop_name: str | None = None
    status: str | None = None
    rationale: str
    source_ref: str
    bind_to_canon: bool | None = None


class CreateRelationshipEdgeRequest(BaseModel):
    project_id: str
    source_character_id: str
    target_character_id: str
    relation_type: str
    relation_stage: str = "established"
    metadata: dict[str, Any] = Field(default_factory=dict)
    bind_to_latest_canon: bool = False
    source_type: str = "human_seed"
    source_ref: str | None = None


class RelationshipEdge(IdentifiedModel):
    object_type: Literal["relationship_edge"] = "relationship_edge"
    logical_object_id: str
    predecessor_version_id: str | None = None
    project_id: str
    snapshot_id: str | None = None
    version_no: int = 1
    is_current_version: bool = True
    superseded_at: datetime | None = None
    retired_at: datetime | None = None
    lifecycle_status: str = "active"
    change_reason: str | None = None
    source_character_id: str
    target_character_id: str
    relation_type: str
    relation_stage: str = "established"
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_type: str = "human_seed"
    source_ref: str | None = None
    is_canon_bound: bool = False


class UpdateRelationshipEdgeRequest(BaseModel):
    project_id: str
    relation_type: str | None = None
    relation_stage: str | None = None
    metadata: dict[str, Any] | None = None
    rationale: str
    source_ref: str
    bind_to_canon: bool | None = None


class RestoreObjectVersionRequest(BaseModel):
    project_id: str
    rationale: str
    source_ref: str
    restore_from_version_id: str | None = None
    restore_from_version_no: int | None = None
    bind_to_canon: bool | None = None

    @model_validator(mode="after")
    def validate_restore_selector(self) -> "RestoreObjectVersionRequest":
        selectors = [self.restore_from_version_id is not None, self.restore_from_version_no is not None]
        if sum(selectors) != 1:
            raise ValueError("restore_from_version_id 和 restore_from_version_no 必须且只能提供一个")
        return self


class RetireObjectRequest(BaseModel):
    project_id: str
    rationale: str
    source_ref: str
    retire_reason: str | None = None
