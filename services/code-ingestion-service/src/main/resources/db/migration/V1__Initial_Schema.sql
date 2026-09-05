CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE repository (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    url VARCHAR(255),
    description TEXT,
    language VARCHAR(50),
    stars INT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE document (
    id UUID PRIMARY KEY,
    repository_id UUID NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
    path VARCHAR(1000) NOT NULL,
    type VARCHAR(50),
    language VARCHAR(50),
    content TEXT,
    ingested_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE chunk (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT,
    token_count INT,
    embedding_vector vector(1536)
);

-- B-Tree Indexes for fast lookups
CREATE INDEX idx_repository_name ON repository(name);
CREATE INDEX idx_document_path ON document(path);
CREATE INDEX idx_document_repository_id ON document(repository_id);
CREATE INDEX idx_chunk_document_id ON chunk(document_id);

-- GIN Indexes for Native Full-Text Search
CREATE INDEX idx_document_content_fts ON document USING GIN (to_tsvector('english', content));
CREATE INDEX idx_chunk_content_fts ON chunk USING GIN (to_tsvector('english', content));
