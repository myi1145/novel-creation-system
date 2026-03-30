from pydantic import BaseModel, Field

from app.schemas.common import IdentifiedModel


class CreateProjectRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=100)
    premise: str = Field(..., min_length=1)
    genre_id: str | None = None


class Project(IdentifiedModel):
    project_name: str
    premise: str
    genre_id: str | None = None
    current_chapter_no: int = 0
