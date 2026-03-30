from __future__ import annotations

from copy import deepcopy
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import CanonSnapshotORM, CharacterCardORM, ImmutableLogORM, OpenLoopCardORM, ProjectORM, RelationshipEdgeORM, RuleCardORM
from app.schemas.object_models import (
    CharacterCard,
    CreateCharacterCardRequest,
    CreateOpenLoopCardRequest,
    CreateRelationshipEdgeRequest,
    CreateRuleCardRequest,
    OpenLoopCard,
    RelationshipEdge,
    RuleCard,
)

TOrm = TypeVar("TOrm", CharacterCardORM, RuleCardORM, OpenLoopCardORM, RelationshipEdgeORM)


class ObjectService:
    def create_character(self, db: Session, request: CreateCharacterCardRequest) -> CharacterCard:
        self._ensure_project(db, request.project_id)
        self._ensure_working_object_create(request.bind_to_latest_canon)
        entity = CharacterCardORM(
            project_id=request.project_id,
            character_name=request.character_name,
            role_tags=request.role_tags,
            current_state=request.current_state,
            source_type=request.source_type,
            source_ref=request.source_ref,
            is_canon_bound=False,
            lifecycle_status="active",
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return CharacterCard.model_validate(entity)

    def list_characters(
        self,
        db: Session,
        project_id: str,
        snapshot_id: str | None = None,
        logical_object_id: str | None = None,
        current_only: bool = True,
        include_retired: bool = False,
    ) -> list[CharacterCard]:
        query = db.query(CharacterCardORM).filter(CharacterCardORM.project_id == project_id)
        if snapshot_id:
            query = query.filter(CharacterCardORM.snapshot_id == snapshot_id)
        if logical_object_id:
            query = query.filter(CharacterCardORM.logical_object_id == logical_object_id)
        if current_only:
            query = query.filter(CharacterCardORM.is_current_version.is_(True))
        if not include_retired:
            query = query.filter(CharacterCardORM.lifecycle_status != "retired")
        return [CharacterCard.model_validate(item) for item in query.order_by(CharacterCardORM.created_at.asc()).all()]

    def create_rule(self, db: Session, request: CreateRuleCardRequest) -> RuleCard:
        self._ensure_project(db, request.project_id)
        self._ensure_working_object_create(request.bind_to_latest_canon)
        entity = RuleCardORM(
            project_id=request.project_id,
            rule_name=request.rule_name,
            description=request.description,
            severity=request.severity,
            source_type=request.source_type,
            source_ref=request.source_ref,
            is_canon_bound=False,
            lifecycle_status="active",
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return RuleCard.model_validate(entity)

    def list_rules(
        self,
        db: Session,
        project_id: str,
        snapshot_id: str | None = None,
        logical_object_id: str | None = None,
        current_only: bool = True,
        include_retired: bool = False,
    ) -> list[RuleCard]:
        query = db.query(RuleCardORM).filter(RuleCardORM.project_id == project_id)
        if snapshot_id:
            query = query.filter(RuleCardORM.snapshot_id == snapshot_id)
        if logical_object_id:
            query = query.filter(RuleCardORM.logical_object_id == logical_object_id)
        if current_only:
            query = query.filter(RuleCardORM.is_current_version.is_(True))
        if not include_retired:
            query = query.filter(RuleCardORM.lifecycle_status != "retired")
        return [RuleCard.model_validate(item) for item in query.order_by(RuleCardORM.created_at.asc()).all()]

    def create_open_loop(self, db: Session, request: CreateOpenLoopCardRequest) -> OpenLoopCard:
        self._ensure_project(db, request.project_id)
        self._ensure_working_object_create(request.bind_to_latest_canon)
        entity = OpenLoopCardORM(
            project_id=request.project_id,
            loop_name=request.loop_name,
            status=request.status,
            source_type=request.source_type,
            source_ref=request.source_ref,
            is_canon_bound=False,
            lifecycle_status="active",
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return OpenLoopCard.model_validate(entity)

    def list_open_loops(
        self,
        db: Session,
        project_id: str,
        snapshot_id: str | None = None,
        logical_object_id: str | None = None,
        current_only: bool = True,
        include_retired: bool = False,
    ) -> list[OpenLoopCard]:
        query = db.query(OpenLoopCardORM).filter(OpenLoopCardORM.project_id == project_id)
        if snapshot_id:
            query = query.filter(OpenLoopCardORM.snapshot_id == snapshot_id)
        if logical_object_id:
            query = query.filter(OpenLoopCardORM.logical_object_id == logical_object_id)
        if current_only:
            query = query.filter(OpenLoopCardORM.is_current_version.is_(True))
        if not include_retired:
            query = query.filter(OpenLoopCardORM.lifecycle_status != "retired")
        return [OpenLoopCard.model_validate(item) for item in query.order_by(OpenLoopCardORM.created_at.asc()).all()]

    def create_relationship(self, db: Session, request: CreateRelationshipEdgeRequest) -> RelationshipEdge:
        self._ensure_project(db, request.project_id)
        self._ensure_working_object_create(request.bind_to_latest_canon)
        source_logical_id = self.resolve_character_logical_id(db, request.project_id, request.source_character_id)
        target_logical_id = self.resolve_character_logical_id(db, request.project_id, request.target_character_id)
        entity = RelationshipEdgeORM(
            project_id=request.project_id,
            source_character_id=source_logical_id,
            target_character_id=target_logical_id,
            relation_type=request.relation_type,
            relation_stage=request.relation_stage,
            relation_metadata=request.metadata,
            source_type=request.source_type,
            source_ref=request.source_ref,
            is_canon_bound=False,
            lifecycle_status="active",
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return self._relationship_schema(entity)

    def list_relationships(
        self,
        db: Session,
        project_id: str,
        snapshot_id: str | None = None,
        logical_object_id: str | None = None,
        current_only: bool = True,
        include_retired: bool = False,
    ) -> list[RelationshipEdge]:
        query = db.query(RelationshipEdgeORM).filter(RelationshipEdgeORM.project_id == project_id)
        if snapshot_id:
            query = query.filter(RelationshipEdgeORM.snapshot_id == snapshot_id)
        if logical_object_id:
            query = query.filter(RelationshipEdgeORM.logical_object_id == logical_object_id)
        if current_only:
            query = query.filter(RelationshipEdgeORM.is_current_version.is_(True))
        if not include_retired:
            query = query.filter(RelationshipEdgeORM.lifecycle_status != "retired")
        return [self._relationship_schema(item) for item in query.order_by(RelationshipEdgeORM.created_at.asc()).all()]

    def get_current_character(self, db: Session, project_id: str, logical_object_id: str) -> CharacterCardORM:
        return self._get_current_object(db, CharacterCardORM, project_id, logical_object_id)

    def get_current_rule(self, db: Session, project_id: str, logical_object_id: str) -> RuleCardORM:
        return self._get_current_object(db, RuleCardORM, project_id, logical_object_id)

    def get_current_open_loop(self, db: Session, project_id: str, logical_object_id: str) -> OpenLoopCardORM:
        return self._get_current_object(db, OpenLoopCardORM, project_id, logical_object_id)

    def get_current_relationship(self, db: Session, project_id: str, logical_object_id: str) -> RelationshipEdgeORM:
        return self._get_current_object(db, RelationshipEdgeORM, project_id, logical_object_id)

    def build_current_canon_payload(self, db: Session, project_id: str, timeline_events: list[dict] | None = None) -> dict[str, list[dict[str, Any]]]:
        return {
            "rule_cards": [self._rule_payload(item) for item in self._current_objects(db, RuleCardORM, project_id)],
            "character_cards": [self._character_payload(item) for item in self._current_objects(db, CharacterCardORM, project_id)],
            "relationship_edges": [self._relationship_payload(item) for item in self._current_objects(db, RelationshipEdgeORM, project_id)],
            "open_loops": [self._open_loop_payload(item) for item in self._current_objects(db, OpenLoopCardORM, project_id)],
            "timeline_events": deepcopy(timeline_events or []),
        }

    def create_snapshot_from_current_objects(
        self,
        db: Session,
        project_id: str,
        title: str,
        timeline_events: list[dict] | None = None,
    ) -> CanonSnapshotORM:
        latest = self._get_latest_snapshot(db, project_id)
        payload = self.build_current_canon_payload(
            db=db,
            project_id=project_id,
            timeline_events=timeline_events if timeline_events is not None else latest.timeline_events,
        )
        snapshot = CanonSnapshotORM(
            project_id=project_id,
            title=title,
            version_no=latest.version_no + 1,
            rule_cards=payload["rule_cards"],
            character_cards=payload["character_cards"],
            relationship_edges=payload["relationship_edges"],
            open_loops=payload["open_loops"],
            timeline_events=payload["timeline_events"],
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    def resolve_character_logical_id(self, db: Session, project_id: str, raw_id: str) -> str:
        current = (
            db.query(CharacterCardORM)
            .filter(
                CharacterCardORM.project_id == project_id,
                CharacterCardORM.logical_object_id == raw_id,
                CharacterCardORM.is_current_version.is_(True),
                CharacterCardORM.lifecycle_status == "active",
            )
            .first()
        )
        if current is not None:
            return current.logical_object_id
        by_row_id = db.get(CharacterCardORM, raw_id)
        if (
            by_row_id is not None
            and by_row_id.project_id == project_id
            and by_row_id.is_current_version
            and by_row_id.lifecycle_status == "active"
        ):
            return by_row_id.logical_object_id
        raise NotFoundError("角色不存在、已失效，或不是当前可用版本，无法建立关系")

    def _ensure_project(self, db: Session, project_id: str) -> None:
        if db.get(ProjectORM, project_id) is None:
            raise NotFoundError("项目不存在")

    def _ensure_working_object_create(self, bind_to_latest_canon: bool) -> None:
        if bind_to_latest_canon:
            raise ConflictError("对象创建不能直接写入 Canon。请先创建工作对象，或通过 ChangeSet 提议 Canon 变更。")

    def _get_latest_snapshot(self, db: Session, project_id: str) -> CanonSnapshotORM:
        snapshot = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        if snapshot is None:
            raise ConflictError("当前项目尚未初始化 Canon Snapshot，无法绑定对象到正史")
        return snapshot

    def _current_objects(self, db: Session, orm_class: type[TOrm], project_id: str) -> list[TOrm]:
        return (
            db.query(orm_class)
            .filter(
                orm_class.project_id == project_id,
                orm_class.is_current_version.is_(True),
                orm_class.is_canon_bound.is_(True),
                orm_class.lifecycle_status == "active",
            )
            .order_by(orm_class.created_at.asc())
            .all()
        )

    def _get_current_object(self, db: Session, orm_class: type[TOrm], project_id: str, logical_object_id: str) -> TOrm:
        entity = (
            db.query(orm_class)
            .filter(
                orm_class.project_id == project_id,
                orm_class.logical_object_id == logical_object_id,
                orm_class.is_current_version.is_(True),
            )
            .first()
        )
        if entity is None:
            raise NotFoundError(f"对象不存在或当前版本不可用: {logical_object_id}")
        return entity

    def _log_event(self, db: Session, project_id: str, event_type: str, payload: dict[str, Any]) -> None:
        db.add(ImmutableLogORM(event_type=event_type, project_id=project_id, event_payload=payload))

    def _character_payload(self, entity: CharacterCardORM) -> dict[str, Any]:
        return {
            "id": entity.id,
            "logical_object_id": entity.logical_object_id,
            "object_type": "character_card",
            "character_name": entity.character_name,
            "role_tags": entity.role_tags,
            "current_state": entity.current_state,
            "lifecycle_status": entity.lifecycle_status,
            "version_no": entity.version_no,
        }

    def _rule_payload(self, entity: RuleCardORM) -> dict[str, Any]:
        return {
            "id": entity.id,
            "logical_object_id": entity.logical_object_id,
            "object_type": "rule_card",
            "rule_name": entity.rule_name,
            "description": entity.description,
            "severity": entity.severity,
            "lifecycle_status": entity.lifecycle_status,
            "version_no": entity.version_no,
        }

    def _open_loop_payload(self, entity: OpenLoopCardORM) -> dict[str, Any]:
        return {
            "id": entity.id,
            "logical_object_id": entity.logical_object_id,
            "object_type": "open_loop_card",
            "loop_name": entity.loop_name,
            "status": entity.status,
            "source_ref": entity.source_ref,
            "lifecycle_status": entity.lifecycle_status,
            "version_no": entity.version_no,
        }

    def _relationship_payload(self, entity: RelationshipEdgeORM) -> dict[str, Any]:
        return {
            "id": entity.id,
            "logical_object_id": entity.logical_object_id,
            "object_type": "relationship_edge",
            "source_character_id": entity.source_character_id,
            "target_character_id": entity.target_character_id,
            "relation_type": entity.relation_type,
            "relation_stage": entity.relation_stage,
            "metadata": entity.relation_metadata,
            "lifecycle_status": entity.lifecycle_status,
            "version_no": entity.version_no,
        }

    def _relationship_schema(self, entity: RelationshipEdgeORM) -> RelationshipEdge:
        return RelationshipEdge.model_validate({**entity.__dict__, "metadata": entity.relation_metadata})


object_service = ObjectService()
