"""Citation Formatter — formats Evidence records into citation strings.

Supports APA and MLA formats.
Extensible: add a new format function to FORMATTERS dict.
"""

from domain.entities import Evidence


def format_citation(evidence: Evidence, style: str = "apa") -> str:
    """Format an Evidence record as a citation string.

    Args:
        evidence: Evidence entity with source_location, content, confidence.
        style: "apa" or "mla".

    Returns:
        Formatted citation string.
    """
    formatter = FORMATTERS.get(style, FORMATTERS["apa"])
    return formatter(evidence)


def _format_apa(evidence: Evidence) -> str:
    author = evidence.source_location or "Unknown"
    year = ""
    title = evidence.metadata.get("title", "") if evidence.metadata else ""

    parts = [author]
    if year:
        parts.append(f"({year})")
    if title:
        parts.append(title)
    parts.append(f"p. {evidence.metadata.get('page', 'n.p.')}" if evidence.metadata else "")
    return ", ".join(p for p in parts if p)


def _format_mla(evidence: Evidence) -> str:
    author = evidence.source_location or "Unknown"
    title = evidence.metadata.get("title", "") if evidence.metadata else ""
    publisher = evidence.metadata.get("publisher", "") if evidence.metadata else ""
    year = ""

    parts = [f"{author}."]
    if title:
        parts.append(f'"{title}."')
    if publisher:
        parts.append(publisher)
    if year:
        parts.append(year)
    parts.append(f"p. {evidence.metadata.get('page', 'n.p.')}" if evidence.metadata else "")
    return " ".join(p for p in parts if p)


FORMATTERS = {
    "apa": _format_apa,
    "mla": _format_mla,
}
