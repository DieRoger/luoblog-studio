"""Domain entities — core business objects with identity and state.

Each entity owns its state transitions. No infrastructure or framework imports allowed.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from domain.enums import (
    AgentType,
    ArticleStatus,
    ClaimStatus,
    DocumentStatus,
    FileType,
    SourceType,
    TaskStatus,
)
from domain.errors import InvalidStateTransition
from domain.value_objects import Confidence, ReviewScores, Score


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


@dataclass
class Document:
    id: UUID = field(default_factory=uuid4)
    title: str = ""
    file_type: FileType = FileType.PDF
    status: DocumentStatus = DocumentStatus.IMPORTED
    source_path: str = ""
    file_hash: str | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def mark_processing(self) -> None:
        if self.status != DocumentStatus.IMPORTED:
            raise InvalidStateTransition("Document", self.status.value, "processing")
        self.status = DocumentStatus.PROCESSING

    def mark_ready(self) -> None:
        if self.status != DocumentStatus.PROCESSING:
            raise InvalidStateTransition("Document", self.status.value, "ready")
        self.status = DocumentStatus.READY

    def mark_failed(self) -> None:
        if self.status not in (DocumentStatus.IMPORTED, DocumentStatus.PROCESSING):
            raise InvalidStateTransition("Document", self.status.value, "failed")
        self.status = DocumentStatus.FAILED


# ---------------------------------------------------------------------------
# DocumentChunk
# ---------------------------------------------------------------------------


@dataclass
class DocumentChunk:
    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    content: str = ""
    section: str | None = None
    page: int | None = None
    chunk_index: int = 0
    token_count: int = 0
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------


@dataclass
class Article:
    id: UUID = field(default_factory=uuid4)
    title: str = ""
    slug: str = ""
    summary: str | None = None
    content: str | None = None
    status: ArticleStatus = ArticleStatus.DRAFT
    quality_score: float | None = None
    topics: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def submit_for_review(self) -> None:
        if self.status != ArticleStatus.DRAFT:
            raise InvalidStateTransition("Article", self.status.value, "review")
        self.status = ArticleStatus.REVIEW

    def publish(self) -> None:
        if self.status != ArticleStatus.REVIEW:
            raise InvalidStateTransition("Article", self.status.value, "published")
        self.status = ArticleStatus.PUBLISHED
        self.published_at = datetime.utcnow()

    def archive(self) -> None:
        if self.status not in (ArticleStatus.DRAFT, ArticleStatus.PUBLISHED):
            raise InvalidStateTransition("Article", self.status.value, "archived")
        self.status = ArticleStatus.ARCHIVED


# ---------------------------------------------------------------------------
# Claim & Evidence
# ---------------------------------------------------------------------------


@dataclass
class Claim:
    id: UUID = field(default_factory=uuid4)
    article_id: UUID = field(default_factory=uuid4)
    content: str = ""
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    position: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def verify(self) -> None:
        self.status = ClaimStatus.VERIFIED

    def dispute(self) -> None:
        self.status = ClaimStatus.DISPUTED


@dataclass
class Evidence:
    id: UUID = field(default_factory=uuid4)
    chunk_id: UUID = field(default_factory=uuid4)
    claim_id: UUID | None = None
    source_type: SourceType = SourceType.QUOTE
    content: str = ""
    source_location: str = ""
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def link_to_claim(self, claim_id: UUID) -> None:
        self.claim_id = claim_id


# ---------------------------------------------------------------------------
# Agent Task
# ---------------------------------------------------------------------------


@dataclass
class AgentTask:
    id: UUID = field(default_factory=uuid4)
    agent_type: AgentType = AgentType.RESEARCH
    input: dict = field(default_factory=dict)
    output: dict | None = None
    status: TaskStatus = TaskStatus.PENDING
    total_tokens: int = 0
    cost: float = 0.0
    latency_ms: float | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def start(self) -> None:
        if self.status != TaskStatus.PENDING:
            raise InvalidStateTransition("AgentTask", self.status.value, "running")
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self, output: dict, tokens: int, cost: float) -> None:
        if self.status != TaskStatus.RUNNING:
            raise InvalidStateTransition("AgentTask", self.status.value, "completed")
        self.status = TaskStatus.COMPLETED
        self.output = output
        self.total_tokens = tokens
        self.cost = cost
        self.latency_ms = (datetime.utcnow() - self.started_at).total_seconds() * 1000 if self.started_at else None
        self.completed_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        if self.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            raise InvalidStateTransition("AgentTask", self.status.value, "failed")
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow()
