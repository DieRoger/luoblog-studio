"""Evidence Service — links article claims to Knowledge Hub evidence.

Builds the Claim → Evidence → Source chain that distinguishes LuoBlog
from standard AI writing tools.
"""

from uuid import UUID

from domain.entities import Claim, Evidence
from domain.enums import ClaimStatus, SourceType
from domain.grounding import GroundingReport
from domain.repositories import ClaimRepository, EvidenceRepository
from logging_config import get_logger
from services.grounding import GroundingChecker

logger = get_logger(__name__)


class EvidenceService:
    """Orchestrate claim-evidence linking for generated articles."""

    def __init__(
        self,
        claim_repo: ClaimRepository,
        evidence_repo: EvidenceRepository,
        grounding_checker: GroundingChecker,
    ) -> None:
        self._claim_repo = claim_repo
        self._evidence_repo = evidence_repo
        self._checker = grounding_checker

    async def process_article(self, article_id: UUID, article_text: str) -> GroundingReport:
        """Extract claims, verify against KB, store Claim + Evidence records.

        Returns a GroundingReport showing which claims are grounded.
        """
        # Run grounding check
        report = await self._checker.verify(article_text)

        # Save each verification as Claim + Evidence records
        for i, v in enumerate(report.verifications):
            claim = Claim(
                article_id=article_id,
                content=v.claim_text,
                status=ClaimStatus.VERIFIED if v.is_grounded else ClaimStatus.UNVERIFIED,
                position=i,
            )
            saved_claim = await self._claim_repo.save(claim)

            if v.is_grounded and v.source_content and v.chunk_id:
                evidence = Evidence(
                    chunk_id=UUID(v.chunk_id) if v.chunk_id else None,
                    claim_id=saved_claim.id,
                    source_type=SourceType.QUOTE,
                    content=v.source_content,
                    source_location=v.source_title,
                    confidence=v.confidence,
                )
                await self._evidence_repo.save(evidence)

        logger.info(
            "evidence.processed",
            article_id=str(article_id),
            claims=report.total_claims,
            grounded=report.grounded_claims,
        )
        return report

    async def get_article_evidence(self, article_id: UUID) -> list[dict]:
        """Get all claims with their evidence for an article."""
        claims = await self._claim_repo.get_by_article(article_id)
        result = []
        for claim in claims:
            evidence_list = await self._evidence_repo.get_by_claim(claim.id)
            result.append(
                {
                    "claim": claim.content,
                    "status": claim.status.value,
                    "evidence": [
                        {
                            "source": e.source_location,
                            "content": e.content[:200],
                            "confidence": e.confidence,
                        }
                        for e in evidence_list
                    ],
                }
            )
        return result
