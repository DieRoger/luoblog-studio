"""API router aggregation — all v1 endpoints are mounted here."""

from fastapi import APIRouter

from api.routers import documents, knowledge, tags, articles

api_router = APIRouter()

# Health
@api_router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}

# Feature routers
api_router.include_router(documents.router)
api_router.include_router(knowledge.router)
api_router.include_router(tags.router)
api_router.include_router(articles.router)
