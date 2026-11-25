CREATE TABLE movie_semantic_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    template_version text NOT NULL,
    document_locale text NOT NULL DEFAULT 'en',
    source_policy text NOT NULL CHECK (source_policy IN ('PERMITTED','REFERENCE_ONLY','UNKNOWN')),
    document_text text,
    content_sha256 bytea NOT NULL CHECK (octet_length(content_sha256) = 32),
    generated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((source_policy = 'PERMITTED' AND document_text IS NOT NULL)
        OR (source_policy IN ('REFERENCE_ONLY','UNKNOWN') AND document_text IS NULL)),
    UNIQUE (movie_id, template_version, document_locale, content_sha256)
);
CREATE INDEX movie_semantic_documents_movie_idx ON movie_semantic_documents(movie_id, generated_at DESC);

CREATE TABLE movie_semantic_document_evidence (
    semantic_document_id uuid NOT NULL REFERENCES movie_semantic_documents(id) ON DELETE CASCADE,
    evidence_record_id uuid NOT NULL REFERENCES evidence_records(id),
    PRIMARY KEY (semantic_document_id, evidence_record_id)
);
CREATE INDEX semantic_document_evidence_evidence_idx ON movie_semantic_document_evidence(evidence_record_id);

CREATE TABLE embedding_spaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    model_name text NOT NULL,
    immutable_revision text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions BETWEEN 1 AND 16000),
    instruction_version text NOT NULL DEFAULT 'none',
    template_version text NOT NULL,
    similarity_metric text NOT NULL CHECK (similarity_metric IN ('COSINE','INNER_PRODUCT','L2')),
    lifecycle_state text NOT NULL DEFAULT 'PLANNED' CHECK (lifecycle_state IN ('PLANNED','ACTIVE','RETIRED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, model_name, immutable_revision, dimensions, instruction_version, template_version),
    UNIQUE (id, dimensions)
);

CREATE TABLE movie_embeddings (
    semantic_document_id uuid NOT NULL REFERENCES movie_semantic_documents(id) ON DELETE CASCADE,
    embedding_space_id uuid NOT NULL,
    embedding_dimension integer NOT NULL,
    embedding vector NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (semantic_document_id, embedding_space_id),
    FOREIGN KEY (embedding_space_id, embedding_dimension) REFERENCES embedding_spaces(id, dimensions),
    CHECK (vector_dims(embedding) = embedding_dimension)
);
CREATE INDEX movie_embeddings_space_idx ON movie_embeddings(embedding_space_id, semantic_document_id);
