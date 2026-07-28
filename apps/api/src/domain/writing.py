"""Writing Agent domain types — data classes for generated articles."""

from dataclasses import dataclass, field


@dataclass
class Citation:
    """A reference to a source chunk from the knowledge base."""
    source_title: str
    chunk_content: str
    score: float


@dataclass
class Section:
    """A single section in a generated article."""
    heading: str
    content: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class WritingResult:
    """Complete result from the Writing Agent."""
    title: str
    summary: str
    sections: list[Section] = field(default_factory=list)
