ALTER TABLE source_records DROP CONSTRAINT source_records_entity_type_check;
ALTER TABLE source_records ADD CONSTRAINT source_records_entity_type_check
    CHECK (entity_type IN ('MOVIE','PERSON','ORGANIZATION','GENRE','COMPANY'));

CREATE UNIQUE INDEX evidence_records_identity_uq
    ON evidence_records(source_record_id, evidence_key, coalesce(locator, ''));
CREATE UNIQUE INDEX assertion_provenance_evidence_uq
    ON assertion_provenance(evidence_record_id) WHERE evidence_record_id IS NOT NULL;
CREATE UNIQUE INDEX movie_titles_assertion_uq
    ON movie_titles(movie_id, title, normalized_title, locale, title_type, provenance_id);
CREATE UNIQUE INDEX movie_facts_assertion_uq
    ON movie_fact_assertions(movie_id, fact_key, provenance_id);
CREATE UNIQUE INDEX person_names_assertion_uq
    ON person_names(person_id, normalized_name, locale, name_type, provenance_id);
CREATE UNIQUE INDEX movie_credits_assertion_uq
    ON movie_credits(movie_id, person_id, credit_type, job, coalesce(character_name, ''), coalesce(billing_order, -1), provenance_id);

ALTER TABLE movie_credits
    ADD COLUMN valid_from timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN valid_to timestamptz,
    ADD CONSTRAINT movie_credits_validity_check CHECK (valid_to IS NULL OR valid_to > valid_from);
ALTER TABLE movie_taxonomy_assertions
    ADD COLUMN valid_from timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN valid_to timestamptz,
    ADD CONSTRAINT movie_taxonomy_validity_check CHECK (valid_to IS NULL OR valid_to > valid_from);
ALTER TABLE movie_production_countries
    ADD COLUMN valid_from timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN valid_to timestamptz,
    ADD CONSTRAINT movie_production_country_validity_check CHECK (valid_to IS NULL OR valid_to > valid_from);
CREATE UNIQUE INDEX movie_credits_provider_current_uq
    ON movie_credits(movie_id, person_id, credit_type, job, coalesce(character_name, ''), coalesce(billing_order, -1))
    WHERE valid_to IS NULL;
CREATE UNIQUE INDEX movie_taxonomy_provider_current_uq
    ON movie_taxonomy_assertions(movie_id, taxonomy_term_id, provenance_id)
    WHERE valid_to IS NULL;
CREATE UNIQUE INDEX movie_production_country_provider_current_uq
    ON movie_production_countries(movie_id, country_code, provenance_id)
    WHERE valid_to IS NULL;

ALTER TABLE movie_credits DROP CONSTRAINT movie_credits_check;
ALTER TABLE movie_credits ADD CONSTRAINT movie_credits_character_nonblank_check
    CHECK (character_name IS NULL OR length(btrim(character_name)) > 0);

CREATE TABLE taxonomy_source_links (
    source_record_id uuid PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
    taxonomy_term_id uuid NOT NULL REFERENCES taxonomy_terms(id) ON DELETE CASCADE,
    linked_by_provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    linked_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (taxonomy_term_id, source_record_id)
);
CREATE INDEX taxonomy_source_links_term_idx ON taxonomy_source_links(taxonomy_term_id);

CREATE TABLE movie_external_identifiers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    identifier_type text NOT NULL CHECK (identifier_type ~ '^[a-z][a-z0-9_]*$'),
    external_id text NOT NULL CHECK (length(btrim(external_id)) > 0),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (identifier_type, external_id),
    UNIQUE (movie_id, identifier_type, external_id, provenance_id)
);
CREATE INDEX movie_external_identifiers_movie_idx ON movie_external_identifiers(movie_id);

CREATE TABLE production_companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE production_company_source_links (
    source_record_id uuid PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
    production_company_id uuid NOT NULL REFERENCES production_companies(id) ON DELETE CASCADE,
    linked_by_provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    UNIQUE (production_company_id, source_record_id)
);
CREATE INDEX production_company_source_links_company_idx ON production_company_source_links(production_company_id);
CREATE TABLE production_company_names (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    production_company_id uuid NOT NULL REFERENCES production_companies(id) ON DELETE CASCADE,
    name text NOT NULL CHECK (length(btrim(name)) > 0),
    normalized_name text NOT NULL CHECK (normalized_name = lower(btrim(normalized_name))),
    locale text NOT NULL DEFAULT 'und',
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    UNIQUE (production_company_id, normalized_name, locale, provenance_id)
);
CREATE TABLE movie_production_companies (
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    production_company_id uuid NOT NULL REFERENCES production_companies(id),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    PRIMARY KEY (movie_id, production_company_id, provenance_id)
);
CREATE INDEX movie_production_companies_company_idx ON movie_production_companies(production_company_id, movie_id);
