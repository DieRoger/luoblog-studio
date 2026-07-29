"""Grounding domain types — claim verification results."""

from dataclasses import dataclass, field


@dataclass
class ClaimVerification:
    """Result of verifying a single claim against the knowledge base."""
    claim_text: str
    is_grounded: bool
    confidence: float  # 0.0–1.0
    source_title: str = ""
    source_content: str = ""
    source_score: float = 0.0


@dataclass
class GroundingReport:
    """Complete grounding verification result for an article."""
    total_claims: int = 0
    grounded_claims: int = 0
    ungrounded_claims: int = 0
    verifications: list[ClaimVerification] = field(default_factory=list)
    evidence_coverage: float = 0.0  # grounded / total
