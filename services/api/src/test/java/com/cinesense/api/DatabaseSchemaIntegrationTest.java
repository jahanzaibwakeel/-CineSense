package com.cinesense.api;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
@SpringBootTest
class DatabaseSchemaIntegrationTest {
    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:0.8.7-pg17-bookworm"))
            .withDatabaseName("cinesense")
            .withUsername("cinesense")
            .withPassword("cinesense-test");

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }

    @Autowired
    JdbcTemplate jdbc;

    @Test
    void migrationsCreateExtensionsTablesAndSearchIndexes() {
        assertThat(jdbc.queryForObject("SELECT count(*) FROM flyway_schema_history WHERE success", Integer.class))
                .isEqualTo(12);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM pg_extension WHERE extname IN ('vector', 'pg_trgm')", Integer.class))
                .isEqualTo(2);
        assertThat(jdbc.queryForObject("SELECT to_regclass('movie_titles_normalized_idx') IS NOT NULL", Boolean.class))
                .isTrue();
        assertThat(jdbc.queryForObject("SELECT to_regclass('movie_semantic_documents_search_idx') IS NOT NULL", Boolean.class))
                .isTrue();
        assertThat(jdbc.queryForObject("SELECT to_regclass('ingestion_checkpoints') IS NOT NULL", Boolean.class)).isTrue();
        assertThat(jdbc.queryForObject("SELECT to_regclass('movie_text_assertions') IS NOT NULL", Boolean.class)).isTrue();
        assertThat(jdbc.queryForObject("SELECT to_regclass('identity_match_candidates') IS NOT NULL", Boolean.class)).isTrue();
    }

    @Test
    void provenanceAndNormalizedMovieClaimsCanBePersistedAndConstraintsApply() {
        UUID movieId = jdbc.queryForObject("INSERT INTO movies DEFAULT VALUES RETURNING id", UUID.class);
        UUID provenanceId = jdbc.queryForObject("INSERT INTO assertion_provenance(origin, review_state) "
                + "VALUES ('INTERNAL','ACCEPTED') RETURNING id", UUID.class);
        jdbc.update("INSERT INTO movie_titles(movie_id, title, normalized_title, locale, title_type, provenance_id) "
                + "VALUES (?, 'Arrival', 'arrival', 'en', 'PRIMARY', ?)", movieId, provenanceId);

        UUID categoryId = jdbc.queryForObject("SELECT id FROM taxonomy_categories WHERE category_key='theme'", UUID.class);
        UUID termId = jdbc.queryForObject("INSERT INTO taxonomy_terms(category_id, term_key, display_name) "
                + "VALUES (?, 'test-theme', 'Test theme') RETURNING id", UUID.class, categoryId);
        jdbc.update("INSERT INTO movie_taxonomy_assertions(movie_id, taxonomy_term_id, provenance_id, relevance) "
                + "VALUES (?, ?, ?, 0.8)", movieId, termId, provenanceId);

        UUID violenceId = jdbc.queryForObject("SELECT id FROM content_dimensions WHERE dimension_key='violence'", UUID.class);
        jdbc.update("INSERT INTO content_attribute_assertions(movie_id, content_dimension_id, intensity, provenance_id) "
                + "VALUES (?, ?, 'UNKNOWN', ?)", movieId, violenceId, provenanceId);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM content_attribute_assertions "
                + "WHERE movie_id=? AND intensity='UNKNOWN'", Integer.class, movieId)).isEqualTo(1);

        UUID sourceId = jdbc.queryForObject("INSERT INTO catalog_sources(source_key, display_name, source_type) "
                + "VALUES ('test-provider','Test Provider','INTERNAL') RETURNING id", UUID.class);
        jdbc.update("INSERT INTO source_records(catalog_source_id, entity_type, external_id) VALUES (?, 'MOVIE', 'x1')", sourceId);
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> jdbc.update(
                "INSERT INTO source_records(catalog_source_id, entity_type, external_id) VALUES (?, 'MOVIE', 'x1')", sourceId))
                .isInstanceOf(org.springframework.dao.DataIntegrityViolationException.class);
    }

    @Test
    void embeddingSpaceEnforcesItsDeclaredDimension() {
        UUID movieId = jdbc.queryForObject("INSERT INTO movies DEFAULT VALUES RETURNING id", UUID.class);
        UUID documentId = jdbc.queryForObject("INSERT INTO movie_semantic_documents(movie_id, template_version, "
                + "source_policy, document_text, content_sha256) VALUES (?, 'v1', 'PERMITTED', 'test', decode(repeat('ab', 32),'hex')) RETURNING id", UUID.class, movieId);
        UUID spaceId = jdbc.queryForObject("INSERT INTO embedding_spaces(provider, model_name, immutable_revision, "
                + "dimensions, template_version, similarity_metric) VALUES ('local','test','rev1',3,'v1','COSINE') RETURNING id", UUID.class);
        jdbc.update("INSERT INTO movie_embeddings(semantic_document_id, embedding_space_id, embedding_dimension, embedding) "
                + "VALUES (?, ?, 3, '[0.1,0.2,0.3]')", documentId, spaceId);

        org.assertj.core.api.Assertions.assertThatThrownBy(() -> jdbc.update(
                "INSERT INTO movie_embeddings(semantic_document_id, embedding_space_id, embedding_dimension, embedding) "
                        + "VALUES (?, ?, 3, '[0.1,0.2]')", documentId, spaceId))
                .isInstanceOf(org.springframework.dao.DataIntegrityViolationException.class);
    }
}
