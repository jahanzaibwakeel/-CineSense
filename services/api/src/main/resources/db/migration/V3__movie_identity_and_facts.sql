CREATE TABLE movies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz
);

CREATE TABLE movie_titles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    title text NOT NULL CHECK (length(btrim(title)) > 0),
    normalized_title text NOT NULL CHECK (normalized_title = lower(btrim(normalized_title))),
    locale text NOT NULL DEFAULT 'und',
    title_type text NOT NULL CHECK (title_type IN ('PRIMARY','ORIGINAL','ALTERNATIVE','TRANSLITERATED')),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX movie_titles_primary_locale_uq ON movie_titles(movie_id, locale) WHERE title_type = 'PRIMARY';
CREATE INDEX movie_titles_movie_idx ON movie_titles(movie_id);
CREATE INDEX movie_titles_normalized_idx ON movie_titles USING gin(normalized_title gin_trgm_ops);

CREATE TABLE movie_source_links (
    source_record_id uuid PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    linked_by_provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    linked_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (movie_id, source_record_id)
);
CREATE INDEX movie_source_links_movie_idx ON movie_source_links(movie_id);

CREATE TABLE movie_fact_assertions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    fact_key text NOT NULL CHECK (fact_key IN ('RELEASE_DATE','RUNTIME_MINUTES','ORIGINAL_LANGUAGE','ADULT_CONTENT','STATUS','BUDGET','REVENUE')),
    value_text text,
    value_integer bigint,
    value_numeric numeric(18,2),
    value_boolean boolean,
    value_date date,
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    CHECK (num_nonnulls(value_text, value_integer, value_numeric, value_boolean, value_date) = 1),
    CHECK (CASE fact_key
        WHEN 'RELEASE_DATE' THEN value_date IS NOT NULL
        WHEN 'RUNTIME_MINUTES' THEN coalesce(value_integer > 0, false)
        WHEN 'ADULT_CONTENT' THEN value_boolean IS NOT NULL
        WHEN 'BUDGET' THEN coalesce(value_numeric >= 0, false)
        WHEN 'REVENUE' THEN coalesce(value_numeric >= 0, false)
        WHEN 'ORIGINAL_LANGUAGE' THEN value_text IS NOT NULL
        WHEN 'STATUS' THEN value_text IS NOT NULL
        ELSE false
    END)
);
CREATE INDEX movie_fact_assertions_movie_fact_idx ON movie_fact_assertions(movie_id, fact_key, valid_from DESC);
CREATE INDEX movie_fact_assertions_provenance_idx ON movie_fact_assertions(provenance_id);

CREATE TABLE movie_production_countries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    country_code char(2) NOT NULL CHECK (country_code = upper(country_code)),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    UNIQUE (movie_id, country_code, provenance_id)
);
CREATE INDEX movie_production_countries_movie_idx ON movie_production_countries(movie_id);
