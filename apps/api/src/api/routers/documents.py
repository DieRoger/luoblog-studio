"""Document API router — upload, list, get, delete."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from domain.errors import AppError
from infrastructure.persistence.repositories import DocumentRepository
from infrastructure.storage.local_fs import DocumentStorage
from logging_config import get_logger
from services.knowledge import KnowledgeService

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Dependency — build KnowledgeService per request
# ---------------------------------------------------------------------------


def get_knowledge_service(db: AsyncSession = Depends(get_db)) -> KnowledgeService:
    storage = DocumentStorage()
    repo = DocumentRepository(db)
    return KnowledgeService(storage=storage, repo=repo)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    """Upload a document file. Supported: PDF, Markdown, TXT, HTML, DOCX, code, images.

    The file is stored locally and a Document record is created. Deduplication
    is performed on content hash — re-uploading the same file returns the
    existing record.
    """
    content = await file.read()

    try:
        doc = await service.import_document(
            filename=file.filename or "untitled",
            content=content,
        )
    except AppError:
        raise
    except Exception as exc:
        logger.exception("document.upload_failed", filename=file.filename)
        raise AppError(
            code="UPLOAD_FAILED",
            message=f"Failed to process file: {exc}",
            status_code=500,
        ) from exc

    return {
        "data": {
            "id": str(doc.id),
            "title": doc.title,
            "file_type": doc.file_type.value,
            "status": doc.status.value,
            "file_hash": doc.file_hash,
            "file_size": doc.metadata.get("file_size", 0),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
    }


@router.get("")
async def list_documents(
    status: str | None = Query(None, description="Filter: imported, processing, ready, failed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    """List documents with optional status filter and pagination."""
    docs, total = await service.list_documents(status=status, page=page, page_size=page_size)
    return {
        "data": [
            {
                "id": str(d.id),
                "title": d.title,
                "file_type": d.file_type.value,
                "status": d.status.value,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: UUID,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> dict:
    """Get a single document by ID."""
    doc = await service.get_document(doc_id)
    return {
        "data": {
            "id": str(doc.id),
            "title": doc.title,
            "file_type": doc.file_type.value,
            "status": doc.status.value,
            "source_path": doc.source_path,
            "file_hash": doc.file_hash,
            "metadata": doc.metadata,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }
    }


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: UUID,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> None:
    """Soft-delete a document and remove its stored files."""
    await service.delete_document(doc_id)
