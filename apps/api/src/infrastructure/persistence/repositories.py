"""SQLAlchemy implementation of domain repository interfaces."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, delete as sa_delete, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities import Document
from domain.enums import DocumentStatus, FileType
from domain.errors import AppError, NotFoundError
from domain.repositories import DocumentRepository as DocRepoABC
from infrastructure.persistence.models import (
    DocumentModel,
    TagModel,
    DocumentTagModel,
)


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


class ChunkRepository:
    """SQLAlchemy implementation of ChunkRepository (ABC in domain.repositories).

    Handles PGVector operations for document chunks.
    Requires PostgreSQL + pgvector extension at runtime.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_batch(self, chunks: list["DocumentChunk"]) -> list["DocumentChunk"]:
        from domain.entities import DocumentChunk as DC

        orm_models = []
        for c in chunks:
            orm = DocumentChunkModel(
                id=c.id,
                document_id=c.document_id,
                content=c.content,
                section=c.section,
                page=c.page,
                chunk_index=c.chunk_index,
                token_count=c.token_count,
                metadata=c.metadata,
            )
            if hasattr(c, "embedding") and c.embedding:
                orm.embedding = c.embedding
            self._session.add(orm)
            orm_models.append(orm)

        await self._session.flush()
        return chunks

    async def get_by_document(self, doc_id: UUID) -> list["DocumentChunk"]:
        from domain.entities import DocumentChunk as DC

        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == doc_id)
            .order_by(DocumentChunkModel.chunk_index)
        )
        result = await self._session.execute(stmt)
        return [_chunk_to_entity(m) for m in result.scalars().all()]

    async def vector_search(
        self, embedding: list[float], top_k: int = 10
    ) -> list[tuple["DocumentChunk", float]]:
        from domain.entities import DocumentChunk as DC

        vec = embedding  # pgvector handles list input
        stmt = (
            select(
                DocumentChunkModel,
                DocumentChunkModel.embedding.cosine_distance(vec).label("distance"),
            )
            .order_by(DocumentChunkModel.embedding.cosine_distance(vec))
            .limit(top_k)
        )
        result = await self._session.execute(stmt)
        return [
            (_chunk_to_entity(row.DocumentChunkModel), 1.0 - float(row.distance))
            for row in result
        ]

    async def hybrid_search(
        self, query: str, embedding: list[float], top_k: int = 10
    ) -> list[tuple["DocumentChunk", float]]:
        """Combine vector cosine similarity + BM25 text ranking.

        Score = 0.5 * (1 - cosine_distance) + 0.5 * ts_rank
        """
        from sqlalchemy import text

        vec = embedding
        tsq = func.plainto_tsquery("english", query)
        ts_rank = func.ts_rank(
            func.to_tsvector("english", DocumentChunkModel.content), tsq
        )
        vec_score = (1.0 - DocumentChunkModel.embedding.cosine_distance(vec)).label("vec_score")

        stmt = (
            select(
                DocumentChunkModel,
                (vec_score * 0.5 + ts_rank * 0.5).label("combined_score"),
            )
            .where(tsq.isnot(None))
            .order_by(text("combined_score DESC"))
            .limit(top_k)
        )
        result = await self._session.execute(stmt)
        return [
            (_chunk_to_entity(row.DocumentChunkModel), float(row.combined_score))
            for row in result
        ]

    async def delete_by_document(self, doc_id: UUID) -> None:
        from sqlalchemy import delete as sa_delete

        stmt = sa_delete(DocumentChunkModel).where(DocumentChunkModel.document_id == doc_id)
        await self._session.execute(stmt)
        await self._session.flush()


# ---------------------------------------------------------------------------
# Mapper — ChunkModel → Chunk entity
# ---------------------------------------------------------------------------


def _chunk_to_entity(m: "DocumentChunkModel") -> "DocumentChunk":
    from domain.entities import DocumentChunk as DC

    return DC(
        id=m.id,
        document_id=m.document_id,
        content=m.content,
        section=m.section,
        page=m.page,
        chunk_index=m.chunk_index,
        token_count=m.token_count,
        metadata=m.metadata if isinstance(m.metadata, dict) else {},
    )


class TagRepository:
    """SQLAlchemy implementation of TagRepository ABC."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str, is_ai_generated: bool = False) -> TagModel:
        orm = TagModel(name=name, is_ai_generated=is_ai_generated)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return orm

    async def get_by_id(self, tag_id: UUID) -> TagModel | None:
        return await self._session.get(TagModel, tag_id)

    async def get_by_name(self, name: str) -> TagModel | None:
        stmt = select(TagModel).where(TagModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[TagModel]:
        stmt = select(TagModel).order_by(TagModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, tag_id: UUID) -> None:
        orm = await self._session.get(TagModel, tag_id)
        if orm is None:
            raise NotFoundError("Tag", str(tag_id))
        await self._session.delete(orm)
        await self._session.flush()

    async def add_to_document(self, document_id: UUID, tag_id: UUID) -> None:
        self._session.add(DocumentTagModel(document_id=document_id, tag_id=tag_id))
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            # Duplicate (document_id, tag_id) — ignore silently

    async def remove_from_document(self, document_id: UUID, tag_id: UUID) -> None:
        stmt = sa_delete(DocumentTagModel).where(
            and_(DocumentTagModel.document_id == document_id, DocumentTagModel.tag_id == tag_id)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_document_tags(self, document_id: UUID) -> list[TagModel]:
        stmt = (
            select(TagModel)
            .join(DocumentTagModel, DocumentTagModel.tag_id == TagModel.id)
            .where(DocumentTagModel.document_id == document_id)
            .order_by(TagModel.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_tags(self, tag_names: list[str]) -> list[UUID]:
        """Return document IDs that have ALL specified tags."""
        if not tag_names:
            return []
        stmt = (
            select(DocumentTagModel.document_id)
            .join(TagModel, TagModel.id == DocumentTagModel.tag_id)
            .where(TagModel.name.in_(tag_names))
            .group_by(DocumentTagModel.document_id)
            .having(func.count(DocumentTagModel.tag_id) == len(tag_names))
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result]
