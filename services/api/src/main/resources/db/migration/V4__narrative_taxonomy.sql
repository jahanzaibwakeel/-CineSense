CREATE TABLE taxonomy_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_key text NOT NULL UNIQUE CHECK (category_key ~ '^[a-z][a-z0-9_]*$'),
    display_name text NOT NULL,
    description text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE taxonomy_terms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id uuid NOT NULL REFERENCES taxonomy_categories(id),
    term_key text NOT NULL CHECK (term_key ~ '^[a-z0-9][a-z0-9._-]*$'),
    display_name text NOT NULL,
    description text,
    parent_term_id uuid REFERENCES taxonomy_terms(id),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (category_id, term_key),
    UNIQUE (category_id, id),
    CHECK (parent_term_id IS NULL OR parent_term_id <> id)
);
CREATE INDEX taxonomy_terms_parent_idx ON taxonomy_terms(parent_term_id);

INSERT INTO taxonomy_categories(category_key, display_name, description) VALUES
('genre','Genre','Conventional market and catalog genre.'),
('theme','Theme','Recurring idea or subject explored by a film.'),
('activity','Activity','Prominent activity or setting relevant to discovery.'),
('relationship_dynamic','Relationship dynamic','Central interpersonal relationship pattern.'),
('plot_element','Plot element','High-level narrative device or premise.'),
('narrative_trait','Narrative trait','Structure or storytelling characteristic.'),
('psychological_element','Psychological element','Psychological subject or experience depicted.');

CREATE TABLE movie_taxonomy_assertions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    taxonomy_term_id uuid NOT NULL REFERENCES taxonomy_terms(id),
    polarity text NOT NULL DEFAULT 'PRESENT' CHECK (polarity IN ('PRESENT','ABSENT','UNCERTAIN')),
    relevance numeric(5,4) CHECK (relevance IS NULL OR relevance BETWEEN 0 AND 1),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    asserted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (movie_id, taxonomy_term_id, provenance_id)
);
CREATE INDEX movie_taxonomy_term_movie_idx ON movie_taxonomy_assertions(taxonomy_term_id, movie_id);
CREATE INDEX movie_taxonomy_movie_idx ON movie_taxonomy_assertions(movie_id);
