CREATE TABLE catalog_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key text NOT NULL UNIQUE CHECK (source_key ~ '^[a-z0-9][a-z0-9._-]*$'),
    display_name text NOT NULL,
    source_type text NOT NULL CHECK (source_type IN ('OFFICIAL_PROVIDER','PUBLIC_DATASET','EDITORIAL','INTERNAL','USER')),
    base_uri text,
    attribution text,
    license_name text,
    terms_uri text,
    content_policy text NOT NULL DEFAULT 'UNKNOWN' CHECK (content_policy IN ('PERMITTED','REFERENCE_ONLY','PROHIBITED','UNKNOWN')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE source_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_source_id uuid NOT NULL REFERENCES catalog_sources(id),
    entity_type text NOT NULL CHECK (entity_type IN ('MOVIE','PERSON','ORGANIZATION')),
    external_id text NOT NULL,
    source_uri text,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    source_revision text,
    payload_sha256 bytea CHECK (payload_sha256 IS NULL OR octet_length(payload_sha256) = 32),
    UNIQUE (catalog_source_id, entity_type, external_id)
);
CREATE INDEX source_records_source_entity_idx ON source_records(catalog_source_id, entity_type);

CREATE TABLE evidence_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_record_id uuid NOT NULL REFERENCES source_records(id),
    evidence_key text NOT NULL,
    locator text,
    excerpt text,
    observed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_record_id, evidence_key, locator)
);
CREATE INDEX evidence_records_source_record_idx ON evidence_records(source_record_id);

CREATE TABLE model_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    model_name text NOT NULL,
    immutable_revision text NOT NULL,
    task text NOT NULL,
    runtime_version text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, model_name, immutable_revision, task)
);

CREATE TABLE assertion_provenance (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_record_id uuid REFERENCES evidence_records(id),
    model_version_id uuid REFERENCES model_versions(id),
    origin text NOT NULL CHECK (origin IN ('PROVIDER','DATASET','EDITORIAL','MODEL_INFERENCE','USER','INTERNAL')),
    review_state text NOT NULL DEFAULT 'UNREVIEWED' CHECK (review_state IN ('UNREVIEWED','ACCEPTED','REJECTED','DISPUTED')),
    confidence numeric(5,4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    prompt_version text,
    reviewer text,
    asserted_at timestamptz NOT NULL DEFAULT now(),
    supersedes_id uuid REFERENCES assertion_provenance(id),
    CHECK (evidence_record_id IS NOT NULL OR model_version_id IS NOT NULL OR origin IN ('USER','INTERNAL'))
);
CREATE INDEX assertion_provenance_evidence_idx ON assertion_provenance(evidence_record_id);
CREATE INDEX assertion_provenance_model_idx ON assertion_provenance(model_version_id);
