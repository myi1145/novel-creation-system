from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.changeset import ProposeChangeSetRequest
from app.schemas.object_models import (
    CreateCharacterCardRequest,
    CreateOpenLoopCardRequest,
    CreateRelationshipEdgeRequest,
    CreateRuleCardRequest,
    RestoreObjectVersionRequest,
    RetireObjectRequest,
    UpdateCharacterCardRequest,
    UpdateOpenLoopCardRequest,
    UpdateRelationshipEdgeRequest,
    UpdateRuleCardRequest,
)
from app.services.changeset_service import changeset_service
from app.services.object_service import object_service
from app.utils.response import success_response

router = APIRouter()


def _build_restore_patch(*, object_type: str, logical_object_id: str, current_version_no: int, request: RestoreObjectVersionRequest) -> dict:
    patch: dict = {
        "kind": "object",
        "op": "restore_version",
        "object_type": object_type,
        "logical_object_id": logical_object_id,
        "expected_current_version_no": current_version_no,
        "bind_to_canon": request.bind_to_canon,
    }
    if request.restore_from_version_id is not None:
        patch["restore_from_version_id"] = request.restore_from_version_id
    if request.restore_from_version_no is not None:
        patch["restore_from_version_no"] = request.restore_from_version_no
    return patch


def _build_retire_patch(*, object_type: str, logical_object_id: str, current_version_no: int, request: RetireObjectRequest) -> dict:
    return {
        "kind": "object",
        "op": "retire_version",
        "object_type": object_type,
        "logical_object_id": logical_object_id,
        "expected_current_version_no": current_version_no,
        "retire_reason": request.retire_reason,
    }


@router.post("/characters")
def create_character(request: CreateCharacterCardRequest, db: Session = Depends(get_db)) -> dict:
    item = object_service.create_character(db=db, request=request)
    return success_response(data=item.model_dump(mode="json"), message="角色卡已创建")


@router.get("/characters")
def list_characters(
    project_id: str = Query(...),
    snapshot_id: str | None = Query(default=None),
    logical_object_id: str | None = Query(default=None),
    current_only: bool = Query(default=True),
    include_retired: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    items = [
        item.model_dump(mode="json")
        for item in object_service.list_characters(
            db=db,
            project_id=project_id,
            snapshot_id=snapshot_id,
            logical_object_id=logical_object_id,
            current_only=current_only,
            include_retired=include_retired,
        )
    ]
    return success_response(data=items, message="角色卡列表获取成功")


@router.get("/characters/history")
def character_history(project_id: str = Query(...), logical_object_id: str = Query(...), db: Session = Depends(get_db)) -> dict:
    items = [
        item.model_dump(mode="json")
        for item in object_service.list_characters(
            db=db,
            project_id=project_id,
            logical_object_id=logical_object_id,
            current_only=False,
            include_retired=True,
        )
    ]
    return success_response(data=items, message="角色版本历史获取成功")


@router.post("/characters/{logical_object_id}/changesets/update")
def propose_character_update(logical_object_id: str, request: UpdateCharacterCardRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_character(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = {
        "kind": "object",
        "op": "create_version",
        "object_type": "character_card",
        "logical_object_id": logical_object_id,
        "expected_version_no": current.version_no,
        "bind_to_canon": request.bind_to_canon,
        "value": {key: value for key, value in {"character_name": request.character_name, "role_tags": request.role_tags, "current_state": request.current_state}.items() if value is not None},
    }
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_update", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="角色更新 ChangeSet 已提议")


@router.post("/characters/{logical_object_id}/changesets/restore")
def propose_character_restore(logical_object_id: str, request: RestoreObjectVersionRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_character(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_restore_patch(object_type="character_card", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_restore", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="角色恢复 ChangeSet 已提议")


@router.post("/characters/{logical_object_id}/changesets/retire")
def propose_character_retire(logical_object_id: str, request: RetireObjectRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_character(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_retire_patch(object_type="character_card", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_retire", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="角色退役 ChangeSet 已提议")


@router.post("/rules")
def create_rule(request: CreateRuleCardRequest, db: Session = Depends(get_db)) -> dict:
    item = object_service.create_rule(db=db, request=request)
    return success_response(data=item.model_dump(mode="json"), message="规则卡已创建")


@router.get("/rules")
def list_rules(project_id: str = Query(...), snapshot_id: str | None = Query(default=None), logical_object_id: str | None = Query(default=None), current_only: bool = Query(default=True), include_retired: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in object_service.list_rules(db=db, project_id=project_id, snapshot_id=snapshot_id, logical_object_id=logical_object_id, current_only=current_only, include_retired=include_retired)]
    return success_response(data=items, message="规则卡列表获取成功")


@router.get("/rules/history")
def rule_history(project_id: str = Query(...), logical_object_id: str = Query(...), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in object_service.list_rules(db=db, project_id=project_id, logical_object_id=logical_object_id, current_only=False, include_retired=True)]
    return success_response(data=items, message="规则版本历史获取成功")


@router.post("/rules/{logical_object_id}/changesets/update")
def propose_rule_update(logical_object_id: str, request: UpdateRuleCardRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_rule(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = {"kind": "object", "op": "create_version", "object_type": "rule_card", "logical_object_id": logical_object_id, "expected_version_no": current.version_no, "bind_to_canon": request.bind_to_canon, "value": {key: value for key, value in {"rule_name": request.rule_name, "description": request.description, "severity": request.severity}.items() if value is not None}}
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_update", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="规则更新 ChangeSet 已提议")


@router.post("/rules/{logical_object_id}/changesets/restore")
def propose_rule_restore(logical_object_id: str, request: RestoreObjectVersionRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_rule(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_restore_patch(object_type="rule_card", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_restore", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="规则恢复 ChangeSet 已提议")


@router.post("/rules/{logical_object_id}/changesets/retire")
def propose_rule_retire(logical_object_id: str, request: RetireObjectRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_rule(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_retire_patch(object_type="rule_card", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_retire", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="规则退役 ChangeSet 已提议")


@router.post("/open-loops")
def create_open_loop(request: CreateOpenLoopCardRequest, db: Session = Depends(get_db)) -> dict:
    item = object_service.create_open_loop(db=db, request=request)
    return success_response(data=item.model_dump(mode="json"), message="伏笔卡已创建")


@router.get("/open-loops")
def list_open_loops(project_id: str = Query(...), snapshot_id: str | None = Query(default=None), logical_object_id: str | None = Query(default=None), current_only: bool = Query(default=True), include_retired: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in object_service.list_open_loops(db=db, project_id=project_id, snapshot_id=snapshot_id, logical_object_id=logical_object_id, current_only=current_only, include_retired=include_retired)]
    return success_response(data=items, message="伏笔卡列表获取成功")


@router.get("/open-loops/history")
def open_loop_history(project_id: str = Query(...), logical_object_id: str = Query(...), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in object_service.list_open_loops(db=db, project_id=project_id, logical_object_id=logical_object_id, current_only=False, include_retired=True)]
    return success_response(data=items, message="伏笔版本历史获取成功")


@router.post("/open-loops/{logical_object_id}/changesets/update")
def propose_open_loop_update(logical_object_id: str, request: UpdateOpenLoopCardRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_open_loop(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = {"kind": "object", "op": "create_version", "object_type": "open_loop_card", "logical_object_id": logical_object_id, "expected_version_no": current.version_no, "bind_to_canon": request.bind_to_canon, "value": {key: value for key, value in {"loop_name": request.loop_name, "status": request.status}.items() if value is not None}}
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_update", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="伏笔更新 ChangeSet 已提议")


@router.post("/open-loops/{logical_object_id}/changesets/restore")
def propose_open_loop_restore(logical_object_id: str, request: RestoreObjectVersionRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_open_loop(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_restore_patch(object_type="open_loop_card", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_restore", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="伏笔恢复 ChangeSet 已提议")


@router.post("/open-loops/{logical_object_id}/changesets/retire")
def propose_open_loop_retire(logical_object_id: str, request: RetireObjectRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_open_loop(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_retire_patch(object_type="open_loop_card", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_retire", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="伏笔退役 ChangeSet 已提议")


@router.post("/relationships")
def create_relationship(request: CreateRelationshipEdgeRequest, db: Session = Depends(get_db)) -> dict:
    item = object_service.create_relationship(db=db, request=request)
    return success_response(data=item.model_dump(mode="json"), message="关系边已创建")


@router.get("/relationships")
def list_relationships(project_id: str = Query(...), snapshot_id: str | None = Query(default=None), logical_object_id: str | None = Query(default=None), current_only: bool = Query(default=True), include_retired: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in object_service.list_relationships(db=db, project_id=project_id, snapshot_id=snapshot_id, logical_object_id=logical_object_id, current_only=current_only, include_retired=include_retired)]
    return success_response(data=items, message="关系边列表获取成功")


@router.get("/relationships/history")
def relationship_history(project_id: str = Query(...), logical_object_id: str = Query(...), db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in object_service.list_relationships(db=db, project_id=project_id, logical_object_id=logical_object_id, current_only=False, include_retired=True)]
    return success_response(data=items, message="关系边版本历史获取成功")


@router.post("/relationships/{logical_object_id}/changesets/update")
def propose_relationship_update(logical_object_id: str, request: UpdateRelationshipEdgeRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_relationship(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = {"kind": "object", "op": "create_version", "object_type": "relationship_edge", "logical_object_id": logical_object_id, "expected_version_no": current.version_no, "bind_to_canon": request.bind_to_canon, "value": {key: value for key, value in {"relation_type": request.relation_type, "relation_stage": request.relation_stage, "metadata": request.metadata}.items() if value is not None}}
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_update", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="关系边更新 ChangeSet 已提议")


@router.post("/relationships/{logical_object_id}/changesets/restore")
def propose_relationship_restore(logical_object_id: str, request: RestoreObjectVersionRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_relationship(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_restore_patch(object_type="relationship_edge", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_restore", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="关系边恢复 ChangeSet 已提议")


@router.post("/relationships/{logical_object_id}/changesets/retire")
def propose_relationship_retire(logical_object_id: str, request: RetireObjectRequest, db: Session = Depends(get_db)) -> dict:
    current = object_service.get_current_relationship(db=db, project_id=request.project_id, logical_object_id=logical_object_id)
    patch = _build_retire_patch(object_type="relationship_edge", logical_object_id=logical_object_id, current_version_no=current.version_no, request=request)
    changeset = changeset_service.propose(db=db, request=ProposeChangeSetRequest(project_id=request.project_id, source_type="object_retire", source_ref=request.source_ref, rationale=request.rationale, patch_operations=[patch]))
    return success_response(data=changeset.model_dump(mode="json"), message="关系边退役 ChangeSet 已提议")
