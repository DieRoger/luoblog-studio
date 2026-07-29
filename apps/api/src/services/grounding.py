"""Grounding Checker — verifies article claims against the Knowledge Hub.

Helps the Review Agent improve Evidence Coverage scoring by identifying
which claims in a generated article can be verified from the knowledge base.
"""

import re

from domain.embedding import EmbeddingService
from domain.grounding import ClaimVerification, GroundingReport
from domain.repositories import ChunkRepository, DocumentRepository
from logging_config import get_logger

logger = get_logger(__name__)

MIN_CONFIDENCE = 0.65  # cosine similarity threshold for "grounded"


class GroundingChecker:
    """Verify article claims against the knowledge base."""

    def __init__(
        self,
        embedder: EmbeddingService,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo

    async def verify(self, article_text: str, top_k: int = 5) -> GroundingReport:
        """Extract claims from article text and verify each against the KB.

        Process:
        1. Split article into sentences
        2. Filter out non-claim sentences (headings, citations, generic)
        3. Search each claim in the Knowledge Hub
        4. Score by best-matching chunk similarity
        5. Return GroundingReport with per-claim results
        """
        claims = self._extract_claims(article_text)
        if not claims:
            return GroundingReport()

        verifications: list[ClaimVerification] = []

        for claim_text in claims:
            result = await self._verify_single(claim_text, top_k)
            verifications.append(result)

        grounded = sum(1 for v in verifications if v.is_grounded)
        return GroundingReport(
            total_claims=len(claims),
            grounded_claims=grounded,
            ungrounded_claims=len(claims) - grounded,
            verifications=verifications,
            evidence_coverage=round(grounded / len(claims), 4) if claims else 0.0,
        )

    async def _verify_single(self, claim: str, top_k: int) -> ClaimVerification:
        """Search KB for the claim and determine if it's grounded."""
        embedding = await self._embedder.embed_one(claim)
        if not embedding:
            return ClaimVerification(claim_text=claim, is_grounded=False, confidence=0.0)

        results = await self._chunk_repo.vector_search(embedding, top_k)
        if not results:
            return ClaimVerification(claim_text=claim, is_grounded=False, confidence=0.0)

        # Best match defines confidence
        best_chunk, best_score = results[0]
        is_grounded = best_score >= MIN_CONFIDENCE

        # Get document title
        doc = await self._doc_repo.get_by_id(best_chunk.document_id)
        source_title = doc.title if doc else "Unknown"

        logger.debug(
            "grounding.verified",
            claim=claim[:80],
            score=round(best_score, 4),
            grounded=is_grounded,
        )
        return ClaimVerification(
            claim_text=claim,
            is_grounded=is_grounded,
            confidence=round(best_score, 4),
            source_title=source_title,
            source_content=best_chunk.content[:200],
            source_score=round(best_score, 4),
        )

    # ------------------------------------------------------------------
    # Claim extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_claims(text: str) -> list[str]:
        """Split text into candidate claims (sentences with substance)."""
        # Split by sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text)
        claims = []
        for s in sentences:
            stripped = s.strip()
            if not stripped:
                continue
            # Skip very short sentences, headings, and citations
            if len(stripped) < 30:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("[") and "]" in stripped:
                continue
            # Skip purely citation-like sentences
            if re.match(r"^[\d\s.,;:!?()'\"-]+$", stripped):
                continue
            claims.append(stripped)
        return claims
