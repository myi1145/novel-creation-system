from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.project import CreateProjectRequest
from app.schemas.structured_cards import (
    CharacterCardCreate,
    CharacterCardUpdate,
    FactionCardCreate,
    FactionCardUpdate,
    LocationCardCreate,
    LocationCardUpdate,
    TerminologyCardCreate,
    TerminologyCardUpdate,
)
from app.services.project_service import project_service
from app.services.structured_card_service import structured_card_service
from app.utils.response import success_response

router = APIRouter()


@router.post("")
def create_project(request: CreateProjectRequest, db: Session = Depends(get_db)) -> dict:
    project = project_service.create_project(db=db, request=request)
    return success_response(data=project.model_dump(mode="json"), message="项目已创建")


@router.get("")
def list_projects(db: Session = Depends(get_db)) -> dict:
    projects = [item.model_dump(mode="json") for item in project_service.list_projects(db=db)]
    return success_response(data=projects)


@router.get("/{project_id}/character-cards")
def list_character_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_character_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/character-cards")
def create_character_card(project_id: str, request: CharacterCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_character_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="角色卡已创建")


@router.get("/{project_id}/character-cards/{card_id}")
def get_character_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_character_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/character-cards/{card_id}")
def update_character_card(project_id: str, card_id: int, request: CharacterCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_character_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="角色卡已更新")


@router.get("/{project_id}/terminology-cards")
def list_terminology_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_terminology_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/terminology-cards")
def create_terminology_card(project_id: str, request: TerminologyCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_terminology_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="术语卡已创建")


@router.get("/{project_id}/terminology-cards/{card_id}")
def get_terminology_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_terminology_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/terminology-cards/{card_id}")
def update_terminology_card(project_id: str, card_id: int, request: TerminologyCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_terminology_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="术语卡已更新")


@router.get("/{project_id}/faction-cards")
def list_faction_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_faction_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/faction-cards")
def create_faction_card(project_id: str, request: FactionCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_faction_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="势力卡已创建")


@router.get("/{project_id}/faction-cards/{card_id}")
def get_faction_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_faction_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/faction-cards/{card_id}")
def update_faction_card(project_id: str, card_id: int, request: FactionCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_faction_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="势力卡已更新")


@router.get("/{project_id}/location-cards")
def list_location_cards(project_id: str, db: Session = Depends(get_db)) -> dict:
    items = [item.model_dump(mode="json") for item in structured_card_service.list_location_cards(db=db, project_id=project_id)]
    return success_response(data=items)


@router.post("/{project_id}/location-cards")
def create_location_card(project_id: str, request: LocationCardCreate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.create_location_card(db=db, project_id=project_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="地点卡已创建")


@router.get("/{project_id}/location-cards/{card_id}")
def get_location_card(project_id: str, card_id: int, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.get_location_card(db=db, project_id=project_id, card_id=card_id)
    return success_response(data=item.model_dump(mode="json"))


@router.patch("/{project_id}/location-cards/{card_id}")
def update_location_card(project_id: str, card_id: int, request: LocationCardUpdate, db: Session = Depends(get_db)) -> dict:
    item = structured_card_service.update_location_card(db=db, project_id=project_id, card_id=card_id, request=request)
    return success_response(data=item.model_dump(mode="json"), message="地点卡已更新")
