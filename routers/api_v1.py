from fastapi import APIRouter

from app.routers import canon, changesets, chapters, gates, genres, objects, ping, projects, prompts, workflows

api_router = APIRouter()
api_router.include_router(ping.router, tags=["ping"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(genres.router, prefix="/genres", tags=["genres"])
api_router.include_router(canon.router, prefix="/canon", tags=["canon"])
api_router.include_router(objects.router, prefix="/objects", tags=["objects"])
api_router.include_router(chapters.router, prefix="/chapters", tags=["chapters"])
api_router.include_router(gates.router, prefix="/gates", tags=["gates"])
api_router.include_router(changesets.router, prefix="/changesets", tags=["changesets"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
