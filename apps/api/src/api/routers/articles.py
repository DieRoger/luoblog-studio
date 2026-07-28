"""Article API — CRUD for draft articles."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from domain.errors import AppError
from infrastructure.persistence.repositories import ArticleRepository as ArticleRepoImpl
from services.articles import ArticleService
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/articles", tags=["articles"])


def get_article_service(db: AsyncSession = Depends(get_db)) -> ArticleService:
    return ArticleService(repo=ArticleRepoImpl(db))


@router.post("", status_code=201)
async def create_article(
    body: dict,
    service: ArticleService = Depends(get_article_service),
) -> dict:
    title = body.get("title", "").strip()
    if not title:
        raise AppError(code="INVALID_TITLE", message="Title is required", status_code=422)
    article = await service.create(title)
    return {"data": _article_to_dict(article)}


@router.get("")
async def list_articles(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ArticleService = Depends(get_article_service),
) -> dict:
    articles, total = await service.list(status=status, page=page, page_size=page_size)
    return {
        "data": [_article_to_dict(a) for a in articles],
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.get("/{article_id}")
async def get_article(
    article_id: UUID,
    service: ArticleService = Depends(get_article_service),
) -> dict:
    article = await service.get(article_id)
    return {"data": _article_to_dict(article)}


@router.put("/{article_id}")
async def update_article(
    article_id: UUID,
    body: dict,
    service: ArticleService = Depends(get_article_service),
) -> dict:
    if "content" in body:
        article = await service.update_content(article_id, body["content"])
    elif "status" in body:
        article = await service.update_status(article_id, body["status"])
    else:
        raise AppError(code="NO_UPDATE_FIELDS", message="Provide content or status", status_code=422)
    return {"data": _article_to_dict(article)}


@router.delete("/{article_id}", status_code=204)
async def delete_article(
    article_id: UUID,
    service: ArticleService = Depends(get_article_service),
) -> None:
    await service.delete(article_id)


def _article_to_dict(a) -> dict:
    return {
        "id": str(a.id),
        "title": a.title,
        "slug": a.slug,
        "summary": a.summary,
        "status": a.status.value if hasattr(a.status, "value") else a.status,
        "quality_score": a.quality_score,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }
