from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.services.prompt_template_service import prompt_template_service


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        prompt_template_service.ensure_default_templates(db)
    finally:
        db.close()
