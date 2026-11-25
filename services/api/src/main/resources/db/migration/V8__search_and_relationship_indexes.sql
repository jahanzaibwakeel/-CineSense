ALTER TABLE movie_semantic_documents
    ADD COLUMN search_vector tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', coalesce(document_text, ''))) STORED;
CREATE INDEX movie_semantic_documents_search_idx ON movie_semantic_documents USING gin(search_vector);
CREATE INDEX movie_titles_movie_locale_idx ON movie_titles(movie_id, locale);
CREATE INDEX movie_titles_provenance_idx ON movie_titles(provenance_id);
CREATE INDEX movie_fact_assertions_validity_idx ON movie_fact_assertions(movie_id, valid_to) WHERE valid_to IS NULL;
CREATE INDEX movie_taxonomy_provenance_idx ON movie_taxonomy_assertions(provenance_id);
CREATE INDEX movie_credits_provenance_idx ON movie_credits(provenance_id);
CREATE INDEX content_attribute_provenance_idx ON content_attribute_assertions(provenance_id);
CREATE INDEX assertion_provenance_review_idx ON assertion_provenance(review_state, asserted_at DESC);
