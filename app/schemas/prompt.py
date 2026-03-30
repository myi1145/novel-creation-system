from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PromptTemplate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_key: str
    template_version: int
    agent_type: str
    action_name: str
    provider_scope: str
    scope_type: str
    scope_key: str
    status: str
    is_active: bool
    system_template: str
    user_template: str
    output_contract: dict[str, Any] = Field(default_factory=dict)
    template_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CreatePromptTemplateRequest(BaseModel):
    template_key: str
    agent_type: str
    action_name: str
    provider_scope: str = Field(default="all")
    scope_type: str = Field(default="global")
    scope_key: str = Field(default="__global__")
    system_template: str
    user_template: str
    output_contract: dict[str, Any] = Field(default_factory=dict)
    template_metadata: dict[str, Any] = Field(default_factory=dict)
    activate_now: bool = True


class ActivatePromptTemplateRequest(BaseModel):
    activate_now: bool = True


class PromptResolvePreviewRequest(BaseModel):
    project_id: str | None = None
    genre_id: str | None = None
    agent_type: str
    action_name: str
    provider_scope: str | None = None
    render_context: dict[str, Any] = Field(default_factory=dict)


class PromptResolutionPreview(BaseModel):
    template_id: str
    template_key: str
    template_version: int
    scope_type: str
    scope_key: str
    provider_scope: str
    system_prompt: str
    user_prompt: str
    output_contract: dict[str, Any] = Field(default_factory=dict)
