from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.genre import LoadGenreRequest
from app.services.genre_service import genre_service
from app.utils.response import success_response

router = APIRouter()


@router.post("/load")
def load_genre(request: LoadGenreRequest, db: Session = Depends(get_db)) -> dict:
    genre = genre_service.load_genre(db=db, request=request)
    return success_response(data=genre.model_dump(mode="json"), message="题材配置已装载")


@router.get("")
def list_genres(db: Session = Depends(get_db)) -> dict:
    genres = [item.model_dump(mode="json") for item in genre_service.list_genres(db=db)]
    return success_response(data=genres)
