from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import IdentifiedModel


class InitCanonSnapshotRequest(BaseModel):
    project_id: str
    title: str = "initial_snapshot"
    initial_rules: list[dict[str, Any]] = Field(default_factory=list)
    initial_characters: list[dict[str, Any]] = Field(default_factory=list)


class CanonSnapshot(IdentifiedModel):
    project_id: str
    title: str
    version_no: int = 1
    rule_cards: list[dict[str, Any]] = Field(default_factory=list)
    character_cards: list[dict[str, Any]] = Field(default_factory=list)
    relationship_edges: list[dict[str, Any]] = Field(default_factory=list)
    open_loops: list[dict[str, Any]] = Field(default_factory=list)
    timeline_events: list[dict[str, Any]] = Field(default_factory=list)
