-- =============================================================================
-- LuoBlog Studio — Database Schema
-- =============================================================================
-- This file is used as the initial PostgreSQL schema.
-- For incremental changes, use Alembic migrations (database/migrations/).
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ===========================================================================
-- Documents
-- ===========================================================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'imported',
    source_path TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_documents_status ON documents(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_file_type ON documents(file_type);
CREATE INDEX idx_documents_metadata ON documents USING GIN(metadata);

-- ===========================================================================
-- Document Chunks
-- ===========================================================================

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    section VARCHAR(500),
    page INT,
    chunk_index INT NOT NULL,
    token_count INT NOT NULL,
    embedding VECTOR(1024),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_content_fts ON document_chunks
    USING GIN(to_tsvector('english', content));

-- PGVector index — created after data population for better recall
-- CREATE INDEX idx_chunks_embedding ON document_chunks
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ===========================================================================
-- Articles
-- ===========================================================================

CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    summary TEXT,
    content TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    quality_score FLOAT,
    topics JSONB NOT NULL DEFAULT '[]',
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_articles_status ON articles(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_articles_slug ON articles(slug);
CREATE INDEX idx_articles_content_fts ON articles
    USING GIN(to_tsvector('english', COALESCE(content, '')));

-- ===========================================================================
-- Article Versions
-- ===========================================================================

CREATE TABLE article_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    change_summary TEXT,
    agent_task_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_article_versions_article ON article_versions(article_id, created_at DESC);

-- ===========================================================================
-- Claims
-- ===========================================================================

CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'unverified',
    position INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_claims_article ON claims(article_id);

-- ===========================================================================
-- Evidence
-- ===========================================================================

CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id UUID NOT NULL REFERENCES document_chunks(id),
    claim_id UUID REFERENCES claims(id),
    source_type VARCHAR(20) NOT NULL DEFAULT 'quote',
    content TEXT NOT NULL,
    source_location TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_chunk ON evidence(chunk_id);
CREATE INDEX idx_evidence_claim ON evidence(claim_id);

-- ===========================================================================
-- Agent Tasks
-- ===========================================================================

CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_type VARCHAR(30) NOT NULL,
    input JSONB NOT NULL DEFAULT '{}',
    output JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_tokens INT DEFAULT 0,
    cost FLOAT DEFAULT 0.0,
    latency_ms FLOAT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_type ON agent_tasks(agent_type);
CREATE INDEX idx_agent_tasks_created ON agent_tasks(created_at DESC);

-- ===========================================================================
-- Agent Traces
-- ===========================================================================

CREATE TABLE agent_traces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    node_name VARCHAR(100) NOT NULL,
    input_state JSONB,
    output_state JSONB,
    tokens INT DEFAULT 0,
    latency_ms FLOAT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_traces_task ON agent_traces(task_id);

-- ===========================================================================
-- Tags
-- ===========================================================================

CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    is_ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document_tags (
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, tag_id)
);

CREATE TABLE article_tags (
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

-- ===========================================================================
-- Projects
-- ===========================================================================

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    github_url TEXT,
    tech_stack JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document_projects (
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, project_id)
);

CREATE TABLE article_projects (
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, project_id)
);

-- ===========================================================================
-- Research
-- ===========================================================================

CREATE TABLE research_packs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic TEXT NOT NULL,
    agent_task_id UUID REFERENCES agent_tasks(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE research_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pack_id UUID NOT NULL REFERENCES research_packs(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT,
    source_type VARCHAR(30) NOT NULL,
    summary TEXT,
    relevance_score FLOAT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_research_sources_pack ON research_sources(pack_id);
