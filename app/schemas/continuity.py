from datetime import datetime

from pydantic import BaseModel, Field


class RecentChapterContext(BaseModel):
    published_chapter_id: str
    chapter_no: int
    title: str
    summary: str
    state_summary: str
    next_chapter_seed: str | None = None
    unresolved_open_loops: list[str] = Field(default_factory=list)
    carry_over_constraints: list[str] = Field(default_factory=list)


class CanonContextSummary(BaseModel):
    snapshot_id: str
    version_no: int
    summary: str
    character_count: int = 0
    rule_count: int = 0
    relationship_count: int = 0
    open_loop_count: int = 0
    published_chapter_count: int = 0
    timeline_tail: list[str] = Field(default_factory=list)


class ResolveContinuityPackRequest(BaseModel):
    project_id: str
    target_chapter_no: int
    workflow_run_id: str | None = None
    trace_id: str | None = None
    previous_chapter_summary: str | None = None
    unresolved_open_loops: list[str] = Field(default_factory=list)
    recent_limit: int = Field(default=3, ge=1, le=5)
    force_refresh: bool = False


class ContinuityPack(BaseModel):
    project_id: str
    target_chapter_no: int
    workflow_run_id: str | None = None
    trace_id: str | None = None
    source_snapshot_id: str | None = None
    source_published_chapter_id: str | None = None
    genre_id: str | None = None
    genre_name: str | None = None
    genre_rulepack_summary: str | None = None
    previous_chapter_summary: str | None = None
    next_chapter_seed: str | None = None
    unresolved_open_loops: list[str] = Field(default_factory=list)
    carry_over_constraints: list[str] = Field(default_factory=list)
    recent_chapter_summaries: list[RecentChapterContext] = Field(default_factory=list)
    canon_summary: CanonContextSummary | None = None
    continuity_summary: str
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
