"""Tag Service — CRUD + document association."""

from uuid import UUID

from domain.errors import AppError, NotFoundError
from domain.repositories import TagRepository
from logging_config import get_logger

logger = get_logger(__name__)


class TagService:
    """Tag management for documents and articles."""

    def __init__(self, repo: TagRepository) -> None:
        self._repo = repo

    async def create_tag(self, name: str, is_ai_generated: bool = False) -> dict:
        name = name.strip()
        if not name:
            raise AppError(code="INVALID_TAG", message="Tag name cannot be empty", status_code=422)
        existing = await self._repo.get_by_name(name)
        if existing:
            return {"id": str(existing.id), "name": existing.name, "is_ai_generated": existing.is_ai_generated}
        tag = await self._repo.create(name, is_ai_generated)
        logger.info("tag.created", tag_id=str(tag.id), name=name)
        return {"id": str(tag.id), "name": tag.name, "is_ai_generated": tag.is_ai_generated}

    async def list_tags(self) -> list[dict]:
        tags = await self._repo.list_all()
        return [{"id": str(t.id), "name": t.name, "is_ai_generated": t.is_ai_generated} for t in tags]

    async def delete_tag(self, tag_id: UUID) -> None:
        await self._repo.delete(tag_id)
        logger.info("tag.deleted", tag_id=str(tag_id))

    async def add_tag_to_document(self, document_id: UUID, tag_name: str) -> dict:
        tag = await self._repo.get_by_name(tag_name)
        if tag is None:
            tag = await self._repo.create(tag_name)
        await self._repo.add_to_document(document_id, tag.id)
        logger.info("tag.added_to_document", document_id=str(document_id), tag=tag_name)
        return {"id": str(tag.id), "name": tag.name}

    async def remove_tag_from_document(self, document_id: UUID, tag_name: str) -> None:
        tag = await self._repo.get_by_name(tag_name)
        if tag is None:
            return
        await self._repo.remove_from_document(document_id, tag.id)
        logger.info("tag.removed_from_document", document_id=str(document_id), tag=tag_name)

    async def get_document_tags(self, document_id: UUID) -> list[dict]:
        tags = await self._repo.get_document_tags(document_id)
        return [{"id": str(t.id), "name": t.name} for t in tags]
