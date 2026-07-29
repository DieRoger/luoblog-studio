"""Tests for Knowledge Graph Service."""
import sys, uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from services.knowledge_graph import KnowledgeGraphService


@pytest.fixture
def service() -> KnowledgeGraphService:
    return KnowledgeGraphService(
        doc_repo=AsyncMock(),
        tag_repo=AsyncMock(),
        knowledge_agent=AsyncMock(),
    )


class TestKnowledgeGraph:
    pytestmark = pytest.mark.asyncio

    async def test_get_document_graph(self, service: KnowledgeGraphService) -> None:
        service._tag_repo.get_document_tags.return_value = [
            MagicMock(id=uuid.uuid4(), name="rag"),
            MagicMock(id=uuid.uuid4(), name="python"),
        ]
        service._agent.find_related.return_value = [
            {"document_id": str(uuid.uuid4()), "title": "Related Doc", "relevance": 0.85}
        ]
        result = await service.get_document_graph(uuid.uuid4())
        assert result["relationship_count"] >= 3
        assert len(result["tags"]) == 2
        assert len(result["related_documents"]) == 1

    async def test_graph_summary(self, service: KnowledgeGraphService) -> None:
        service._tag_repo.list_all.return_value = [MagicMock(id=uuid.uuid4(), name="x")]
        summary = await service.get_graph_summary()
        assert summary["tag_count"] == 1
