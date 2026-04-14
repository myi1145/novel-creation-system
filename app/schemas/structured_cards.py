from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CharacterCardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    role_position: str = Field(..., min_length=1)
    profile: str = Field(..., min_length=1)
    personality_keywords: list[str] = Field(default_factory=list)
    relationship_notes: str = ""
    current_status: str = ""
    first_appearance_chapter: int | None = Field(default=None, ge=1)


class CharacterCardCreate(CharacterCardBase):
    pass


class CharacterCardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    role_position: str | None = Field(default=None, min_length=1)
    profile: str | None = Field(default=None, min_length=1)
    personality_keywords: list[str] | None = None
    relationship_notes: str | None = None
    current_status: str | None = None
    first_appearance_chapter: int | None = Field(default=None, ge=1)
    is_canon: bool | None = None


class CharacterCardResponse(CharacterCardBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    last_update_source: str
    is_canon: bool
    created_at: datetime
    updated_at: datetime


class TerminologyCardBase(BaseModel):
    term: str = Field(..., min_length=1, max_length=120)
    term_type: str = Field(..., min_length=1, max_length=120)
    definition: str = Field(..., min_length=1)
    usage_rules: str = ""
    examples: list[str] = Field(default_factory=list)
    first_appearance_chapter: int | None = Field(default=None, ge=1)


class TerminologyCardCreate(TerminologyCardBase):
    pass


class TerminologyCardUpdate(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=120)
    term_type: str | None = Field(default=None, min_length=1, max_length=120)
    definition: str | None = Field(default=None, min_length=1)
    usage_rules: str | None = None
    examples: list[str] | None = None
    first_appearance_chapter: int | None = Field(default=None, ge=1)
    is_canon: bool | None = None


class TerminologyCardResponse(TerminologyCardBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    last_update_source: str
    is_canon: bool
    created_at: datetime
    updated_at: datetime
