"""Tests for ChunkingService — section-aware document chunking.

Coverage:
  - Unit: single section, multiple sections, long sections, empty sections
  - Failure: empty document, sections with no content
  - Edge: very short sections, boundary token count, single paragraph
  - Performance: 100-section document chunking under 1s
"""

import time
import uuid
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.entities import DocumentChunk
from domain.parsing import ParsedDocument, ParsedSection
from services.chunking import ChunkingService


@pytest.fixture
def chunker() -> ChunkingService:
    return ChunkingService()


@pytest.fixture
def doc_id() -> uuid.UUID:
    return uuid.uuid4()


# ============================================================================
# UNIT TESTS — Standard chunking
# ============================================================================


class TestChunkingBasic:
    def test_single_section_produces_one_chunk(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Test",
            sections=[ParsedSection(name="Introduction", page=1, content="Hello world.")],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert len(chunks) == 1
        assert chunks[0].document_id == doc_id
        assert chunks[0].section == "Introduction"
        assert chunks[0].page == 1

    def test_multi_section_produces_multiple_chunks(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Multi",
            sections=[
                ParsedSection(name="A", page=1, content="Section A content."),
                ParsedSection(name="B", page=2, content="Section B content."),
                ParsedSection(name="C", page=3, content="Section C content."),
            ],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert len(chunks) == 3
        assert [c.section for c in chunks] == ["A", "B", "C"]

    def test_chunks_have_incremental_index(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Idx",
            sections=[
                ParsedSection(name="X", page=1, content="X content."),
                ParsedSection(name="Y", page=2, content="Y content."),
            ],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1

    def test_chunk_content_preserved(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        text = "The quick brown fox jumps over the lazy dog."
        doc = ParsedDocument(
            title="Content",
            sections=[ParsedSection(name="Section", page=1, content=text)],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert text in chunks[0].content

    def test_token_count_is_estimated(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        text = "word " * 100  # ~500 chars → ~125 tokens
        doc = ParsedDocument(
            title="Tokens",
            sections=[ParsedSection(name="S", page=1, content=text)],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert chunks[0].token_count > 0
        assert chunks[0].token_count <= len(text)


# ============================================================================
# UNIT TESTS — Long content chunking
# ============================================================================


class TestChunkingLongContent:
    def test_long_section_splits(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        """A section with 5000 chars and max_tokens=250 (~1000 chars) should split."""
        paragraphs = "\n\n".join([f"This is paragraph number {i}. " * 5 for i in range(20)])
        doc = ParsedDocument(
            title="Long",
            sections=[ParsedSection(name="Long Section", page=1, content=paragraphs)],
        )
        chunks = chunker.chunk(doc, doc_id, max_tokens=250)
        assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"

    def test_each_chunk_within_max_tokens(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        paragraphs = "\n\n".join([f"Para-{i} " * 50 for i in range(15)])
        doc = ParsedDocument(
            title="Bound",
            sections=[ParsedSection(name="S", page=1, content=paragraphs)],
        )
        max_tok = 200
        chunks = chunker.chunk(doc, doc_id, max_tokens=max_tok)
        for c in chunks:
            assert c.token_count <= max_tok, f"Chunk {c.chunk_index}: {c.token_count} tokens > {max_tok}"

    def test_section_content_preserved_across_chunks(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        """All original text should appear across the chunks."""
        content = "\n\n".join([f"Paragraph number {i} has unique content." for i in range(10)])
        doc = ParsedDocument(
            title="Preserve",
            sections=[ParsedSection(name="S", page=1, content=content)],
        )
        chunks = chunker.chunk(doc, doc_id, max_tokens=100)
        combined = " ".join(c.content for c in chunks)
        assert "Paragraph number 5" in combined


# ============================================================================
# FAILURE TESTS
# ============================================================================


class TestChunkingFailures:
    def test_empty_document_returns_empty_list(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(title="Empty", sections=[])
        chunks = chunker.chunk(doc, doc_id)
        assert chunks == []

    def test_section_with_empty_content_skipped(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Empty section",
            sections=[
                ParsedSection(name="A", page=1, content=""),
                ParsedSection(name="B", page=2, content="Has content."),
            ],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert len(chunks) == 1
        assert chunks[0].section == "B"

    def test_section_with_whitespace_only_skipped(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Whitespace",
            sections=[
                ParsedSection(name="Blank", page=1, content="   \n\n  "),
                ParsedSection(name="Real", page=2, content="Content here."),
            ],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert len(chunks) == 1
        assert chunks[0].section == "Real"

    def test_very_low_max_tokens_still_produces_chunks(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        """Even with max_tokens=1, content should be split into valid chunks."""
        content = "Short text."
        doc = ParsedDocument(
            title="Low",
            sections=[ParsedSection(name="S", page=1, content=content)],
        )
        chunks = chunker.chunk(doc, doc_id, max_tokens=1)
        # Should still produce at least 1 chunk
        assert len(chunks) >= 1
        # Token count should be at least 1
        for c in chunks:
            assert c.token_count >= 1


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestChunkingEdgeCases:
    def test_single_character_section(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Tiny",
            sections=[ParsedSection(name="A", page=1, content="X")],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert len(chunks) == 1
        assert chunks[0].token_count == 1

    def test_very_large_single_paragraph(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        """A single very long paragraph should still be split."""
        long_text = "word " * 2000  # ~10,000 chars
        doc = ParsedDocument(
            title="BigPara",
            sections=[ParsedSection(name="Big", page=1, content=long_text)],
        )
        chunks = chunker.chunk(doc, doc_id, max_tokens=500)
        assert len(chunks) >= 2

    def test_section_with_only_newlines_filters(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Newlines",
            sections=[ParsedSection(name="N", page=1, content="\n\n\n\n\n")],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert len(chunks) == 0

    def test_chunks_metadata_level(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Meta",
            sections=[ParsedSection(name="# Title", page=1, content="Content.", level=1)],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert chunks[0].metadata.get("level") == 1

    def test_multiple_sections_different_levels(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        doc = ParsedDocument(
            title="Levels",
            sections=[
                ParsedSection(name="H1", page=1, content="A.", level=1),
                ParsedSection(name="H2", page=1, content="B.", level=2),
            ],
        )
        chunks = chunker.chunk(doc, doc_id)
        assert chunks[0].metadata.get("level") == 1
        assert chunks[1].metadata.get("level") == 2


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestChunkingPerformance:
    def test_100_sections_under_1_second(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        sections = [ParsedSection(name=f"S{i}", page=i, content=f"Content of section {i}. ") for i in range(100)]
        doc = ParsedDocument(title="Perf", sections=sections)
        start = time.perf_counter()
        chunks = chunker.chunk(doc, doc_id)
        elapsed = time.perf_counter() - start
        assert len(chunks) == 100
        assert elapsed < 1.0, f"Took {elapsed:.2f}s"

    def test_repeated_chunking_stable(self, chunker: ChunkingService, doc_id: uuid.UUID) -> None:
        sections = [ParsedSection(name=f"S{i}", page=i, content=f"Stable content {i}. ") for i in range(20)]
        doc = ParsedDocument(title="Stable", sections=sections)
        r1 = chunker.chunk(doc, doc_id)
        r2 = chunker.chunk(doc, uuid.uuid4())
        assert len(r1) == len(r2)
