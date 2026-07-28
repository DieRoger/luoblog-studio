"""Domain types for document parsing — pure data classes and parser interface.

No framework, no infrastructure. The parser interface is what services depend on.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    """A single section/chapter detected in a parsed document."""

    name: str
    page: int
    content: str
    level: int = 1  # Markdown heading level (# = 1, ## = 2, etc.)


@dataclass
class ParsedDocument:
    """Structured result of parsing a document."""

    title: str
    sections: list[ParsedSection] = field(default_factory=list)
    pages: int = 0
    raw_text: str = ""  # Full text for debugging / fallback


class DocumentParser(ABC):
    """Abstract document parser. Implementations handle specific file types.

    Parsing PDFs is CPU-bound (memory decode, layout analysis). Callers that
    need concurrency should wrap parse() with run_in_executor.
    """

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """Parse a document file and return structured sections."""
        ...
