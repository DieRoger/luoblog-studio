"""Knowledge Graph — entity relationship service.

Builds a lightweight graph from existing data:
  Document → tags → related documents
  Document → project → related documents

For MVP, uses existing tables (tags, projects, document_tags, document_projects).
"""

from uuid import UUID

from domain.repositories import DocumentRepository, TagRepository
from logging_config import get_logger
from services.knowledge_agent import KnowledgeAgent

logger = get_logger(__name__)


class KnowledgeGraphService:
    """Build and query the knowledge graph."""

    def __init__(
        self,
        doc_repo: DocumentRepository,
        tag_repo: TagRepository,
        knowledge_agent: KnowledgeAgent,
    ) -> None:
        self._doc_repo = doc_repo
        self._tag_repo = tag_repo
        self._agent = knowledge_agent

    async def get_document_graph(self, document_id: UUID) -> dict:
        """Get all relationships for a document."""
        # Tags linked to this document
        tags = await self._tag_repo.get_document_tags(document_id)

        # Related documents via embedding similarity
        related = await self._agent.find_related(document_id, top_k=5)

        return {
            "document_id": str(document_id),
            "tags": [{"id": str(t.id), "name": t.name} for t in tags],
            "related_documents": related,
            "relationship_count": len(tags) + len(related),
        }

    async def get_graph_summary(self) -> dict:
        """Get a summary of the entire knowledge graph."""
        doc_count = 0
        tag_count = 0
        try:
            tags = await self._tag_repo.list_all()
            tag_count = len(tags)
        except Exception:
            pass
        return {
            "node_count": doc_count + tag_count,
            "document_count": doc_count,
            "tag_count": tag_count,
        }
