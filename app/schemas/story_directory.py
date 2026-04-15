from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


DirectoryStatus = Literal["draft", "confirmed"]


class StoryDirectoryChapterItem(BaseModel):
    chapter_no: int
    chapter_title: str
    chapter_role: str = ""
    chapter_goal: str = ""
    stage_label: str = ""
    required_entities: list[str] = Field(default_factory=list)
    required_seed_points: list[str] = Field(default_factory=list)
    foreshadow_constraints: list[str] = Field(default_factory=list)


class StoryDirectoryUpsert(BaseModel):
    story_planning_id: str | None = None
    directory_title: str = "全书章节目录"
    directory_summary: str = ""
    directory_status: DirectoryStatus = "draft"
    chapter_items: list[StoryDirectoryChapterItem] = Field(default_factory=list)


class StoryDirectoryResponse(BaseModel):
    id: str
    project_id: str
    story_planning_id: str | None
    directory_title: str
    directory_summary: str
    directory_status: DirectoryStatus
    chapter_items: list[StoryDirectoryChapterItem]
    last_update_source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryDirectoryGenerateRequest(BaseModel):
    target_chapter_count: int | None = None


class StoryDirectoryGenerateData(BaseModel):
    directory_title: str
    directory_summary: str
    directory_status: DirectoryStatus = "draft"
    chapter_items: list[StoryDirectoryChapterItem]


class StoryDirectoryGenerateResponse(BaseModel):
    project_id: str
    generated: bool
    data: StoryDirectoryGenerateData
    message: str
