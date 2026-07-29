"""Tests for Knowledge Agent."""
import sys, uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.entities import DocumentChunk
from services.knowledge_agent import KnowledgeAgent


@pytest.fixture
def agent() -> KnowledgeAgent:
    embedder = AsyncMock()
    embedder.embed_one.return_value = [0.1] * 128
    chunk_repo = AsyncMock()
    doc_repo = AsyncMock()
    return KnowledgeAgent(embedder=embedder, chunk_repo=chunk_repo, doc_repo=doc_repo)


class TestKnowledgeAgent:
    pytestmark = pytest.mark.asyncio

    async def test_find_related_no_chunks_returns_empty(self, agent: KnowledgeAgent) -> None:
        agent._chunk_repo.get_by_document.return_value = []
        result = await agent.find_related(uuid.uuid4())
        assert result == []

    async def test_find_related_skips_same_doc(self, agent: KnowledgeAgent) -> None:
        doc_id = uuid.uuid4()
        agent._chunk_repo.get_by_document.return_value = [
            DocumentChunk(id=uuid.uuid4(), document_id=doc_id, content="Test", section="Intro", chunk_index=0, token_count=5)
        ]
        other_id = uuid.uuid4()
        other = DocumentChunk(id=uuid.uuid4(), document_id=other_id, content="Other", section="Body", chunk_index=0, token_count=5)
        agent._chunk_repo.vector_search.return_value = [(other, 0.85)]
        agent._doc_repo.get_by_id.return_value = MagicMock(title="Related Paper")

        result = await agent.find_related(doc_id)
        assert len(result) == 1
        assert result[0]["document_id"] == str(other_id)

    async def test_scan_all_returns_connections(self, agent: KnowledgeAgent) -> None:
        doc_id = uuid.uuid4()
        agent._doc_repo.list_all.return_value = ([MagicMock(id=doc_id, title="Doc A")], 1)
        agent._chunk_repo.get_by_document.return_value = [
            DocumentChunk(id=uuid.uuid4(), document_id=doc_id, content="Content", section="S", chunk_index=0, token_count=5)
        ]
        other_id = uuid.uuid4()
        agent._chunk_repo.vector_search.return_value = [
            (DocumentChunk(id=uuid.uuid4(), document_id=other_id, content="Other", section="S", chunk_index=0, token_count=5), 0.9)
        ]
        agent._doc_repo.get_by_id.return_value = MagicMock(title="Related")

        result = await agent.scan_all(limit=5)
        assert len(result) >= 1
