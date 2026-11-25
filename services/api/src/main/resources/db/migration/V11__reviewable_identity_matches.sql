CREATE TABLE identity_match_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incoming_source_record_id uuid NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
    candidate_movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    match_score numeric(5,4) NOT NULL CHECK (match_score BETWEEN 0 AND 1),
    match_signals jsonb NOT NULL DEFAULT '{}'::jsonb,
    review_status text NOT NULL DEFAULT 'REVIEW_REQUIRED'
        CHECK (review_status IN ('REVIEW_REQUIRED','CONFIRMED','DISMISSED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    UNIQUE (incoming_source_record_id, candidate_movie_id)
);
CREATE INDEX identity_match_candidates_review_idx ON identity_match_candidates(review_status, match_score DESC);
