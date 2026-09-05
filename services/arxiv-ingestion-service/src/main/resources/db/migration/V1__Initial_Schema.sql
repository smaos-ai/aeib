-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arxiv_id VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(1024) NOT NULL,
    abstract TEXT NOT NULL,
    published_date TIMESTAMP NOT NULL,
    source_url VARCHAR(512) NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'cs.AI',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Full-text search vector (indexed)
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', title), 'A') ||
        setweight(to_tsvector('english', abstract), 'B')
    ) STORED
);

-- Index for full-text search
CREATE INDEX idx_documents_search_vector ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_arxiv_id ON documents(arxiv_id);
CREATE INDEX idx_documents_published_date ON documents(published_date DESC);
CREATE INDEX idx_documents_category ON documents(category);

-- Authors table
CREATE TABLE authors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(512) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_authors_name ON authors(name);

-- Join table for many-to-many relationship
CREATE TABLE document_authors (
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    author_position INT NOT NULL,
    PRIMARY KEY (document_id, author_id)
);

CREATE INDEX idx_document_authors_author_id ON document_authors(author_id);
CREATE INDEX idx_document_authors_position ON document_authors(document_id, author_position);

-- Ingestion job tracking
CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    papers_fetched INT DEFAULT 0,
    papers_inserted INT DEFAULT 0,
    papers_skipped INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ingestion_jobs_status ON ingestion_jobs(status);
CREATE INDEX idx_ingestion_jobs_created_at ON ingestion_jobs(created_at DESC);
