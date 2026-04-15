from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def generate_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_name: Mapped[str] = mapped_column(String(100), nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=False)
    genre_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_chapter_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)






class StoryPlanningORM(Base):
    __tablename__ = "story_plannings"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_story_plannings_project"),
        CheckConstraint("planning_status in ('draft', 'confirmed')", name="ck_story_plannings_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    worldview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    main_outline: Mapped[str] = mapped_column(Text, default="", nullable=False)
    volume_plan: Mapped[str] = mapped_column(Text, default="", nullable=False)
    core_seed_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    planning_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    last_update_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)




class StoryDirectoryORM(Base):
    __tablename__ = "story_directories"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_story_directories_project"),
        CheckConstraint("directory_status in ('draft', 'confirmed')", name="ck_story_directories_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    story_planning_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("story_plannings.id", ondelete="SET NULL"), nullable=True)
    directory_title: Mapped[str] = mapped_column(String(200), default="全书章节目录", nullable=False)
    directory_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    directory_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    chapter_items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    last_update_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

class WorkflowRunORM(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    chapter_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False)
    current_step: Mapped[str] = mapped_column(String(50), default="chapter_goal_input", nullable=False)
    run_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class GenreProfileORM(Base):
    __tablename__ = "genre_profiles"

    genre_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    genre_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    world: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    narrative: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    style: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class CanonSnapshotORM(Base):
    __tablename__ = "canon_snapshots"
    __table_args__ = (
        UniqueConstraint("project_id", "version_no", name="uq_canon_snapshots_project_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rule_cards: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    character_cards: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    relationship_edges: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    open_loops: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    timeline_events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class ImmutableLogORM(Base):
    __tablename__ = "immutable_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    event_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class PromptTemplateORM(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint(
            "template_key",
            "template_version",
            "provider_scope",
            "scope_type",
            "scope_key",
            name="uq_prompt_template_version_scope",
        ),
        Index(
            "ix_prompt_template_active_unique",
            "template_key",
            "provider_scope",
            "scope_type",
            "scope_key",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    template_key: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    action_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    provider_scope: Mapped[str] = mapped_column(String(50), default="all", index=True, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), default="global", index=True, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(100), default="__global__", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system_template: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_contract: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    template_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class AgentCallLogORM(Base):
    __tablename__ = "agent_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    agent_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    action_name: Mapped[str] = mapped_column(String(50), nullable=False)
    configured_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    active_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("prompt_templates.id", ondelete="SET NULL"), index=True, nullable=True)
    prompt_template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_scope_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    prompt_scope_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_provider_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    call_status: Mapped[str] = mapped_column(String(30), index=True, default="success", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    circuit_state_at_call: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rate_limited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class ProviderCircuitStateORM(Base):
    __tablename__ = "provider_circuit_states"

    provider_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    current_state: Mapped[str] = mapped_column(String(30), default="closed", nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    half_open_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class CharacterCardORM(Base):
    __tablename__ = "character_cards"
    __table_args__ = (
        UniqueConstraint("project_id", "logical_object_id", "version_no", name="uq_character_versions"),
        Index("ix_character_current_unique", "project_id", "logical_object_id", unique=True, sqlite_where=text("is_current_version = 1")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    logical_object_id: Mapped[str] = mapped_column(String(36), index=True, default=generate_id, nullable=False)
    predecessor_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("character_cards.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="SET NULL"), index=True, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current_version: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    current_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="human_seed", nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_canon_bound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class RuleCardORM(Base):
    __tablename__ = "rule_cards"
    __table_args__ = (
        UniqueConstraint("project_id", "logical_object_id", "version_no", name="uq_rule_versions"),
        Index("ix_rule_current_unique", "project_id", "logical_object_id", unique=True, sqlite_where=text("is_current_version = 1")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    logical_object_id: Mapped[str] = mapped_column(String(36), index=True, default=generate_id, nullable=False)
    predecessor_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("rule_cards.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="SET NULL"), index=True, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current_version: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="hard", nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="human_seed", nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_canon_bound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class OpenLoopCardORM(Base):
    __tablename__ = "open_loop_cards"
    __table_args__ = (
        UniqueConstraint("project_id", "logical_object_id", "version_no", name="uq_open_loop_versions"),
        Index("ix_open_loop_current_unique", "project_id", "logical_object_id", unique=True, sqlite_where=text("is_current_version = 1")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    logical_object_id: Mapped[str] = mapped_column(String(36), index=True, default=generate_id, nullable=False)
    predecessor_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("open_loop_cards.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="SET NULL"), index=True, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current_version: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    loop_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="human_seed", nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_canon_bound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class RelationshipEdgeORM(Base):
    __tablename__ = "relationship_edges"
    __table_args__ = (
        UniqueConstraint("project_id", "logical_object_id", "version_no", name="uq_relationship_versions"),
        Index("ix_relationship_current_unique", "project_id", "logical_object_id", unique=True, sqlite_where=text("is_current_version = 1")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    logical_object_id: Mapped[str] = mapped_column(String(36), index=True, default=generate_id, nullable=False)
    predecessor_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("relationship_edges.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="SET NULL"), index=True, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current_version: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_character_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_character_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    relation_stage: Mapped[str] = mapped_column(String(50), default="established", nullable=False)
    relation_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="human_seed", nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_canon_bound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class ChapterGoalORM(Base):
    __tablename__ = "chapter_goals"
    __table_args__ = (
        UniqueConstraint("project_id", "chapter_no", name="uq_chapter_goal_project_chapter"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    current_volume_goal: Mapped[str] = mapped_column(Text, nullable=False)
    structure_goal: Mapped[str] = mapped_column(Text, nullable=False)
    conflict_level: Mapped[str] = mapped_column(String(50), nullable=False)
    info_reveal_level: Mapped[str] = mapped_column(String(50), nullable=False)
    required_elements: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    banned_elements: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class ChapterBlueprintORM(Base):
    __tablename__ = "chapter_blueprints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    chapter_goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_goals.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    title_hint: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    advances: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    risks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class SceneCardORM(Base):
    __tablename__ = "scene_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    blueprint_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_blueprints.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    scene_goal: Mapped[str] = mapped_column(Text, nullable=False)
    participating_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(50), nullable=False)
    emotional_curve: Mapped[str] = mapped_column(String(50), nullable=False)
    information_delta: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class ChapterDraftORM(Base):
    __tablename__ = "chapter_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    blueprint_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_blueprints.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    draft_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class ChapterStateTransitionORM(Base):
    __tablename__ = "chapter_state_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_drafts.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    transition_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class GateReviewORM(Base):
    __tablename__ = "gate_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_drafts.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    gate_name: Mapped[str] = mapped_column(String(50), nullable=False)
    pass_status: Mapped[str] = mapped_column(String(30), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    highest_severity: Mapped[str] = mapped_column(String(10), default="S0", nullable=False)
    recommended_route: Mapped[str] = mapped_column(String(30), default="pass", nullable=False)
    can_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    issues: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class ChangeSetORM(Base):
    __tablename__ = "changesets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    source_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    patch_operations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    required_gate_names: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="SET NULL"), nullable=True)
    result_snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class PublishedChapterORM(Base):
    __tablename__ = "published_chapters"
    __table_args__ = (
        UniqueConstraint("project_id", "chapter_no", name="uq_published_chapters_project_chapter_no"),
        UniqueConstraint("draft_id", name="uq_published_chapters_draft_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_drafts.id", ondelete="CASCADE"), index=True, nullable=False)
    blueprint_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_blueprints.id", ondelete="CASCADE"), index=True, nullable=False)
    chapter_goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_goals.id", ondelete="CASCADE"), index=True, nullable=False)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="published", nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="RESTRICT"), index=True, nullable=False)
    changeset_id: Mapped[str] = mapped_column(String(36), ForeignKey("changesets.id", ondelete="RESTRICT"), index=True, nullable=False)
    publish_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class PublishRecordORM(Base):
    __tablename__ = "publish_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    published_chapter_id: Mapped[str] = mapped_column(String(36), ForeignKey("published_chapters.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapter_drafts.id", ondelete="CASCADE"), index=True, nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("canon_snapshots.id", ondelete="RESTRICT"), index=True, nullable=False)
    changeset_id: Mapped[str] = mapped_column(String(36), ForeignKey("changesets.id", ondelete="RESTRICT"), index=True, nullable=False)
    publish_gate_review_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("gate_reviews.id", ondelete="SET NULL"), nullable=True)
    published_by: Mapped[str] = mapped_column(String(100), nullable=False)
    publish_status: Mapped[str] = mapped_column(String(30), default="published", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class StructuredCharacterCardORM(Base):
    __tablename__ = "structured_character_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    role_position: Mapped[str] = mapped_column(Text, nullable=False)
    profile: Mapped[str] = mapped_column(Text, nullable=False)
    personality_keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    relationship_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_status: Mapped[str] = mapped_column(Text, default="", nullable=False)
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_update_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    is_canon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class TerminologyCardORM(Base):
    __tablename__ = "terminology_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    term: Mapped[str] = mapped_column(String(120), nullable=False)
    term_type: Mapped[str] = mapped_column(String(120), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    usage_rules: Mapped[str] = mapped_column(Text, default="", nullable=False)
    examples: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_update_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    is_canon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class StructuredFactionCardORM(Base):
    __tablename__ = "structured_faction_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    faction_type: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    core_members: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    territory: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stance: Mapped[str] = mapped_column(Text, default="", nullable=False)
    goals: Mapped[str] = mapped_column(Text, default="", nullable=False)
    relationship_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_status: Mapped[str] = mapped_column(Text, default="", nullable=False)
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_update_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    is_canon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class StructuredLocationCardORM(Base):
    __tablename__ = "structured_location_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    location_type: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, default="", nullable=False)
    key_features: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    related_factions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    narrative_role: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_status: Mapped[str] = mapped_column(Text, default="", nullable=False)
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_update_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    is_canon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
