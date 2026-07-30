"""Domain value objects — immutable, identity-less types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Score:
    """Score with guaranteed 0.0–1.0 range."""

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Score must be 0.0–1.0, got {self.value}")


@dataclass(frozen=True)
class Confidence:
    """Evidence confidence, 0.0–1.0."""

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Confidence must be 0.0–1.0, got {self.value}")


@dataclass(frozen=True)
class ReviewScores:
    technical_accuracy: float
    evidence_coverage: float
    writing_quality: float
    originality: float

    @property
    def overall(self) -> float:
        return round(
            (
                self.technical_accuracy * 0.35
                + self.evidence_coverage * 0.30
                + self.writing_quality * 0.20
                + self.originality * 0.15
            ),
            1,
        )
