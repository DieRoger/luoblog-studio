"""Chunking Service — transforms ParsedDocument into DocumentChunks.

Strategy: Section-aware chunking (PRD §11).
  - Each ParsedSection creates at least one chunk.
  - If section exceeds max_tokens, split by paragraph (double newline).
  - Headings are preserved as the chunk's section field.
"""

import math
import re
from uuid import UUID, uuid4

from domain.entities import DocumentChunk
from domain.parsing import ParsedDocument
from logging_config import get_logger

logger = get_logger(__name__)

# Conservative token estimate: ~4 chars per token for English text.
CHARS_PER_TOKEN = 4.0


class ChunkingService:
    """Structure-aware document chunking.

    This is a pure domain service — no infrastructure dependencies.
    Can be used in tests without a database.
    """

    def chunk(
        self,
        parsed_doc: ParsedDocument,
        document_id: UUID,
        max_tokens: int = 1000,
        min_chunk_chars: int = 50,
    ) -> list[DocumentChunk]:
        """Split a parsed document into chunks.

        Args:
            parsed_doc: Result from a DocumentParser.
            document_id: Owning document UUID.
            max_tokens: Maximum tokens per chunk (default 1000 ≈ 4000 chars).
            min_chunk_chars: Chunks shorter than this are merged into the next.

        Returns:
            Ordered list of DocumentChunk entities.
        """
        if not parsed_doc.sections:
            logger.warning("chunking.empty_document", document_id=str(document_id))
            return []

        chunks: list[DocumentChunk] = []
        chunk_index = 0

        for section in parsed_doc.sections:
            section_chunks = self._split_section(
                section=section,
                document_id=document_id,
                max_tokens=max_tokens,
                min_chunk_chars=min_chunk_chars,
                start_index=chunk_index,
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

        logger.info(
            "chunking.completed",
            document_id=str(document_id),
            sections=len(parsed_doc.sections),
            chunks=len(chunks),
        )
        return chunks

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _split_section(
        self,
        section: "ParsedSection",
        document_id: UUID,
        max_tokens: int,
        min_chunk_chars: int,
        start_index: int,
    ) -> list[DocumentChunk]:
        """Split one ParsedSection into one or more chunks."""
        content = section.content.strip()
        if not content:
            return []

        max_chars = int(max_tokens * CHARS_PER_TOKEN)

        if len(content) <= max_chars:
            # Single chunk
            return [
                DocumentChunk(
                    id=uuid4(),
                    document_id=document_id,
                    content=content,
                    section=section.name,
                    page=section.page,
                    chunk_index=start_index,
                    token_count=self.count_tokens(content),
                    metadata={"level": section.level},
                )
            ]

        # Section exceeds max_tokens → split by paragraphs
        return self._split_by_paragraphs(
            content=content,
            section_name=section.name,
            page=section.page,
            section_level=section.level,
            document_id=document_id,
            max_chars=max_chars,
            min_chunk_chars=min_chunk_chars,
            start_index=start_index,
        )

    @staticmethod
    def _split_by_paragraphs(
        content: str,
        section_name: str,
        page: int | None,
        section_level: int,
        document_id: UUID,
        max_chars: int,
        min_chunk_chars: int,
        start_index: int,
    ) -> list[DocumentChunk]:
        """Split long content by paragraphs, merging small chunks."""
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        chunks: list[DocumentChunk] = []
        buffer = ""
        idx = start_index

        for para in paragraphs:
            # If a single paragraph is longer than max_chars, split by sentence
            if len(para) > max_chars:
                # Flush current buffer first (if it meets minimum size)
                _flush_or_merge(
                    buffer,
                    chunks,
                    section_name,
                    page,
                    section_level,
                    document_id,
                    min_chunk_chars,
                    idx,
                )
                if chunks and chunks[-1].chunk_index == idx:
                    idx += 1
                buffer = ""

                # Split long paragraph into sentence-chunks
                sentence_chunks = _split_long_paragraph(
                    para, section_name, page, section_level, document_id, max_chars, idx
                )
                chunks.extend(sentence_chunks)
                idx += len(sentence_chunks)
                continue

            # Normal paragraph — add to buffer
            if len(buffer) + len(para) + 2 <= max_chars:
                if buffer:
                    buffer += "\n\n"
                buffer += para
            else:
                _flush_or_merge(
                    buffer,
                    chunks,
                    section_name,
                    page,
                    section_level,
                    document_id,
                    min_chunk_chars,
                    idx,
                )
                if chunks and chunks[-1].chunk_index == idx:
                    idx += 1
                buffer = para

        # Flush remaining buffer
        _flush_or_merge(
            buffer, chunks, section_name, page, section_level, document_id, min_chunk_chars, idx
        )
        return chunks

    @staticmethod
    def count_tokens(text: str) -> int:
        """Estimate token count (chars / 4, rounded up)."""
        return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


# ---------------------------------------------------------------------------
# Module-level helpers (no self access)
# ---------------------------------------------------------------------------


def _make_chunk(
    content: str,
    section_name: str,
    page: int | None,
    section_level: int,
    document_id: UUID,
    index: int,
) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        document_id=document_id,
        content=content.strip(),
        section=section_name,
        page=page,
        chunk_index=index,
        token_count=ChunkingService.count_tokens(content),
        metadata={"level": section_level},
    )


def _flush_or_merge(
    buffer: str,
    chunks: list[DocumentChunk],
    section_name: str,
    page: int | None,
    section_level: int,
    document_id: UUID,
    min_chunk_chars: int,
    index: int,
) -> None:
    """Append buffer as a new chunk, or merge into the previous if too short."""
    if not buffer:
        return
    if chunks and len(buffer) < min_chunk_chars:
        # Merge into previous chunk's content
        prev = chunks[-1]
        prev.content += "\n\n" + buffer.strip()
        prev.token_count = ChunkingService.count_tokens(prev.content)
        return
    chunks.append(_make_chunk(buffer, section_name, page, section_level, document_id, index))


def _split_long_paragraph(
    paragraph: str,
    section_name: str,
    page: int | None,
    section_level: int,
    document_id: UUID,
    max_chars: int,
    start_index: int,
) -> list[DocumentChunk]:
    """Split a single long paragraph by sentence boundaries, with word-level fallback.
    Supports English, Chinese, and Japanese punctuation."""
    # Try sentence boundaries first (English .!? + CJK 。！？)
    sentences = re.split(r"(?<=[.!?。！？])\s*(?=[\u4e00-\u9fff\w\"'(])", paragraph)
    # If sentence splitting didn't reduce size enough, split by words
    if len(sentences) == 1 and len(sentences[0]) > max_chars:
        sentences = sentences[0].split()
    chunks: list[DocumentChunk] = []
    buffer = ""
    idx = start_index

    for sent in sentences:
        # If a single sent/word still exceeds max, force-flush in word-sized pieces
        remaining = sent if isinstance(sent, str) else sent
        if len(remaining) > max_chars:
            # Flush current buffer first
            if buffer:
                chunks.append(
                    _make_chunk(buffer, section_name, page, section_level, document_id, idx)
                )
                idx += 1
                buffer = ""
            # Split into word-level chunks of max_chars
            while remaining:
                chunk_text = remaining[:max_chars]
                remaining = remaining[max_chars:]
                chunks.append(
                    _make_chunk(chunk_text, section_name, page, section_level, document_id, idx)
                )
                idx += 1
            continue

        if len(buffer) + len(remaining) + 1 <= max_chars:
            if buffer:
                buffer += " "
            buffer += remaining
        else:
            if buffer:
                chunks.append(
                    _make_chunk(buffer, section_name, page, section_level, document_id, idx)
                )
                idx += 1
            buffer = remaining

    if buffer:
        chunks.append(_make_chunk(buffer, section_name, page, section_level, document_id, idx))
    return chunks
