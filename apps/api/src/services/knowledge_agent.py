"""Knowledge Agent — finds connections between documents.

Scans the knowledge base to suggest links between related documents.
For MVP: finds top-N similar documents for each document via embedding.
"""

from uuid import UUID

from domain.embedding import EmbeddingService
from domain.repositories import ChunkRepository, DocumentRepository
from logging_config import get_logger

logger = get_logger(__name__)


class KnowledgeAgent:
    """Discover connections between documents in the knowledge base."""

    def __init__(
        self,
        embedder: EmbeddingService,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo

    async def find_related(self, document_id: UUID, top_k: int = 5) -> list[dict]:
        """Find documents related to a given document."""
        chunks = await self._chunk_repo.get_by_document(document_id)
        if not chunks:
            return []

        # Use first chunk's content to search for related content
        query = chunks[0].content[:500]
        embedding = await self._embedder.embed_one(query)
        if not embedding:
            return []

        results = await self._chunk_repo.vector_search(embedding, top_k)
        seen_docs: set[UUID] = set()
        related: list[dict] = []

        for chunk, score in results:
            if chunk.document_id == document_id:
                continue
            if chunk.document_id in seen_docs:
                continue
            seen_docs.add(chunk.document_id)
            doc = await self._doc_repo.get_by_id(chunk.document_id)
            related.append({
                "document_id": str(chunk.document_id),
                "title": doc.title if doc else "Unknown",
                "relevance": round(score, 4),
            })

        return related

    async def scan_all(self, limit: int = 20) -> list[dict]:
        """Scan recent documents and return all discovered connections."""
        docs, _ = await self._doc_repo.list_all(limit=limit)
        connections = []
        for doc in docs:
            related = await self.find_related(doc.id, top_k=3)
            if related:
                connections.append({
                    "source_id": str(doc.id),
                    "source_title": doc.title,
                    "related": related,
                })
        logger.info("knowledge.scan_complete", documents=len(docs), connections=len(connections))
        return connections
