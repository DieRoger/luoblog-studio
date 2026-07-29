"""Markdown parser — extracts section structure.

Pipeline:
  .md file → Line-by-line parsing → Heading Detection → Section Grouping → ParsedDocument

Supports ATX headings (# through ######) with code fence awareness.
"""

from pathlib import Path

from domain.errors import AppError, ParsingError
from domain.parsing import DocumentParser, ParsedDocument, ParsedSection
from logging_config import get_logger

logger = get_logger(__name__)

_CODE_FENCE_CHARS = ("```", "~~~")


class MarkdownParser(DocumentParser):
    """Parse a Markdown file into structured sections using Mistune AST."""

    def parse(self, file_path: str) -> ParsedDocument:
        if not file_path:
            raise AppError(
                code="EMPTY_FILE_PATH",
                message="File path is empty",
                status_code=400,
            )

        try:
            raw_text = Path(file_path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ParsingError("markdown", f"File not found: {exc}") from exc
        except Exception as exc:
            raise ParsingError("markdown", f"Failed to read file: {exc}") from exc

        try:
            title = self._extract_title(raw_text)
            sections = self._extract_sections(raw_text)
        except Exception as exc:
            logger.exception("markdown.parse_failed", path=file_path)
            raise ParsingError("markdown", f"Parsing failed: {exc}") from exc

        result = ParsedDocument(
            title=title,
            sections=sections,
            pages=1,
            raw_text=raw_text,
        )

        logger.info(
            "markdown.parsed",
            path=file_path,
            sections=len(result.sections),
        )
        return result

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_title(text: str) -> str:
        """Extract document title from first H1 heading."""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                return stripped[2:].strip()
        return "Untitled"

    def _extract_sections(self, text: str) -> list[ParsedSection]:
        """Parse markdown into sections by heading level."""
        sections: list[ParsedSection] = []
        current_section = ParsedSection(name="preamble", page=1, content="", level=0)
        code_fence = False

        for line in text.splitlines():
            # Track code fences to avoid parsing headings inside code blocks
            stripped = line.strip()
            if any(stripped.startswith(f) for f in _CODE_FENCE_CHARS):
                code_fence = not code_fence
                current_section.content += line + "\n"
                continue

            if code_fence:
                current_section.content += line + "\n"
                continue

            # Check for heading
            heading_match = self._match_heading(stripped)
            if heading_match:
                level, name = heading_match
                # Flush previous section
                if current_section.content.strip():
                    sections.append(current_section)
                current_section = ParsedSection(
                    name=name,
                    page=1,
                    content="",
                    level=level,
                )
            else:
                current_section.content += line + "\n"

        # Flush last section
        if current_section.content.strip():
            sections.append(current_section)

        # If no sections at all, create one
        if not sections and current_section.content.strip():
            sections.append(current_section)

        return sections

    @staticmethod
    def _match_heading(line: str) -> tuple[int, str] | None:
        """Detect markdown heading and return (level, name)."""
        if not line.startswith("#"):
            return None
        # Count # characters
        level = 0
        for ch in line:
            if ch == "#":
                level += 1
            else:
                break
        if level > 6 or level < 1:
            return None
        name = line[level:].strip()
        if not name:
            return None
        # Skip setext-style headings (underlined with === or ---)
        # Those are parsed as regular text in this simple parser
        return level, name
