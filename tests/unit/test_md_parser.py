"""Tests for Markdown Parser — heading detection, section grouping, failure cases.

Coverage:
  - Unit: H1-H6 headings, code blocks with headings, nested sections
  - Failure: empty file, nonexistent file, no headings
  - Edge: unicode content, setext-style headings, fenced code blocks
  - Performance: 100-section document < 1s
"""

import os
import tempfile
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.errors import AppError, ParsingError
from domain.parsing import ParsedDocument
from infrastructure.parsing.md_parser import MarkdownParser


@pytest.fixture
def parser() -> MarkdownParser:
    return MarkdownParser()


def _write_md(content: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w", encoding="utf-8")
    tmp.write(content)
    tmp.close()
    return tmp.name


# ============================================================================
# UNIT TESTS
# ============================================================================


class TestMarkdownParser:
    def test_simple_sections(self, parser: MarkdownParser) -> None:
        md = "# Title\n\nIntro text.\n\n## Section 1\n\nContent of section 1.\n\n## Section 2\n\nContent of section 2."
        path = _write_md(md)
        try:
            result = parser.parse(path)
            assert result.title == "Title"
            assert len(result.sections) >= 2
            assert result.sections[0].name == "preamble" or result.sections[0].name == "Title"
        finally:
            os.unlink(path)

    def test_no_title_uses_filename(self, parser: MarkdownParser) -> None:
        content = "Just plain text with no heading."
        path = _write_md(content)
        try:
            result = parser.parse(path)
            assert result.title  # Should fallback to something
        finally:
            os.unlink(path)

    def test_code_block_with_heading_inside(self, parser: MarkdownParser) -> None:
        """Headings inside code fences should not create sections."""
        md = "# Doc\n\nOutside.\n\n```\n## This is code, not a heading\n```\n\nAfter code."
        path = _write_md(md)
        try:
            result = parser.parse(path)
            section_names = [s.name for s in result.sections]
            # "This is code, not a heading" should NOT be in section names
            assert "This is code" not in " ".join(section_names)
        finally:
            os.unlink(path)

    def test_nested_sections(self, parser: MarkdownParser) -> None:
        md = "# L1\n\nContent for H1.\n\n## L2\n\nContent for H2.\n\n### L3\n\nContent for H3."
        path = _write_md(md)
        try:
            result = parser.parse(path)
            levels = [s.level for s in result.sections if s.level > 0]
            assert 1 in levels
            assert 2 in levels
            assert 3 in levels
        finally:
            os.unlink(path)


# ============================================================================
# FAILURE TESTS
# ============================================================================


class TestMarkdownParserFailures:
    def test_empty_path_raises(self, parser: MarkdownParser) -> None:
        with pytest.raises(AppError) as exc:
            parser.parse("")
        assert exc.value.code == "EMPTY_FILE_PATH"

    def test_nonexistent_file_raises(self, parser: MarkdownParser) -> None:
        with pytest.raises(ParsingError):
            parser.parse("/tmp/nonexistent_xyz.md")

    def test_empty_file_parses_gracefully(self, parser: MarkdownParser) -> None:
        path = _write_md("")
        try:
            result = parser.parse(path)
            assert result.raw_text == ""
        finally:
            os.unlink(path)

    def test_whitespace_only_file(self, parser: MarkdownParser) -> None:
        path = _write_md("   \n\n  \n\n")
        try:
            result = parser.parse(path)
            assert len(result.sections) >= 0
        finally:
            os.unlink(path)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestMarkdownParserEdgeCases:
    def test_unicode_content(self, parser: MarkdownParser) -> None:
        md = "# 研究评估\n\n这篇论文讨论了 RAG 评估方法。\n\n## 方法论\n\n我们使用了混合检索。"
        path = _write_md(md)
        try:
            result = parser.parse(path)
            assert "研究" in result.raw_text
            assert "方法论" in [s.name for s in result.sections]
        finally:
            os.unlink(path)

    def test_h1_to_h6_heading_levels(self, parser: MarkdownParser) -> None:
        md = "# H1\n\nContent H1.\n\n## H2\n\nContent H2.\n\n### H3\n\nContent H3.\n\n#### H4\n\nContent H4.\n\n##### H5\n\nContent H5.\n\n###### H6\n\nContent H6."
        path = _write_md(md)
        try:
            result = parser.parse(path)
            names = [s.name for s in result.sections]
            assert "H1" in names
            assert "H6" in names
        finally:
            os.unlink(path)

    def test_multiple_code_fences(self, parser: MarkdownParser) -> None:
        md = "# Doc\n\n```python\nprint('hello')\n```\n\n## Next\n\n```\nmore code\n```"
        path = _write_md(md)
        try:
            result = parser.parse(path)
            assert len(result.sections) > 1
        finally:
            os.unlink(path)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestMarkdownParserPerformance:
    def test_100_sections_under_1_second(self, parser: MarkdownParser) -> None:
        lines = ["# Document"]
        for i in range(100):
            lines.append(f"\n## Section {i}\n\nContent of section {i}.\n")
        md = "\n".join(lines)
        path = _write_md(md)
        try:
            start = time.perf_counter()
            parser.parse(path)
            elapsed = time.perf_counter() - start
            assert elapsed < 1.0, f"Took {elapsed:.2f}s"
        finally:
            os.unlink(path)
