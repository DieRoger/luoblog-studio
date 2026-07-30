"""Knowledge search API — hybrid search across all indexed documents."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from config import settings
from domain.embedding import EmbeddingService
from domain.errors import AppError
from domain.parsing import DocumentParser
from infrastructure.embedding.api_embedding import LiteLLMEmbeddingService
from infrastructure.persistence.repositories import ChunkRepository, DocumentRepository
from infrastructure.persistence.repositories import TagRepository as TagRepoImpl
from infrastructure.storage.local_fs import DocumentStorage
from logging_config import get_logger
from services.pipeline import KnowledgePipelineService

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_pipeline_service(db: AsyncSession = Depends(get_db)) -> KnowledgePipelineService:
    storage = DocumentStorage()
    doc_repo = DocumentRepository(db)
    chunk_repo = ChunkRepository(db)

    # Choose embedding implementation based on config
    if settings.embedding_mode == "local":
        from infrastructure.embedding.local_bge import LocalBgeEmbeddingService

        embedder: EmbeddingService = LocalBgeEmbeddingService()
    else:
        embedder = LiteLLMEmbeddingService()

    # Choose parser based on config (MVP: PDF only)
    from infrastructure.parsing.pdf_parser import PdfParser

    parser: DocumentParser = PdfParser()

    return KnowledgePipelineService(
        storage=storage,
        doc_repo=doc_repo,
        chunk_repo=chunk_repo,
        parser=parser,
        embedder=embedder,
    )


@router.post("/process/{doc_id}", status_code=202)
async def process_document(
    doc_id: UUID,
    pipeline: KnowledgePipelineService = Depends(get_pipeline_service),
) -> dict:
    """Process an imported document through the full pipeline: parse → chunk → embed → index."""
    try:
        doc = await pipeline.process_document(doc_id)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("knowledge.process_failed", doc_id=str(doc_id))
        raise AppError(
            code="PROCESS_FAILED",
            message=f"Failed to process document: {exc}",
            status_code=500,
        ) from exc

    return {
        "data": {
            "id": str(doc.id),
            "status": doc.status.value,
        }
    }


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
    search_type: str = Query("hybrid", pattern="^(vector|hybrid)$"),
    tags: str = Query(None, description="Comma-separated tag names to filter by"),
    pipeline: KnowledgePipelineService = Depends(get_pipeline_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Search indexed documents by semantic similarity + keyword.

    Args:
        q: Natural language query string.
        top_k: Number of results (default 10, max 50).
        search_type: 'vector' for pure vector search, 'hybrid' for BM25 + vector.
        tags: Optional comma-separated tag names. Only documents with ALL tags returned.

    Returns:
        List of matched chunks with document title, section, page, and relevance score.
    """
    try:
        doc_ids = None
        if tags:
            tag_names = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_names:
                tag_repo = TagRepoImpl(db)
                matching = await tag_repo.search_by_tags(tag_names)
                doc_ids = set(matching)
        results = await pipeline.search(
            query=q, top_k=top_k, search_type=search_type, doc_ids=doc_ids
        )
    except AppError:
        raise
    except Exception as exc:
        logger.exception("knowledge.search_failed", query=q)
        raise AppError(
            code="SEARCH_FAILED",
            message=f"Search failed: {exc}",
            status_code=500,
        ) from exc

    return {
        "data": results,
        "meta": {
            "query": q,
            "result_count": len(results),
            "search_type": search_type,
        },
    }
