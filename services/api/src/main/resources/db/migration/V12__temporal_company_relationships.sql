ALTER TABLE movie_production_companies
    ADD COLUMN valid_from timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN valid_to timestamptz,
    ADD CONSTRAINT movie_production_company_validity_check CHECK (valid_to IS NULL OR valid_to > valid_from);
CREATE UNIQUE INDEX movie_production_company_current_uq
    ON movie_production_companies(movie_id, production_company_id, provenance_id)
    WHERE valid_to IS NULL;
