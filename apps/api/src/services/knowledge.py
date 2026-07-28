"""Knowledge Service — business orchestration for document import and search."""

from uuid import UUID, uuid4

from infrastructure.storage.local_fs import DocumentStorage
from domain.repositories import DocumentRepository
from domain.entities import Document
from domain.enums import DocumentStatus, FileType, SUFFIX_TO_FILETYPE
from domain.errors import AppError, DuplicateFileError, NotFoundError
from logging_config import get_logger
from pathlib import Path

logger = get_logger(__name__)


class KnowledgeService:
    """Orchestrates document import, retrieval, and lifecycle management."""

    def __init__(self, storage: DocumentStorage, doc_repo: DocumentRepository) -> None:
        self._storage = storage
        self._repo = doc_repo

    async def import_document(
        self,
        *,
        filename: str,
        content: bytes,
        project_ids: list[UUID] | None = None,
        tags: list[str] | None = None,
    ) -> Document:
        """Full document import pipeline: validate → store → persist.

        Raises:
            AppError: if file type unsupported, file too large, or duplicate.
        """
        file_type = self._detect_file_type(filename)

        # Persist raw file to local storage
        doc_id = str(uuid4())
        storage_result = self._storage.upload(
            filename=filename, content=content, doc_id=doc_id
        )

        # Dedup check
        existing = await self._repo.get_by_hash(storage_result["file_hash"])
        if existing:
            # Clean up the just-saved duplicate file
            self._storage.delete(doc_id)
            logger.info("document.duplicate_skipped", existing_id=str(existing.id), filename=filename)
            return existing

        # Create domain entity
        doc = Document(
            id=UUID(doc_id),
            title=filename,
            file_type=file_type,
            status=DocumentStatus.IMPORTED,
            source_path=storage_result["source_path"],
            file_hash=storage_result["file_hash"],
            metadata={
                "original_filename": filename,
                "file_size": storage_result["file_size"],
                "project_ids": [str(p) for p in (project_ids or [])],
                "tags": tags or [],
            },
        )

        try:
            saved = await self._repo.save(doc)
        except DuplicateFileError:
            # Race condition: another request saved the same hash concurrently.
            self._storage.delete(doc_id)
            existing = await self._repo.get_by_hash(storage_result["file_hash"])
            if existing:
                logger.info("document.duplicate_skipped", existing_id=str(existing.id), filename=filename)
                return existing
            raise AppError(
                code="DUPLICATE_FILE",
                message="This file already exists but could not be retrieved",
                status_code=409,
            )

        logger.info("document.imported", doc_id=str(saved.id), file_type=file_type.value)
        return saved

    async def get_document(self, doc_id: UUID) -> Document:
        doc = await self._repo.get_by_id(doc_id)
        if doc is None:
            raise NotFoundError("Document", str(doc_id))
        return doc

    async def list_documents(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        offset = (page - 1) * page_size
        return await self._repo.list_all(status=status, limit=page_size, offset=offset)

    async def delete_document(self, doc_id: UUID) -> None:
        doc = await self._repo.get_by_id(doc_id)
        if doc is None:
            raise NotFoundError("Document", str(doc_id))
        await self._repo.delete(doc_id)
        self._storage.delete(str(doc_id))
        logger.info("document.deleted", doc_id=str(doc_id))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_file_type(filename: str) -> FileType:
        return SUFFIX_TO_FILETYPE.get(Path(filename).suffix.lower(), FileType.TXT)
