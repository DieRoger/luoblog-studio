"""Review domain types — ReviewReport, ReviewIssue, ReviewScores."""

from dataclasses import dataclass, field

from domain.value_objects import ReviewScores


@dataclass
class ReviewIssue:
    """A single issue found during review."""

    severity: str  # "critical" | "warning" | "suggestion"
    location: str  # e.g. "Section 2, Paragraph 3"
    message: str
    suggestion: str


@dataclass
class ReviewReport:
    """Complete review result for an article or section."""

    scores: ReviewScores
    issues: list[ReviewIssue] = field(default_factory=list)
    summary: str = ""
