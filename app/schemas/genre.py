from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoadGenreRequest(BaseModel):
    file_name: str


class GenreProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    genre_id: str
    genre_name: str
    base_genre: str | None = None
    tags: list[str] = Field(default_factory=list)
    world: dict[str, Any] = Field(default_factory=dict)
    narrative: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
