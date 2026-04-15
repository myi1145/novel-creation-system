from datetime import datetime
from typing import Literal

from pydantic import BaseModel


PlanningStatus = Literal["draft", "confirmed"]


class StoryPlanningUpsert(BaseModel):
    worldview: str = ""
    main_outline: str = ""
    volume_plan: str = ""
    core_seed_summary: str = ""
    planning_status: PlanningStatus = "draft"


class StoryPlanningResponse(BaseModel):
    id: str
    project_id: str
    worldview: str
    main_outline: str
    volume_plan: str
    core_seed_summary: str
    planning_status: PlanningStatus
    last_update_source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryPlanningGenerateRequest(BaseModel):
    target_chapter_count: int | None = None
    tone: str | None = None


class StoryPlanningGenerateData(BaseModel):
    worldview: str
    main_outline: str
    volume_plan: str
    core_seed_summary: str


class StoryPlanningGenerateResponse(BaseModel):
    project_id: str
    generated: bool
    data: StoryPlanningGenerateData
    message: str
