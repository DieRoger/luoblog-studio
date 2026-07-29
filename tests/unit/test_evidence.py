"""Tests for Evidence Service — claim-evidence linking.

Coverage:
  - Unit: process article with grounded claims
  - Unit: process article with ungrounded claims
  - Unit: get article evidence with claims + evidence records
  - Failure: empty article
  - Edge: no evidence found for any claim
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.grounding import ClaimVerification, GroundingReport
from services.evidence import EvidenceService


@pytest.fixture
def mock_claim_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def mock_evidence_repo() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def mock_checker() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_claim_repo: MagicMock,
    mock_evidence_repo: MagicMock,
    mock_checker: MagicMock,
) -> EvidenceService:
    return EvidenceService(
        claim_repo=mock_claim_repo,
        evidence_repo=mock_evidence_repo,
        grounding_checker=mock_checker,
    )


class TestEvidenceProcessing:
    pytestmark = pytest.mark.asyncio

    async def test_process_article_with_grounded_claims(
        self, service: EvidenceService, mock_checker: MagicMock, mock_claim_repo: MagicMock, mock_evidence_repo: MagicMock
    ) -> None:
        report = GroundingReport(
            total_claims=2, grounded_claims=2, ungrounded_claims=0,
            verifications=[
                ClaimVerification(claim_text="RAG needs multi-dim metrics.", is_grounded=True, confidence=0.85,
                                  chunk_id=str(uuid.uuid4()), source_title="Paper A", source_content="RAG evaluation requires multiple dimensions."),
                ClaimVerification(claim_text="Hybrid search improves recall.", is_grounded=True, confidence=0.78,
                                  chunk_id=str(uuid.uuid4()), source_title="Paper B", source_content="Hybrid search outperforms vector search."),
            ],
            evidence_coverage=1.0,
        )
        mock_checker.verify.return_value = report
        mock_claim_repo.save.side_effect = lambda c: c

        result = await service.process_article(uuid.uuid4(), "Article text here.")
        assert result.total_claims == 2
        assert result.grounded_claims == 2
        assert mock_claim_repo.save.call_count == 2
        assert mock_evidence_repo.save.call_count == 2

    async def test_process_empty_article(
        self, service: EvidenceService, mock_checker: MagicMock
    ) -> None:
        mock_checker.verify.return_value = GroundingReport()
        result = await service.process_article(uuid.uuid4(), "")
        assert result.total_claims == 0

    async def test_get_article_evidence(
        self, service: EvidenceService, mock_claim_repo: MagicMock, mock_evidence_repo: MagicMock
    ) -> None:
        from domain.entities import Claim
        from domain.enums import ClaimStatus

        cid = uuid.uuid4()
        mock_claim_repo.get_by_article.return_value = [
            Claim(id=cid, article_id=uuid.uuid4(), content="Test claim.", status=ClaimStatus.VERIFIED, position=0),
        ]
        from domain.entities import Evidence
        from domain.enums import SourceType

        mock_evidence_repo.get_by_claim.return_value = [
            Evidence(chunk_id=uuid.uuid4(), claim_id=cid, source_type=SourceType.QUOTE,
                     content="Evidence content here.", source_location="Paper A, Section 2", confidence=0.9),
        ]

        result = await service.get_article_evidence(uuid.uuid4())
        assert len(result) == 1
        assert result[0]["claim"] == "Test claim."
        assert len(result[0]["evidence"]) == 1
        assert result[0]["evidence"][0]["confidence"] == 0.9

    async def test_all_claims_ungrounded(
        self, service: EvidenceService, mock_checker: MagicMock,
        mock_claim_repo: MagicMock, mock_evidence_repo: MagicMock
    ) -> None:
        report = GroundingReport(
            total_claims=3, grounded_claims=0, ungrounded_claims=3,
            verifications=[ClaimVerification(claim_text=f"C{i}", is_grounded=False, confidence=0.3) for i in range(3)],
            evidence_coverage=0.0,
        )
        mock_checker.verify.return_value = report
        mock_claim_repo.save.side_effect = lambda c: c

        result = await service.process_article(uuid.uuid4(), "Some text.")
        assert result.total_claims == 3
        assert result.ungrounded_claims == 3
        assert mock_evidence_repo.save.call_count == 0  # no evidence saved for ungrounded
