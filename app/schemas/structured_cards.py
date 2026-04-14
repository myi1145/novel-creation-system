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


class FactionCardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    faction_type: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1)
    core_members: list[str] = Field(default_factory=list)
    territory: str = ""
    stance: str = ""
    goals: str = ""
    relationship_notes: str = ""
    current_status: str = ""
    first_appearance_chapter: int | None = Field(default=None, ge=1)


class FactionCardCreate(FactionCardBase):
    pass


class FactionCardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    faction_type: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1)
    core_members: list[str] | None = None
    territory: str | None = None
    stance: str | None = None
    goals: str | None = None
    relationship_notes: str | None = None
    current_status: str | None = None
    first_appearance_chapter: int | None = Field(default=None, ge=1)
    is_canon: bool | None = None


class FactionCardResponse(FactionCardBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    last_update_source: str
    is_canon: bool
    created_at: datetime
    updated_at: datetime


class LocationCardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    location_type: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1)
    region: str = ""
    key_features: list[str] = Field(default_factory=list)
    related_factions: list[str] = Field(default_factory=list)
    narrative_role: str = ""
    current_status: str = ""
    first_appearance_chapter: int | None = Field(default=None, ge=1)


class LocationCardCreate(LocationCardBase):
    pass


class LocationCardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    location_type: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1)
    region: str | None = None
    key_features: list[str] | None = None
    related_factions: list[str] | None = None
    narrative_role: str | None = None
    current_status: str | None = None
    first_appearance_chapter: int | None = Field(default=None, ge=1)
    is_canon: bool | None = None


class LocationCardResponse(LocationCardBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    last_update_source: str
    is_canon: bool
    created_at: datetime
    updated_at: datetime


class StructuredCardsExportCards(BaseModel):
    characters: list[CharacterCardCreate] = Field(default_factory=list)
    terminologies: list[TerminologyCardCreate] = Field(default_factory=list)
    factions: list[FactionCardCreate] = Field(default_factory=list)
    locations: list[LocationCardCreate] = Field(default_factory=list)


class StructuredCardsExportResponse(BaseModel):
    project_id: str
    exported_at: datetime
    version: str = "1.0"
    cards: StructuredCardsExportCards


class StructuredCardImportError(BaseModel):
    row: int
    field: str
    message: str


class StructuredCardImportSkipped(BaseModel):
    row: int
    reason: str


class StructuredCardImportReport(BaseModel):
    card_type: str
    total_rows: int
    created_count: int
    skipped_count: int
    error_count: int
    errors: list[StructuredCardImportError] = Field(default_factory=list)
    skipped: list[StructuredCardImportSkipped] = Field(default_factory=list)


class StructuredCardsImportJsonPayload(BaseModel):
    cards: StructuredCardsExportCards


class StructuredCardsImportJsonRequest(BaseModel):
    payload: StructuredCardsImportJsonPayload | None = None
