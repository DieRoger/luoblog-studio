"""Tag API — CRUD + document association."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from domain.errors import AppError
from infrastructure.persistence.repositories import TagRepository as TagRepoImpl
from services.tags import TagService
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tags", tags=["tags"])


def get_tag_service(db: AsyncSession = Depends(get_db)) -> TagService:
    return TagService(repo=TagRepoImpl(db))


@router.post("", status_code=201)
async def create_tag(
    body: dict,
    service: TagService = Depends(get_tag_service),
) -> dict:
    name = body.get("name", "").strip()
    if not name:
        raise AppError(code="INVALID_TAG", message="Tag name is required", status_code=422)
    result = await service.create_tag(name, body.get("is_ai_generated", False))
    return {"data": result}


@router.get("")
async def list_tags(
    service: TagService = Depends(get_tag_service),
) -> dict:
    tags = await service.list_tags()
    return {"data": tags}


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: UUID,
    service: TagService = Depends(get_tag_service),
) -> None:
    await service.delete_tag(tag_id)


@router.post("/link/{document_id}")
async def add_tag_to_document(
    document_id: UUID,
    body: dict,
    service: TagService = Depends(get_tag_service),
) -> dict:
    tag_name = body.get("tag", "").strip()
    if not tag_name:
        raise AppError(code="INVALID_TAG", message="Tag name is required", status_code=422)
    result = await service.add_tag_to_document(document_id, tag_name)
    return {"data": result}


@router.delete("/link/{document_id}/{tag_name}", status_code=204)
async def remove_tag_from_document(
    document_id: UUID,
    tag_name: str,
    service: TagService = Depends(get_tag_service),
) -> None:
    await service.remove_tag_from_document(document_id, tag_name)


@router.get("/document/{document_id}")
async def get_document_tags(
    document_id: UUID,
    service: TagService = Depends(get_tag_service),
) -> dict:
    tags = await service.get_document_tags(document_id)
    return {"data": tags}
