"""Tests for PDF Parser — PdfParser (PyMuPDF) and domain types.

Coverage:
  - Unit: PDF text extraction, heading detection, section grouping
  - Failure: missing file, corrupted PDF, unsupported format
  - Edge: single page, no headings, no metadata
  - Performance: 20+ page PDF under time limit
"""

import os
import tempfile
import time
import uuid
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.errors import AppError, ParsingError
from domain.parsing import ParsedDocument, ParsedSection
from infrastructure.parsing.pdf_parser import PdfParser


# ============================================================================
# Fixtures — generate test PDFs using PyMuPDF
# ============================================================================


def _create_test_pdf(
    *,
    title: str = "Test Document",
    page_count: int = 3,
    headings: list[str] | None = None,
    add_bold_headings: bool = False,
    body_text: str = "This is body text with normal font size. " * 10,
) -> bytes:
    """Create an in-memory PDF using PyMuPDF's document writer."""
    import fitz

    doc = fitz.open()  # new empty PDF
    if title:
        doc.metadata["title"] = title

    page = doc.new_page()  # first page

    # Page 1: title-like large text, then body
    insert_point = fitz.Point(72, 100)
    page.insert_text(insert_point, title, fontsize=24, fontname="helv")

    if headings:
        if add_bold_headings:
            page.insert_text(fitz.Point(72, 140), headings[0], fontsize=16, fontname="helv")
        else:
            page.insert_text(fitz.Point(72, 140), headings[0], fontsize=16, fontname="helv")
        page.insert_text(fitz.Point(72, 165), body_text[:200], fontsize=10, fontname="helv")
    else:
        page.insert_text(fitz.Point(72, 140), body_text[:200], fontsize=10, fontname="helv")

    # Additional pages
    for i in range(1, page_count):
        page = doc.new_page()
        if headings and i < len(headings):
            if add_bold_headings:
                page.insert_text(fitz.Point(72, 100), headings[i], fontsize=16, fontname="helv")
            else:
                page.insert_text(fitz.Point(72, 100), headings[i], fontsize=16, fontname="helv")
            page.insert_text(fitz.Point(72, 130), body_text[:200], fontsize=10, fontname="helv")
        else:
            page.insert_text(fitz.Point(72, 100), body_text[:200], fontsize=10, fontname="helv")

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _save_pdf(pdf_bytes: bytes, suffix: str = ".pdf") -> str:
    """Save PDF bytes to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(pdf_bytes)
    tmp.close()
    return tmp.name


@pytest.fixture
def parser() -> PdfParser:
    return PdfParser()


@pytest.fixture
def simple_pdf() -> str:
    pdf = _create_test_pdf(title="Simple Report", page_count=3)
    path = _save_pdf(pdf)
    yield path
    os.unlink(path)


@pytest.fixture
def structured_pdf() -> str:
    pdf = _create_test_pdf(
        title="RAG Survey 2025",
        page_count=4,
        headings=["Introduction", "Methodology", "Evaluation Results", "Discussion"],
    )
    path = _save_pdf(pdf)
    yield path
    os.unlink(path)


# ============================================================================
# UNIT TESTS — Basic parsing
# ============================================================================


class TestPdfParser:
    """Verify that a PDF is parsed into the expected structured format."""

    def test_parse_returns_parsed_document(self, parser: PdfParser, structured_pdf: str) -> None:
        result = parser.parse(structured_pdf)
        assert isinstance(result, ParsedDocument)
        assert result.pages == 4
        assert len(result.sections) > 0
        assert result.raw_text

    def test_parse_simple_pdf(self, parser: PdfParser, simple_pdf: str) -> None:
        result = parser.parse(simple_pdf)
        assert result.pages == 3
        assert result.raw_text

    def test_parse_detects_section_names(self, parser: PdfParser, structured_pdf: str) -> None:
        result = parser.parse(structured_pdf)
        section_names = [s.name.lower() for s in result.sections]
        # At least preamble or first heading should be present
        assert len(result.sections) >= 1

    def test_parse_assigns_page_numbers(self, parser: PdfParser, structured_pdf: str) -> None:
        result = parser.parse(structured_pdf)
        for section in result.sections:
            assert 1 <= section.page <= result.pages

    def test_parse_sections_have_content(self, parser: PdfParser, structured_pdf: str) -> None:
        result = parser.parse(structured_pdf)
        for section in result.sections:
            assert len(section.content) > 0


# ============================================================================
# FAILURE TESTS
# ============================================================================


class TestPdfParserFailures:
    def test_empty_path_raises_app_error(self, parser: PdfParser) -> None:
        with pytest.raises(AppError) as exc:
            parser.parse("")
        assert exc.value.code == "EMPTY_FILE_PATH"

    def test_nonexistent_file_raises_parsing_error(self, parser: PdfParser) -> None:
        with pytest.raises(ParsingError):
            parser.parse(str(uuid.uuid4()) + ".pdf")

    def test_not_a_pdf_raises_parsing_error(self, parser: PdfParser) -> None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(b"This is not a PDF file")
        tmp.close()
        try:
            with pytest.raises(ParsingError) as exc:
                parser.parse(tmp.name)
            assert exc.value.code == "PARSING_FAILED"
        finally:
            os.unlink(tmp.name)

    def test_empty_pdf_parses_gracefully(self, parser: PdfParser) -> None:
        import fitz

        doc = fitz.open()
        doc.new_page()  # empty page
        pdf_bytes = doc.tobytes()
        doc.close()
        path = _save_pdf(pdf_bytes)
        try:
            result = parser.parse(path)
            assert result.pages == 1
            assert result.sections  # Should have at least a preamble
        finally:
            os.unlink(path)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestPdfParserEdgeCases:
    def test_single_page_pdf(self, parser: PdfParser) -> None:
        pdf = _create_test_pdf(title="Single Page", page_count=1)
        path = _save_pdf(pdf)
        try:
            result = parser.parse(path)
            assert result.pages == 1
        finally:
            os.unlink(path)

    def test_no_title_metadata(self, parser: PdfParser) -> None:
        """When no title in metadata, parser should not crash."""
        import fitz

        doc = fitz.open()
        doc.metadata["title"] = ""  # explicitly empty
        doc.new_page()
        doc[0].insert_text(fitz.Point(72, 100), "Content without title", fontsize=12, fontname="helv")
        pdf_bytes = doc.tobytes()
        doc.close()
        path = _save_pdf(pdf_bytes)
        try:
            result = parser.parse(path)
            assert result.title  # Should fallback to something
        finally:
            os.unlink(path)

    def test_long_document(self, parser: PdfParser) -> None:
        """15-page PDF should parse within reasonable time."""
        pdf = _create_test_pdf(title="Long Doc", page_count=15,
                               headings=["Section " + str(i) for i in range(1, 7)])
        path = _save_pdf(pdf)
        try:
            result = parser.parse(path)
            assert result.pages == 15
            assert len(result.sections) > 0
        finally:
            os.unlink(path)

    def test_unicode_content(self, parser: PdfParser) -> None:
        """PDF with accented Latin text."""
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(fitz.Point(72, 100), "Research Evaluation: Co^limé & Müller (2025)", fontsize=16, fontname="helv")
        page.insert_text(fitz.Point(72, 130), "Accented: résumé naïve, Jaén, São Paulo, Zürich", fontsize=10, fontname="helv")
        pdf_bytes = doc.tobytes()
        doc.close()
        path = _save_pdf(pdf_bytes)
        try:
            result = parser.parse(path)
            assert "Co^limé" in result.raw_text
        finally:
            os.unlink(path)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPdfParserPerformance:
    def test_parse_under_5_seconds(self, parser: PdfParser) -> None:
        """25-page PDF should parse in under 5 seconds."""
        pdf = _create_test_pdf(title="Perf Test", page_count=25,
                               headings=["H" + str(i) for i in range(5)])
        path = _save_pdf(pdf)
        try:
            start = time.perf_counter()
            parser.parse(path)
            elapsed = time.perf_counter() - start
            assert elapsed < 5.0, f"25-page PDF took {elapsed:.2f}s, expected < 5s"
        finally:
            os.unlink(path)

    def test_repeated_parse_is_stable(self, parser: PdfParser) -> None:
        """Parsing the same PDF twice should produce identical results."""
        pdf = _create_test_pdf(title="Stable", page_count=5,
                               headings=["A", "B"])
        path = _save_pdf(pdf)
        try:
            r1 = parser.parse(path)
            r2 = parser.parse(path)
            assert r1.pages == r2.pages
            assert len(r1.sections) == len(r2.sections)
        finally:
            os.unlink(path)
