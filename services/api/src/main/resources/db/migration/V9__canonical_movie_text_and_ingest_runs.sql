CREATE TABLE movie_text_assertions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    text_type text NOT NULL CHECK (text_type IN ('OVERVIEW','TAGLINE')),
    locale text NOT NULL DEFAULT 'und',
    text_value text NOT NULL CHECK (length(btrim(text_value)) > 0),
    content_sha256 bytea NOT NULL CHECK (octet_length(content_sha256) = 32),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    source_asserted_at timestamptz NOT NULL,
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    UNIQUE (movie_id, text_type, locale, provenance_id)
);
CREATE INDEX movie_text_assertions_current_idx ON movie_text_assertions(movie_id, text_type, locale, valid_from DESC)
    WHERE valid_to IS NULL;
CREATE INDEX movie_text_assertions_provenance_idx ON movie_text_assertions(provenance_id);

CREATE TABLE ingestion_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_source_id uuid NOT NULL REFERENCES catalog_sources(id),
    job_type text NOT NULL CHECK (job_type IN ('DISCOVER','SEARCH','GENRES','RETRY_FAILURES')),
    status text NOT NULL CHECK (status IN ('RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    requested_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    pages_processed integer NOT NULL DEFAULT 0 CHECK (pages_processed >= 0),
    records_discovered integer NOT NULL DEFAULT 0 CHECK (records_discovered >= 0),
    records_inserted integer NOT NULL DEFAULT 0 CHECK (records_inserted >= 0),
    records_updated integer NOT NULL DEFAULT 0 CHECK (records_updated >= 0),
    records_skipped integer NOT NULL DEFAULT 0 CHECK (records_skipped >= 0),
    records_failed integer NOT NULL DEFAULT 0 CHECK (records_failed >= 0),
    failure_summary text,
    CHECK ((status = 'RUNNING' AND finished_at IS NULL) OR (status <> 'RUNNING' AND finished_at IS NOT NULL))
);
CREATE INDEX ingestion_runs_source_started_idx ON ingestion_runs(catalog_source_id, started_at DESC);
CREATE INDEX ingestion_runs_status_idx ON ingestion_runs(status, started_at DESC);

CREATE TABLE ingestion_checkpoints (
    catalog_source_id uuid NOT NULL REFERENCES catalog_sources(id),
    job_key text NOT NULL,
    cursor_state jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_successful_external_id text,
    run_id uuid REFERENCES ingestion_runs(id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (catalog_source_id, job_key)
);
CREATE INDEX ingestion_checkpoints_run_idx ON ingestion_checkpoints(run_id);

CREATE TABLE ingestion_failures (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
    catalog_source_id uuid NOT NULL REFERENCES catalog_sources(id),
    provider_external_id text,
    processing_stage text NOT NULL,
    failure_category text NOT NULL,
    error_summary text NOT NULL CHECK (length(error_summary) <= 1000),
    retryable boolean NOT NULL,
    attempt_count integer NOT NULL DEFAULT 1 CHECK (attempt_count > 0),
    status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RESOLVED','IGNORED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz
);
CREATE INDEX ingestion_failures_retry_idx ON ingestion_failures(catalog_source_id, created_at)
    WHERE status = 'OPEN' AND retryable;
CREATE INDEX ingestion_failures_run_idx ON ingestion_failures(run_id, created_at);
CREATE INDEX ingestion_failures_external_idx ON ingestion_failures(catalog_source_id, provider_external_id)
    WHERE provider_external_id IS NOT NULL;

CREATE TABLE ingestion_quality_metrics (
    run_id uuid NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
    metric_key text NOT NULL,
    metric_value bigint NOT NULL CHECK (metric_value >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, metric_key)
);

ALTER TABLE movie_semantic_documents
    ADD COLUMN stale boolean NOT NULL DEFAULT false,
    ADD COLUMN stale_marked_at timestamptz,
    ADD COLUMN stale_reason text;
