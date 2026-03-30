from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import IdentifiedModel


class StructuredCreativeObject(IdentifiedModel):
    """最小结构优先协议壳层。

    不引入新表，不强行重构 ORM；仅把主链对象统一到可追踪的协议字段上，
    方便后续 workflow/gate/prompt/object schema 继续收口。
    """

    object_type: str
    schema_version: str = "v1"
    object_version: int = 1
    story_id: str | None = None
    lifecycle_stage: str = "working"
    source_type: str = "workflow"
    source_ref: str | None = None
    related_object_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    extension_fields: dict[str, Any] = Field(default_factory=dict)
