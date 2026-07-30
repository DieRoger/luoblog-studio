"""SQLAlchemy ORM models — 1:1 mapping to PostgreSQL tables.

Declarative base. All models use UUID PKs, timestamps, and soft-delete where
applicable. PGVector columns use the pgvector.sqlalchemy.Vector type.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="imported")
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[list["DocumentChunkModel"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_documents_status", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_documents_file_type", "file_type"),
        Index("idx_documents_metadata", "metadata", postgresql_using="gin"),
    )


# ---------------------------------------------------------------------------
# DocumentChunk
# ---------------------------------------------------------------------------


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(String(500))
    page: Mapped[int | None] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding = mapped_column(Vector(1024))  # BGE-m3 dimension
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    document: Mapped["DocumentModel"] = relationship(back_populates="chunks")

    __table_args__ = (Index("idx_chunks_document_id", "document_id"),)


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------


class ArticleModel(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    quality_score: Mapped[float | None] = mapped_column(Float)
    topics = mapped_column(JSONB, nullable=False, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_articles_status", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_articles_slug", "slug"),
    )


# ---------------------------------------------------------------------------
# ArticleVersion
# ---------------------------------------------------------------------------


class ArticleVersionModel(Base):
    __tablename__ = "article_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    agent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (Index("idx_article_versions_article", "article_id", "created_at"),)


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------


class ClaimModel(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unverified")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (Index("idx_claims_article", "article_id"),)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceModel(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="quote")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_evidence_chunk", "chunk_id"),
        Index("idx_evidence_claim", "claim_id"),
    )


# ---------------------------------------------------------------------------
# AgentTask
# ---------------------------------------------------------------------------


class AgentTaskModel(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_agent_tasks_status", "status"),
        Index("idx_agent_tasks_type", "agent_type"),
        Index("idx_agent_tasks_created", "created_at"),
    )


# ---------------------------------------------------------------------------
# AgentTrace
# ---------------------------------------------------------------------------


class AgentTraceModel(Base):
    __tablename__ = "agent_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_state: Mapped[dict | None] = mapped_column(JSONB)
    output_state: Mapped[dict | None] = mapped_column(JSONB)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


# ---------------------------------------------------------------------------
# Tags (many-to-many)
# ---------------------------------------------------------------------------


class TagModel(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class DocumentTagModel(Base):
    __tablename__ = "document_tags"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ArticleTagModel(Base):
    __tablename__ = "article_tags"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    github_url: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class DocumentProjectModel(Base):
    __tablename__ = "document_projects"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )


class ArticleProjectModel(Base):
    __tablename__ = "article_projects"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
