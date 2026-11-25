CREATE TABLE content_dimensions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dimension_key text NOT NULL UNIQUE CHECK (dimension_key ~ '^[a-z][a-z0-9_]*$'),
    display_name text NOT NULL,
    description text,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO content_dimensions(dimension_key, display_name, description) VALUES
('nudity','Nudity','Depicted nudity.'),
('sexual_content','Sexual content','Sexual content, distinct from nudity.'),
('sexual_violence','Sexual violence','Sexual violence and coercion.'),
('violence','Violence','Depicted physical violence.'),
('gore','Gore','Graphic injury or gore.'),
('language','Language','Strong or potentially offensive language.'),
('drug_use','Drug use','Depicted substance use.'),
('psychological_intensity','Psychological intensity','Psychological distress or intensity.'),
('horror_intensity','Horror intensity','Horror imagery or suspense intensity.');

CREATE TABLE content_attribute_assertions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    content_dimension_id uuid NOT NULL REFERENCES content_dimensions(id),
    intensity text NOT NULL CHECK (intensity IN ('NONE','MILD','MODERATE','STRONG','UNKNOWN')),
    notes text,
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    asserted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (movie_id, content_dimension_id, provenance_id)
);
CREATE INDEX content_attribute_movie_dimension_idx ON content_attribute_assertions(movie_id, content_dimension_id);
CREATE INDEX content_attribute_dimension_movie_idx ON content_attribute_assertions(content_dimension_id, movie_id);

CREATE TABLE movie_certifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    region_code text NOT NULL CHECK (region_code = upper(region_code) AND length(region_code) BETWEEN 2 AND 6),
    certification text NOT NULL,
    source_record_id uuid REFERENCES source_records(id),
    provenance_id uuid NOT NULL REFERENCES assertion_provenance(id),
    effective_date date,
    UNIQUE (movie_id, region_code, certification, provenance_id)
);
CREATE INDEX movie_certifications_region_idx ON movie_certifications(region_code, certification, movie_id);
