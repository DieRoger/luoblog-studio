"""PDF parser using PyMuPDF — text extraction with structure detection.

Pipeline:
  PDF → PyMuPDF → Block Extraction → Heading Detection → Section Grouping → ParsedDocument

Heading detection is heuristic-based:
  - Larger font size → potential heading
  - Bold typeface → potential heading
  - Short lines (≤ 80 chars) with preceding whitespace → potential heading
"""

import fitz  # PyMuPDF

from domain.errors import AppError, ParsingError
from domain.parsing import DocumentParser, ParsedDocument, ParsedSection
from logging_config import get_logger

logger = get_logger(__name__)

# Heuristic: a text block is potentially a heading if its font size exceeds
# the page median by at least this ratio.
HEADING_SIZE_RATIO = 1.3

# Bold fonts often contain "Bold", "Heavy", "Black" in their PostScript name.
BOLD_INDICATORS = ("bold", "heavy", "black", "semibold")


class PdfParser(DocumentParser):
    """Parse a PDF file into structured sections using PyMuPDF font heuristics."""

    def parse(self, file_path: str) -> ParsedDocument:
        if not file_path:
            raise AppError(
                code="EMPTY_FILE_PATH",
                message="File path is empty",
                status_code=400,
            )

        try:
            doc = fitz.open(file_path)
        except fitz.FileDataError as exc:
            raise ParsingError("pdf", f"Not a valid PDF file: {exc}") from exc
        except FileNotFoundError as exc:
            raise ParsingError("pdf", f"File not found: {exc}") from exc
        except Exception as exc:
            raise ParsingError("pdf", f"Failed to open PDF: {exc}") from exc

        try:
            title = self._extract_title(doc)
            sections, raw_text = self._extract_sections(doc)
            pages = len(doc)
        except Exception as exc:
            logger.exception("pdf.parse_failed", path=file_path)
            raise ParsingError("pdf", f"PDF parsing failed: {exc}") from exc
        finally:
            doc.close()

        result = ParsedDocument(
            title=title,
            sections=sections,
            pages=pages,
            raw_text=raw_text,
        )

        logger.info(
            "pdf.parsed",
            path=file_path,
            pages=result.pages,
            sections=len(result.sections),
        )
        return result

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_title(doc: fitz.Document) -> str:
        """Best-effort title extraction from metadata or first-page content."""
        if doc.metadata and doc.metadata.get("title"):
            return doc.metadata["title"].strip()
        # Fallback: first non-metadata filename-like prefix
        if doc.metadata and doc.metadata.get("subject"):
            return doc.metadata["subject"].strip()
        return doc.name or "Untitled"

    def _extract_sections(
        self, doc: fitz.Document
    ) -> tuple[list[ParsedSection], str]:
        """Iterate pages, detect heading blocks, group into sections.

        First pass collects font sizes for global median, then second
        pass extracts sections using that median as the heading threshold.
        """
        all_text_parts: list[str] = []
        sections: list[ParsedSection] = []
        current_section = ParsedSection(name="preamble", page=1, content="", level=0)

        # First pass: collect global font statistics
        all_font_sizes: list[float] = []
        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            all_font_sizes.extend(self._collect_font_sizes(blocks))
        global_median = self._median(all_font_sizes) if all_font_sizes else 12.0
        global_threshold = global_median * HEADING_SIZE_RATIO

        # Second pass: extract sections
        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") != 0:  # 0 = text block
                    continue

                block_text = self._block_text(block)
                if not block_text.strip():
                    continue

                all_text_parts.append(block_text)

                # Determine if this block looks like a heading
                max_size = self._block_max_font_size(block)
                is_bold = self._block_is_bold(block)
                is_heading = (max_size >= global_threshold) or is_bold
                is_short = len(block_text.strip()) < 80

                if is_heading and is_short:
                    # Flush previous section
                    if current_section.content.strip():
                        sections.append(current_section)
                    current_section = ParsedSection(
                        name=block_text.strip(),
                        page=page_num,
                        content="",
                        level=self._estimate_level(max_size, global_median),
                    )
                else:
                    current_section.content += block_text + "\n"

        # Flush last section
        if current_section.content.strip():
            sections.append(current_section)

        # If no sections detected, create one
        if not sections:
            sections.append(current_section)

        return sections, "\n".join(all_text_parts)

    # ------------------------------------------------------------------
    # Font analysis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_font_sizes(blocks: list[dict]) -> list[float]:
        sizes = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(span.get("size", 0))
        return sizes

    @staticmethod
    def _block_text(block: dict) -> str:
        lines = []
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            lines.append(text)
        return " ".join(lines)

    @staticmethod
    def _block_max_font_size(block: dict) -> float:
        max_size = 0.0
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                max_size = max(max_size, span.get("size", 0))
        return max_size

    @staticmethod
    def _block_is_bold(block: dict) -> bool:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                font = span.get("font", "").lower()
                if any(indicator in font for indicator in BOLD_INDICATORS):
                    return True
        return False

    @staticmethod
    def _estimate_level(max_size: float, median_size: float) -> int:
        if max_size >= median_size * 2.0:
            return 1  # # Title-level
        if max_size >= median_size * 1.5:
            return 2  # ## Section-level
        return 3  # ### Subsection-level

    @staticmethod
    def _median(values: list[float]) -> float:
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n == 0:
            return 0.0
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
        return float(sorted_vals[mid])
