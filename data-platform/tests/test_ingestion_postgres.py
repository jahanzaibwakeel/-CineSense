"""Real schema integration tests against the same PostgreSQL/pgvector image as API CI."""
from pathlib import Path

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

from data_platform.normalization.tmdb import normalize_movie
from data_platform.persistence.ingestion_repository import IngestionRepository


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "services" / "api" / "src" / "main" / "resources" / "db" / "migration"


@pytest.fixture(scope="module")
def db_connection():
    with PostgresContainer("pgvector/pgvector:0.8.7-pg17-bookworm") as postgres:
        dsn = postgres.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        with psycopg.connect(dsn, autocommit=True) as connection:
            for migration in sorted(MIGRATIONS.glob("V*.sql"),key=lambda path:int(path.name.split("__",1)[0][1:])):
                sql = migration.read_text(encoding="utf-8")
                # These versioned migrations contain no procedural dollar-quoted blocks.
                for statement in sql.split(";"):
                    if statement.strip():
                        connection.execute(statement)
        yield dsn


@pytest.fixture(autouse=True)
def isolated_catalog(db_connection):
    with psycopg.connect(db_connection) as connection:
        connection.execute("TRUNCATE movies,catalog_sources CASCADE")


def movie(title="A Film", overview="A sourced overview.", cast_name="A Person",provider_id=8800123):
    details={"id": provider_id,"title":title,"original_title":title,"release_date":"2024-02-03","original_language":"en","runtime":101,"adult":False,
             "status":"Released","overview":overview,"tagline":"A sourced tagline.","genres":[{"id":12,"name":"Adventure"}],
             "production_countries":[{"iso_3166_1":"US","name":"United States"}],"production_companies":[{"id":9901,"name":"CineSense Test Fixture Studio"}]}
    credits={"cast":[{"id":771123,"name":cast_name,"character":"The lead","order":0}],"crew":[{"id":771124,"name":"A Director","job":"Director","department":"Directing"}]}
    return normalize_movie(details,credits,{"imdb_id":"tt1234567"},requested_locale="en-US")[0]


def test_repeated_ingestion_is_idempotent_and_preserves_evidence_and_identity(db_connection):
    with psycopg.connect(db_connection) as conn:
        repo=IngestionRepository(conn)
        with conn.transaction():
            source=repo.ensure_source(policy="PERMITTED",attribution="TMDB attribution",terms_url="https://example.test/terms")
            run=repo.create_run(source,"DISCOVER",{"limit":1})
            assert repo.ingest_movie(source,movie()) == "inserted"
            repo.save_checkpoint(source,"discover::en-US",2,run,"8800123")
            repo.add_quality_metrics(run,{"records_discovered":1,"records_accepted":1})
        with conn.transaction():
            assert repo.ingest_movie(source,movie()) == "skipped"
        assert conn.execute("SELECT count(*) FROM movies").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM movie_source_links").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM movie_text_assertions WHERE valid_to IS NULL").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM movie_credits WHERE valid_to IS NULL").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM person_source_links").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM taxonomy_source_links").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM movie_production_companies WHERE valid_to IS NULL").fetchone()[0] == 1
        assert conn.execute("SELECT cursor_state->>'page' FROM ingestion_checkpoints").fetchone()[0] == "2"
        assert conn.execute("SELECT metric_value FROM ingestion_quality_metrics WHERE metric_key='records_accepted'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM assertion_provenance WHERE origin='PROVIDER'").fetchone()[0] > 5
        assert conn.execute("SELECT count(*) FROM evidence_records WHERE excerpt IS NOT NULL").fetchone()[0] == 0


def test_changed_provider_revision_supersedes_text_and_current_credit(db_connection):
    with psycopg.connect(db_connection) as conn:
        repo=IngestionRepository(conn)
        with conn.transaction():
            source=repo.ensure_source(policy="PERMITTED",attribution="TMDB attribution",terms_url="https://example.test/terms")
            repo.ingest_movie(source,movie())
        with conn.transaction():
            repo.ingest_movie(source,movie(title="A New Film",overview="Updated sourced overview.",cast_name="Another Person"))
        assert conn.execute("SELECT count(*) FROM movies").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM movie_text_assertions WHERE valid_to IS NULL").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM movie_text_assertions WHERE valid_to IS NOT NULL").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM movie_credits WHERE valid_to IS NULL").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM movie_credits WHERE valid_to IS NOT NULL").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM movie_production_companies WHERE valid_to IS NULL").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM movie_production_companies WHERE valid_to IS NOT NULL").fetchone()[0] == 1


def test_transaction_rollback_includes_movie_and_assertions(db_connection):
    with psycopg.connect(db_connection) as conn:
        repo=IngestionRepository(conn)
        with pytest.raises(RuntimeError):
            with conn.transaction():
                source=repo.ensure_source(policy="PERMITTED",attribution="TMDB attribution",terms_url="https://example.test/terms")
                repo.ingest_movie(source,movie())
                raise RuntimeError("simulated interruption")
        assert conn.execute("SELECT count(*) FROM movies").fetchone()[0] == 0


def test_catalog_source_policy_must_be_explicit(db_connection):
    with psycopg.connect(db_connection) as conn:
        with pytest.raises(ValueError,match="explicitly PERMITTED"):
            IngestionRepository(conn).ensure_source(policy="UNKNOWN",attribution="",terms_url="")


def test_quarantined_failure_can_be_retried_and_resolved(db_connection):
    with psycopg.connect(db_connection) as conn:
        repo=IngestionRepository(conn)
        with conn.transaction():
            source=repo.ensure_source(policy="PERMITTED",attribution="TMDB attribution",terms_url="https://example.test/terms")
            run=repo.create_run(source,"DISCOVER",{"limit":1})
            conn.execute("INSERT INTO ingestion_failures(run_id,catalog_source_id,provider_external_id,processing_stage,failure_category,error_summary,retryable) VALUES (%s,%s,'8800123','details','PROVIDER','temporary provider error',true)",(run,source))
        with conn.transaction():
            conn.execute("UPDATE ingestion_failures SET attempt_count=attempt_count+1,status='RESOLVED',resolved_at=now() WHERE catalog_source_id=%s AND provider_external_id='8800123' AND status='OPEN'",(source,))
        status,attempts=conn.execute("SELECT status,attempt_count FROM ingestion_failures").fetchone()
        assert (status,attempts)==("RESOLVED",2)


def test_similar_title_year_creates_review_candidate_without_merging(db_connection):
    with psycopg.connect(db_connection) as conn:
        repo=IngestionRepository(conn)
        with conn.transaction():
            source=repo.ensure_source(policy="PERMITTED",attribution="TMDB attribution",terms_url="https://example.test/terms")
            repo.ingest_movie(source,movie())
            preview=repo.preview_movie(movie(title="A Film!",provider_id=8800124))
            assert preview["would"] == "insert" and len(preview["duplicate_candidates"]) == 1
            assert conn.execute("SELECT count(*) FROM movies").fetchone()[0] == 1
            repo.ingest_movie(source,movie(title="A Film!",provider_id=8800124))
        assert conn.execute("SELECT count(*) FROM movies").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM identity_match_candidates WHERE review_status='REVIEW_REQUIRED'").fetchone()[0] == 1
