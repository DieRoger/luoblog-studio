"""Tests for Citation Formatter."""
import sys, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from domain.entities import Evidence
from domain.enums import SourceType
from services.citation import format_citation


def test_apa_format():
    e = Evidence(chunk_id=uuid.uuid4(), source_type=SourceType.QUOTE, content="Test",
                 source_location="Smith, J.", confidence=0.9,
                 metadata={"title": "RAG Survey", "page": 12})
    result = format_citation(e, "apa")
    assert "Smith" in result
    assert "RAG Survey" in result


def test_mla_format():
    e = Evidence(chunk_id=uuid.uuid4(), source_type=SourceType.QUOTE, content="Test",
                 source_location="Smith, J.", confidence=0.9,
                 metadata={"title": "RAG Survey", "page": 12})
    result = format_citation(e, "mla")
    assert "Smith" in result
    assert "RAG Survey" in result


def test_unknown_style_falls_back_to_apa():
    e = Evidence(chunk_id=uuid.uuid4(), source_type=SourceType.QUOTE, content="Test",
                 source_location="Smith, J.", confidence=0.9)
    result = format_citation(e, "chicago")
    assert "Smith" in result


def test_no_metadata():
    e = Evidence(chunk_id=uuid.uuid4(), source_type=SourceType.QUOTE, content="Test",
                 source_location="Author", confidence=0.5)
    result = format_citation(e, "apa")
    assert "Author" in result
