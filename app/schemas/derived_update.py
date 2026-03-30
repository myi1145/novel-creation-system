from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


DEFAULT_DERIVED_UPDATE_TASKS = [
    "refresh_chapter_summary",
    "refresh_next_chapter_seed",
    "refresh_vector_index",
    "refresh_graph_index",
    "refresh_search_index",
]


class DerivedUpdateTask(BaseModel):
    task_id: str
    task_type: str = "derived_update_task"
    task_name: str
    project_id: str
    published_chapter_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    source_type: str = "published_chapter"
    source_ref: str
    status: str
    blocking: bool = False
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    derived_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunDerivedUpdatesRequest(BaseModel):
    project_id: str
    published_chapter_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    task_names: list[str] = Field(default_factory=lambda: list(DEFAULT_DERIVED_UPDATE_TASKS))
    force_refresh_summary: bool = False
    force_rerun_tasks: bool = False


class DerivedUpdateBatchResult(BaseModel):
    project_id: str
    published_chapter_id: str
    workflow_run_id: str | None = None
    trace_id: str | None = None
    status: str
    tasks: list[DerivedUpdateTask] = Field(default_factory=list)
    generated_at: datetime
