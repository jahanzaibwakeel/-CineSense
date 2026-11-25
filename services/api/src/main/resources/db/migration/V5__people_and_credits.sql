CREATE TABLE people (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE person_names (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    name text NOT NULL CHECK (length(btrim(name)) > 0),
    normalized_name text NOT NULL CHECK (normalized_name = lower(btrim(normalized_name))),
    locale text NOT NULL DEFAULT 'und',
    name_type text NOT NULL CHECK (name_type IN ('PRIMARY','ALTERNATIVE','TRANSLITERATED')),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX person_names_primary_locale_uq ON person_names(person_id, locale) WHERE name_type = 'PRIMARY';
CREATE INDEX person_names_person_idx ON person_names(person_id);
CREATE INDEX person_names_normalized_idx ON person_names USING gin(normalized_name gin_trgm_ops);

CREATE TABLE person_source_links (
    source_record_id uuid PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    linked_by_provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    UNIQUE (person_id, source_record_id)
);
CREATE INDEX person_source_links_person_idx ON person_source_links(person_id);

CREATE TABLE movie_credits (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES people(id),
    credit_type text NOT NULL CHECK (credit_type IN ('CAST','CREW')),
    job text NOT NULL,
    character_name text,
    billing_order integer CHECK (billing_order IS NULL OR billing_order >= 0),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((credit_type = 'CAST' AND character_name IS NOT NULL) OR credit_type = 'CREW')
);
CREATE INDEX movie_credits_movie_idx ON movie_credits(movie_id, credit_type, billing_order);
CREATE INDEX movie_credits_person_idx ON movie_credits(person_id, movie_id);
