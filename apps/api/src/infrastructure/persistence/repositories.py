"""SQLAlchemy implementation of domain repository interfaces."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities import Document
from domain.enums import DocumentStatus, FileType
from domain.errors import AppError, NotFoundError
from domain.repositories import DocumentRepository as DocRepoABC
from infrastructure.persistence.models import DocumentModel


class DocumentRepository(DocRepoABC):
    """Async SQLAlchemy implementation of DocumentRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document: Document) -> Document:
        orm = DocumentModel(
            id=document.id,
            title=document.title,
            file_type=document.file_type.value,
            status=document.status.value,
            source_path=document.source_path,
            file_hash=document.file_hash,
            metadata=document.metadata,
        )
        self._session.add(orm)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            raise DuplicateFileError(document.file_hash or "unknown") from None
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def get_by_id(self, doc_id: UUID) -> Document | None:
        stmt = select(DocumentModel).where(
            DocumentModel.id == doc_id, DocumentModel.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def get_by_hash(self, file_hash: str) -> Document | None:
        """Check if a file with the same content hash already exists (excludes soft-deleted)."""
        stmt = select(DocumentModel).where(
            DocumentModel.file_hash == file_hash,
            DocumentModel.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def list_all(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        base = select(DocumentModel).where(DocumentModel.deleted_at.is_(None))
        count_q = select(func.count()).select_from(DocumentModel).where(
            DocumentModel.deleted_at.is_(None)
        )

        if status:
            base = base.where(DocumentModel.status == status)
            count_q = count_q.where(DocumentModel.status == status)

        base = base.order_by(DocumentModel.created_at.desc()).offset(offset).limit(limit)

        rows = await self._session.execute(base)
        total = (await self._session.execute(count_q)).scalar_one()

        documents = [self._to_entity(r) for r in rows.scalars().all()]
        return documents, total

    async def delete(self, doc_id: UUID) -> None:
        orm = await self._session.get(DocumentModel, doc_id)
        if orm is None:
            raise NotFoundError("Document", str(doc_id))
        orm.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def update_status(self, doc_id: UUID, status: DocumentStatus) -> None:
        orm = await self._session.get(DocumentModel, doc_id)
        if orm is None:
            raise NotFoundError("Document", str(doc_id))
        orm.status = status.value
        orm.updated_at = datetime.now(timezone.utc)
        await self._session.flush()

    # ------------------------------------------------------------------
    # Mapper
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(m: DocumentModel) -> Document:
        return Document(
            id=m.id,
            title=m.title,
            file_type=FileType(m.file_type),
            status=DocumentStatus(m.status),
            source_path=m.source_path,
            file_hash=m.file_hash,
            metadata=m.metadata if isinstance(m.metadata, dict) else {},
            created_at=m.created_at.replace(tzinfo=None) if m.created_at else None,
            updated_at=m.updated_at.replace(tzinfo=None) if m.updated_at else None,
        )
