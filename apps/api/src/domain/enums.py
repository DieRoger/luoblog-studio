"""Domain enums — status types and discriminators used across all layers."""

from enum import StrEnum


class FileType(StrEnum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    CODE = "code"
    IMAGE = "image"
    TXT = "txt"
    HTML = "html"
    DOCX = "docx"


# Canonical suffix → FileType mapping. Single source of truth used by
# both DocumentStorage (validation) and KnowledgeService (entity creation).
SUFFIX_TO_FILETYPE: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".md": FileType.MARKDOWN,
    ".txt": FileType.TXT,
    ".html": FileType.HTML,
    ".htm": FileType.HTML,
    ".docx": FileType.DOCX,
    ".py": FileType.CODE,
    ".js": FileType.CODE,
    ".ts": FileType.CODE,
    ".go": FileType.CODE,
    ".rs": FileType.CODE,
    ".java": FileType.CODE,
    ".cpp": FileType.CODE,
    ".yaml": FileType.CODE,
    ".yml": FileType.CODE,
    ".json": FileType.CODE,
    ".png": FileType.IMAGE,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".svg": FileType.IMAGE,
}


class DocumentStatus(StrEnum):
    IMPORTED = "imported"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"


class SourceType(StrEnum):
    QUOTE = "quote"
    DATA = "data"
    CODE = "code"
    EXPERIMENT = "experiment"


class AgentType(StrEnum):
    RESEARCH = "research"
    PAPER = "paper"
    WRITING = "writing"
    REVIEW = "review"
    WRITING_PIPELINE = "writing_pipeline"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
