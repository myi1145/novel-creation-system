from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import CanonSnapshotORM, CharacterCardORM, ImmutableLogORM, OpenLoopCardORM, ProjectORM, RelationshipEdgeORM, RuleCardORM
from app.schemas.canon import CanonSnapshot, InitCanonSnapshotRequest


class CanonService:
    def init_snapshot(self, db: Session, request: InitCanonSnapshotRequest) -> CanonSnapshot:
        project = db.get(ProjectORM, request.project_id)
        if project is None:
            raise NotFoundError("项目不存在，无法初始化 Canon Snapshot")

        latest = (
            db.query(CanonSnapshotORM)
            .filter(CanonSnapshotORM.project_id == request.project_id)
            .order_by(CanonSnapshotORM.version_no.desc())
            .first()
        )
        if latest is not None:
            raise ConflictError("当前版本仅允许初始化一次 Canon Snapshot。后续 Canon 变化请通过 ChangeSet。")

        snapshot = CanonSnapshotORM(
            project_id=request.project_id,
            title=request.title,
            version_no=1,
            rule_cards=request.initial_rules,
            character_cards=request.initial_characters,
            relationship_edges=[],
            open_loops=[],
            timeline_events=[],
        )
        db.add(snapshot)
        db.flush()

        self._materialize_seed_objects(db, snapshot=snapshot)
        db.add(
            ImmutableLogORM(
                event_type="canon_snapshot_initialized",
                project_id=request.project_id,
                event_payload={
                    "snapshot_id": snapshot.id,
                    "title": request.title,
                    "version_no": 1,
                },
            )
        )
        db.commit()
        db.refresh(snapshot)
        return CanonSnapshot.model_validate(snapshot)

    def list_snapshots(self, db: Session, project_id: str | None = None) -> list[CanonSnapshot]:
        query = db.query(CanonSnapshotORM)
        if project_id:
            query = query.filter(CanonSnapshotORM.project_id == project_id)
        items = query.order_by(CanonSnapshotORM.project_id.asc(), CanonSnapshotORM.version_no.desc()).all()
        return [CanonSnapshot.model_validate(item) for item in items]

    def _materialize_seed_objects(self, db: Session, snapshot: CanonSnapshotORM) -> None:
        for item in snapshot.character_cards:
            logical_object_id = item.get("logical_object_id") or item.get("id")
            payload = {
                "project_id": snapshot.project_id,
                "snapshot_id": snapshot.id,
                "logical_object_id": logical_object_id,
                "version_no": int(item.get("version_no", 1)),
                "character_name": item.get("character_name") or item.get("name") or "未命名角色",
                "role_tags": item.get("role_tags", []),
                "current_state": item.get("current_state", {}),
                "source_type": "canon_seed",
                "source_ref": snapshot.id,
                "is_canon_bound": True,
                "is_current_version": True,
                "lifecycle_status": item.get("lifecycle_status", "active"),
            }
            if item.get("id"):
                payload["id"] = item["id"]
            db.add(CharacterCardORM(**payload))
        for item in snapshot.rule_cards:
            logical_object_id = item.get("logical_object_id") or item.get("id")
            payload = {
                "project_id": snapshot.project_id,
                "snapshot_id": snapshot.id,
                "logical_object_id": logical_object_id,
                "version_no": int(item.get("version_no", 1)),
                "rule_name": item.get("rule_name") or item.get("name") or "未命名规则",
                "description": item.get("description", ""),
                "severity": item.get("severity", "hard"),
                "source_type": "canon_seed",
                "source_ref": snapshot.id,
                "is_canon_bound": True,
                "is_current_version": True,
                "lifecycle_status": item.get("lifecycle_status", "active"),
            }
            if item.get("id"):
                payload["id"] = item["id"]
            db.add(RuleCardORM(**payload))
        for item in snapshot.open_loops:
            logical_object_id = item.get("logical_object_id") or item.get("id")
            payload = {
                "project_id": snapshot.project_id,
                "snapshot_id": snapshot.id,
                "logical_object_id": logical_object_id,
                "version_no": int(item.get("version_no", 1)),
                "loop_name": item.get("loop_name") or item.get("name") or "未命名伏笔",
                "status": item.get("status", "open"),
                "source_type": "canon_seed",
                "source_ref": snapshot.id,
                "is_canon_bound": True,
                "is_current_version": True,
                "lifecycle_status": item.get("lifecycle_status", "active"),
            }
            if item.get("id"):
                payload["id"] = item["id"]
            db.add(OpenLoopCardORM(**payload))
        for item in snapshot.relationship_edges:
            logical_object_id = item.get("logical_object_id") or item.get("id")
            payload = {
                "project_id": snapshot.project_id,
                "snapshot_id": snapshot.id,
                "logical_object_id": logical_object_id,
                "version_no": int(item.get("version_no", 1)),
                "source_character_id": item.get("source_character_id", ""),
                "target_character_id": item.get("target_character_id", ""),
                "relation_type": item.get("relation_type", "unknown"),
                "relation_stage": item.get("relation_stage", "established"),
                "relation_metadata": item.get("metadata", {}),
                "source_type": "canon_seed",
                "source_ref": snapshot.id,
                "is_canon_bound": True,
                "is_current_version": True,
                "lifecycle_status": item.get("lifecycle_status", "active"),
            }
            if item.get("id"):
                payload["id"] = item["id"]
            db.add(RelationshipEdgeORM(**payload))


canon_service = CanonService()
