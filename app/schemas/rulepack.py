from typing import Any

from pydantic import BaseModel, Field


class GateRulePackConstraints(BaseModel):
    banned_terms: list[str] = Field(default_factory=list)
    taboos: list[str] = Field(default_factory=list)
    preferred_conflict_types: list[str] = Field(default_factory=list)
    hook_style: str | None = None
    chapter_target_words: int | None = None


class GenreRulePackContext(BaseModel):
    genre_id: str | None = None
    genre_name: str = "default"
    base_genre: str | None = None
    tags: list[str] = Field(default_factory=list)
    world: dict[str, Any] = Field(default_factory=dict)
    narrative: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    rulepack_name: str = "base_rulepack_v1"
    rulepack_summary: str = "未加载题材规则包，使用通用创作底座。"
    prompt_context: dict[str, Any] = Field(default_factory=dict)
    gate_constraints: GateRulePackConstraints = Field(default_factory=GateRulePackConstraints)
