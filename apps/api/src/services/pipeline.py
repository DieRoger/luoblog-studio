"""Knowledge Pipeline Service — orchestrates document processing end-to-end.

Pipeline: Document → ParsedDocument → DocumentChunks → Embeddings → PGVector
"""

from uuid import UUID

from domain.entities import Document, DocumentChunk
from domain.enums import DocumentStatus
from domain.errors import AppError, NotFoundError
from domain.repositories import DocumentRepository, ChunkRepository
from domain.parsing import DocumentParser, ParsedDocument
from domain.embedding import EmbeddingService
from infrastructure.storage.local_fs import DocumentStorage
from logging_config import get_logger

logger = get_logger(__name__)


class KnowledgePipelineService:
    """Orchestrates the full document import pipeline.

    Dependencies are injected — no direct infrastructure imports.
    """

    def __init__(
        self,
        storage: DocumentStorage,
        doc_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        parser: DocumentParser,
        embedder: EmbeddingService,
    ) -> None:
        self._storage = storage
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo
        self._parser = parser
        self._embedder = embedder

    async def process_document(self, doc_id: UUID) -> Document:
        """Run the full pipeline for an already-imported document.

        1. Mark processing
        2. Parse PDF → ParsedDocument
        3. Chunk → DocumentChunks
        4. Embed → vectors
        5. Save chunks + vectors to PGVector
        6. Mark ready
        """
        doc = await self._doc_repo.get_by_id(doc_id)
        if doc is None:
            raise NotFoundError("Document", str(doc_id))

        await self._doc_repo.update_status(doc_id, DocumentStatus.PROCESSING)
        logger.info("pipeline.started", doc_id=str(doc_id))

        try:
            # Step 2: Parse
            parsed = self._parser.parse(doc.source_path)  # sync, CPU-bound

            # Step 3: Chunk
            from services.chunking import ChunkingService

            chunker = ChunkingService()
            chunks = chunker.chunk(parsed, doc_id)

            if not chunks:
                logger.warning("pipeline.no_chunks", doc_id=str(doc_id))
                await self._doc_repo.update_status(doc_id, DocumentStatus.READY)
                return doc

            # Step 4: Embed
            texts = [c.content for c in chunks]
            embeddings = await self._embedder.embed(texts)

            # Attach vectors to chunks (entity has no embedding field by design)
            # Use metadata for temporary storage during pipeline execution
            for chunk, vec in zip(chunks, embeddings):
                chunk.metadata["embedding"] = vec

            # Step 5: Save to PGVector
            await self._chunk_repo.save_batch(chunks)

            # Step 6: Mark ready
            await self._doc_repo.update_status(doc_id, DocumentStatus.READY)

            logger.info(
                "pipeline.completed",
                doc_id=str(doc_id),
                chunks=len(chunks),
            )
        except Exception as exc:
            logger.exception("pipeline.failed", doc_id=str(doc_id))
            await self._doc_repo.update_status(doc_id, DocumentStatus.FAILED)
            raise AppError(
                code="PIPELINE_FAILED",
                message=f"Document pipeline failed: {exc}",
                status_code=500,
            ) from exc

        return doc

    async def search(
        self,
        query: str,
        top_k: int = 10,
        search_type: str = "hybrid",
    ) -> list[dict]:
        """Search the knowledge base.

        Args:
            query: Natural language query.
            top_k: Number of results to return.
            search_type: "vector", "hybrid"

        Returns:
            List of { chunk, score, document_title, section, page }.
        """
        query_embedding = await self._embedder.embed_one(query)
        if not query_embedding:
            return []

        if search_type == "vector":
            results = await self._chunk_repo.vector_search(query_embedding, top_k)
        else:
            results = await self._chunk_repo.hybrid_search(query, query_embedding, top_k)

        output = []
        for chunk, score in results:
            doc = await self._doc_repo.get_by_id(chunk.document_id)
            output.append({
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_title": doc.title if doc else "Unknown",
                "content": chunk.content,
                "section": chunk.section,
                "page": chunk.page,
                "score": round(score, 4),
            })
        return output
