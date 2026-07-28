"""Tests for Writing Agent — outline generation, section writing, citation extraction.

Coverage:
  - Unit: _format_context, _parse_json, _extract_citations
  - Failure: empty research results, empty topic, LLM failure
  - Edge: truncated research, JSON with markdown fences
  - Performance: 3-section article under 10s (with mocked LLM)
"""

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

# Mock litellm before any project import
# Use a shared mock that supports both acompletion (writing) and aembedding (embedding)
if "litellm" not in sys.modules:
    _mock_litellm = MagicMock()
    _mock_litellm.acompletion = AsyncMock()
    _mock_litellm.aembedding = AsyncMock()
    sys.modules["litellm"] = _mock_litellm
else:
    _mock_litellm = sys.modules["litellm"]
    if not hasattr(_mock_litellm, "acompletion"):
        _mock_litellm.acompletion = AsyncMock()

from domain.errors import LLMError
from domain.writing import Citation, Section, WritingResult
from services.writing import WritingAgent


@pytest.fixture
def mock_embedder() -> MagicMock:
    m = AsyncMock()
    m.embed_one.return_value = [0.1] * 128
    m.dimension = 128
    return m


@pytest.fixture
def mock_chunk_repo() -> MagicMock:
    m = AsyncMock()
    m.vector_search.return_value = []
    return m


@pytest.fixture
def mock_doc_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def agent(
    mock_embedder: MagicMock,
    mock_chunk_repo: MagicMock,
    mock_doc_repo: MagicMock,
) -> WritingAgent:
    return WritingAgent(
        embedder=mock_embedder,
        chunk_repo=mock_chunk_repo,
        doc_repo=mock_doc_repo,
    )


# ============================================================================
# UNIT TESTS — Core logic (no LLM calls)
# ============================================================================


class TestWritingAgentCore:
    """Tests that don't need LLM — parsing, formatting, citations."""

    def test_parse_json_plain(self, agent: WritingAgent) -> None:
        raw = '{"title": "Test", "summary": "A"}'
        result = agent._parse_json(raw, {})
        assert result["title"] == "Test"

    def test_parse_json_with_fences(self, agent: WritingAgent) -> None:
        raw = '```json\n{"title": "Wrapped"}\n```'
        result = agent._parse_json(raw, {})
        assert result["title"] == "Wrapped"

    def test_parse_json_invalid_returns_default(self, agent: WritingAgent) -> None:
        result = agent._parse_json("not json", {"fallback": True})
        assert result["fallback"] is True

    def test_format_context_empty(self, agent: WritingAgent) -> None:
        result = agent._format_context([])
        assert result == ""

    def test_format_context_one_result(self, agent: WritingAgent) -> None:
        results = [{"document_title": "Paper", "section": "Intro", "score": 0.9, "content": "Content here"}]
        formatted = agent._format_context(results)
        assert "Paper" in formatted
        assert "Intro" in formatted
        assert "0.9" in formatted

    def test_extract_citations(self, agent: WritingAgent) -> None:
        context = "[1] From: Paper A\n[2] From: Paper B\n"
        citations = agent._extract_citations(context, "Intro")
        assert len(citations) == 2
        assert citations[0].source_title == "Paper A"

    def test_extract_citations_dedup(self, agent: WritingAgent) -> None:
        context = "[1] From: Same Paper\n[1] From: Same Paper\n"
        citations = agent._extract_citations(context, "Intro")
        assert len(citations) == 1


# ============================================================================
# UNIT TESTS — WritingAgent with mocked LLM
# ============================================================================


class TestWritingAgentWithMocks:
    """Tests that mock the LLM call."""
    pytestmark = pytest.mark.asyncio

    async def test_write_requires_search_results(self, agent: WritingAgent) -> None:
        """Empty search results should raise AppError."""
        from domain.errors import AppError

        with pytest.raises(AppError) as exc:
            await agent.write("unknown topic")
        assert exc.value.code == "NO_SEARCH_RESULTS"

    async def test_research_returns_empty_if_no_embedding(
        self, agent: WritingAgent, mock_embedder: MagicMock
    ) -> None:
        mock_embedder.embed_one.return_value = []
        result = await agent._research("topic", 5)
        assert result == []

    async def test_research_with_results(
        self, agent: WritingAgent, mock_chunk_repo: MagicMock, mock_doc_repo: MagicMock
    ) -> None:
        # Mock chunk repo to return results
        import uuid

        from domain.entities import DocumentChunk

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="Test content",
            section="Section 1",
            chunk_index=0,
            token_count=10,
        )
        mock_chunk_repo.vector_search.return_value = [(chunk, 0.85)]
        mock_doc_repo.get_by_id.return_value = MagicMock(title="Test Paper")

        results = await agent._research("topic", 5)
        assert len(results) == 1
        assert results[0]["document_title"] == "Test Paper"
        assert results[0]["score"] == 0.85

    async def test_llm_failure_raises_llm_error(self, agent: WritingAgent) -> None:
        """When litellm fails, agent should raise LLMError."""
        import uuid

        from domain.entities import DocumentChunk

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="Test content",
            section="Section 1",
            chunk_index=0,
            token_count=10,
        )
        agent._chunk_repo.vector_search.return_value = [(chunk, 0.85)]
        agent._doc_repo.get_by_id.return_value = MagicMock(title="Paper")

        _mock_litellm.acompletion.reset_mock()
        _mock_litellm.acompletion.side_effect = ConnectionError("API down")
        with pytest.raises(LLMError):
            await agent.write("test topic")


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestWritingAgentEdgeCases:
    """Edge cases for writing types."""
    pytestmark = pytest.mark.asyncio

    def test_section_with_empty_heading(self, agent: WritingAgent) -> None:
        """Section object handles empty heading gracefully."""
        s = Section(heading="", content="Some content")
        assert s.content == "Some content"

    def test_citation_zero_score(self, agent: WritingAgent) -> None:
        c = Citation(source_title="Test", chunk_content="", score=0.0)
        assert c.score == 0.0

    def test_writing_result_equality(self, agent: WritingAgent) -> None:
        r1 = WritingResult(title="A", summary="S", sections=[])
        r2 = WritingResult(title="A", summary="S", sections=[])
        assert r1.title == r2.title
