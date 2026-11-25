# Database

CineSense uses PostgreSQL 17 and pgvector 0.8.7. Flyway owns schema changes; migrations live in `services/api/src/main/resources/db/migration` and run at API startup. Hibernate validates the migrated schema and never creates or alters tables. The relational model and migration sequence are in [DATA_DICTIONARY.md](../DATA_DICTIONARY.md).

## Local operations (PowerShell)

```powershell
docker compose up -d postgres
docker compose ps
docker compose logs -f postgres
docker compose down
```

Compose reads the root `.env`; defaults are for local development only. The named `postgres_data` volume retains data across `docker compose down`. To recreate an empty local database, `docker compose down --volumes` deletes that volume and all its data.

Check readiness and migrations:

```powershell
docker compose exec postgres pg_isready -U cinesense -d cinesense
docker compose exec postgres psql -U cinesense -d cinesense -c "SELECT installed_rank, version, description, success FROM flyway_schema_history ORDER BY installed_rank;"
docker compose exec postgres psql -U cinesense -d cinesense -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pg_trgm');"
```

Flyway upgrades run automatically when the API starts. Add a new `Vn__description.sql` migration; do not edit an applied migration. Review the schema using Flyway validation and the database integration tests before committing.

V9–V12 add ingestion run/checkpoint/failure state, canonical overview/tagline claims, provider identity/idempotency support, external IDs, genre/company links, temporal relationship claims, and review-only fuzzy identity candidates. The Python data-platform uses these same Flyway migrations; it does not create a second schema or migration track. See [data-platform documentation](../data-platform/README.md).

For a development backup:

```powershell
docker compose exec -T postgres pg_dump -U cinesense -d cinesense -Fc -f /tmp/cinesense.dump
docker compose cp postgres:/tmp/cinesense.dump .\cinesense-local.dump
```

Backups can contain user or licensed-source data. Keep them outside Git and handle them under the source's retention terms.
