"""Tests for Grounding Checker — claim extraction and verification.

Coverage:
  - Unit: claim extraction from article text
  - Unit: grounding report statistics
  - Failure: empty article, no search results
  - Edge: short sentences, headings, citation lines
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

if "litellm" not in sys.modules:
    _mock_litellm = MagicMock()
    _mock_litellm.aembedding = AsyncMock()
    sys.modules["litellm"] = _mock_litellm

from domain.entities import DocumentChunk
from domain.grounding import ClaimVerification, GroundingReport
from services.grounding import GroundingChecker


@pytest.fixture
def mock_embedder() -> MagicMock:
    m = AsyncMock()
    m.embed_one.return_value = [0.1] * 128
    return m


@pytest.fixture
def mock_chunk_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def mock_doc_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def checker(
    mock_embedder: MagicMock,
    mock_chunk_repo: MagicMock,
    mock_doc_repo: MagicMock,
) -> GroundingChecker:
    return GroundingChecker(
        embedder=mock_embedder,
        chunk_repo=mock_chunk_repo,
        doc_repo=mock_doc_repo,
    )


# ============================================================================
# UNIT TESTS — Claim extraction
# ============================================================================


class TestClaimExtraction:
    def test_extract_claims_from_article(self, checker: GroundingChecker) -> None:
        text = "RAG evaluation requires multi-dimensional metrics. Faithfulness measures whether the answer is grounded in retrieved context. Answer relevance checks query alignment."
        claims = checker._extract_claims(text)
        assert len(claims) >= 2
        assert "Faithfulness" in claims[1]

    def test_skips_short_sentences(self, checker: GroundingChecker) -> None:
        text = "Yes. No. RAG evaluation requires multi-dimensional metrics to be effective."
        claims = checker._extract_claims(text)
        assert len(claims) == 1

    def test_skips_headings(self, checker: GroundingChecker) -> None:
        text = "# Introduction\n\nThis section discusses RAG evaluation methods.\n\n## Related Work\n\nPrevious work focused on single metrics."
        claims = checker._extract_claims(text)
        for c in claims:
            assert not c.startswith("#")

    def test_empty_text_returns_empty(self, checker: GroundingChecker) -> None:
        assert checker._extract_claims("") == []

    def test_skips_citation_lines(self, checker: GroundingChecker) -> None:
        text = "A significant claim about RAG evaluation that needs verification. [1] From: Paper A. Another claim about evaluation methods that should be checked."
        claims = checker._extract_claims(text)
        assert len(claims) == 2  # citation line filtered, 2 long sentences remain
        for c in claims:
            assert "From:" not in c


# ============================================================================
# UNIT TESTS — Grounding verification
# ============================================================================


class TestGroundingVerification:
    pytestmark = pytest.mark.asyncio

    async def test_verify_empty_text(self, checker: GroundingChecker) -> None:
        report = await checker.verify("")
        assert report.total_claims == 0

    async def test_no_search_results_returns_ungrounded(
        self, checker: GroundingChecker, mock_chunk_repo: MagicMock
    ) -> None:
        mock_chunk_repo.vector_search.return_value = []
        report = await checker.verify("This is a claim about RAG evaluation that must be verified.")
        assert report.total_claims == 1
        assert report.ungrounded_claims == 1
        assert report.evidence_coverage == 0.0

    async def test_high_similarity_is_grounded(
        self, checker: GroundingChecker, mock_chunk_repo: MagicMock, mock_doc_repo: MagicMock
    ) -> None:
        chunk = DocumentChunk(
            id=uuid.uuid4(), document_id=uuid.uuid4(), content="RAG evaluation requires multi-dimensional metrics.",
            section="Intro", chunk_index=0, token_count=10,
        )
        mock_chunk_repo.vector_search.return_value = [(chunk, 0.85)]
        mock_doc_repo.get_by_id.return_value = MagicMock(title="RAG Paper")

        report = await checker.verify("RAG evaluation requires multi-dimensional metrics.")
        assert report.grounded_claims == 1
        assert report.evidence_coverage > 0.5

    async def test_low_similarity_is_ungrounded(
        self, checker: GroundingChecker, mock_chunk_repo: MagicMock
    ) -> None:
        chunk = DocumentChunk(
            id=uuid.uuid4(), document_id=uuid.uuid4(), content="Something completely unrelated about databases.",
            section="Other", chunk_index=0, token_count=10,
        )
        mock_chunk_repo.vector_search.return_value = [(chunk, 0.3)]
        report = await checker.verify("RAG systems improve LLM accuracy by 45%.")
        assert report.ungrounded_claims > 0


class TestGroundingReport:
    def test_report_with_claims(self) -> None:
        v = [
            ClaimVerification(claim_text="Claim 1", is_grounded=True, confidence=0.9),
            ClaimVerification(claim_text="Claim 2", is_grounded=False, confidence=0.3),
        ]
        report = GroundingReport(
            total_claims=2, grounded_claims=1, ungrounded_claims=1,
            verifications=v, evidence_coverage=0.5,
        )
        assert report.evidence_coverage == 0.5
        assert len(report.verifications) == 2

    def test_empty_report(self) -> None:
        report = GroundingReport()
        assert report.total_claims == 0
        assert report.evidence_coverage == 0.0
