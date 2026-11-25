# CineSense project progress

Updated: 2026-11-25

## Phase 2 — complete

| Area | Status | Evidence |
|---|---|---|
| Repository and monorepo inspection | Complete | Git repository and requested `origin`; JavaScript Next workspace, Spring API, FastAPI service, Compose, CI and docs inspected. Working files preserved. |
| Runnable foundation | Complete | Web landing foundation; Spring and FastAPI health routes; local PostgreSQL Compose service; environment example and ignore rules. |
| Architecture reconciliation | Complete | [ARCHITECTURE.md](../ARCHITECTURE.md) records running versus planned boundaries, query/evidence contract, model/version lifecycle and CI/ML CI flows. |
| Dataset/source research | Complete for Phase 1 | [DATA_SOURCES.md](../DATA_SOURCES.md) documents TMDB, CMU, Wikidata and MovieLens coverage, source fields, terms, limits and a staged recommendation. No dataset downloaded. |
| Development and API docs | Complete for current foundation | [DEVELOPMENT_SETUP.md](../DEVELOPMENT_SETUP.md), [ENVIRONMENT_VARIABLES.md](../ENVIRONMENT_VARIABLES.md), [API_DOCUMENTATION.md](../API_DOCUMENTATION.md). |
| Phase 2 database work | Complete | PostgreSQL 17 + pgvector 0.8.7, Flyway V1–V8, JPA schema validation, Testcontainers integration coverage, and database readiness health. |
| Schema/data dictionary | Implemented | [DATA_DICTIONARY.md](../DATA_DICTIONARY.md): normalized entity graph, source/evidence lineage, constraints, indexes, vector versioning, and tradeoffs. |
| Model/data implementation | Not started by design | No movie data, weights, generated embeddings, or fake inference. |
| Later product/MLOps requirements | Not started | No auth, search/reranking, model stack, DVC, MLflow, Prefect, or monitoring yet. These remain scoped to later phases. |

## Phase 3 — complete (live TMDB use unverified)

| Area | Status | Evidence |
|---|---|---|
| Provider adapter and HTTP reliability | Complete | Python provider contract and TMDB HTTPX adapter support discover, search, details, credits, genres, external IDs, pagination, bearer/API-key auth, bounded retries, Retry-After, and 4 req/s pacing. Mocked tests cover successful, empty, malformed, auth, 429, and 500 responses. |
| Rights/source-policy gate | Complete | Provider requests require explicit scope, terms, attribution statement, and official-logo acknowledgements; persistence additionally requires `--execute`, `TMDB_SOURCE_POLICY=PERMITTED`, and persistence acknowledgement. Default remains closed. |
| Normalization and deduplication | Complete | Pydantic canonical models validate metadata; TMDB IDs are stable identity keys; repeated revisions are idempotent; similar title/year candidates receive scores and require human review, never auto-merge. |
| Persistence and recovery | Complete | Flyway V9–V12 add canonical text assertions, runs/checkpoints/failures/quality metrics, idempotency and relationship history, plus review candidates. Python repository persists field-level evidence/provenance and page checkpoint atomically. |
| Integration and security tests | Complete | Python Testcontainers tests exercise migrations, idempotency, movie text, people/credits, genre mapping, checkpoints, policy fail-closed behavior, fuzzy review candidates and rollback. Dry-run test verifies no database connection is opened. |
| Live provider import | Not run | No TMDB credential, logo acknowledgement, or legal retention review was supplied. No provider data was downloaded or imported. |

See [data-platform/README.md](../data-platform/README.md), [ingestion diagrams](diagrams/INGESTION_ARCHITECTURE.md), and migration descriptions in [DATA_DICTIONARY.md](../DATA_DICTIONARY.md).

## Verification — passed 2026-11-24

- `npm ci` — passed from the checked-in lockfile.
- `npm run build` — passed.
- `npm run lint` — passed.
- `npm audit --audit-level=moderate` — passed; 0 vulnerabilities after updating Next.js to 16.4.6.
- Python bytecode compilation and `services/ai/.venv/Scripts/python.exe -m unittest discover -s services/ai/tests -v` — passed (1 health test).
- `docker compose config --quiet` — passed.
- `mvn -B -f services/api/pom.xml verify` — passed, including four API tests; Testcontainers started PostgreSQL 17.12 with pgvector and all eight migrations applied successfully.
- Compose PostgreSQL container — healthy with pgvector 0.8.7; API startup applied all eight migrations and `/actuator/health` reported `UP` with database `UP`.
- `npm run lint` and `npm run build` — passed after rerunning the build with required Windows workspace write access.
- TypeScript source/config audit — no `.ts`, `.tsx`, `tsconfig.json`, or `next-env.d.ts` files found.

The web build uses Next's supported Webpack compiler because its default Turbopack/PostCSS child process exited in this Windows environment. The production build and lint pass with the Webpack configuration.

## Phase 3 verification — passed 2026-11-25

- `python -m pytest data-platform/tests -q` — passed (19 tests), including real PostgreSQL 17 + pgvector Testcontainers integration.
- `python -m compileall -q data-platform/src data-platform/tests` — passed.
- `npm run lint` — passed.
- `npm.cmd run build` — passed with elevated Windows workspace write access.
- `mvn -f services/api/pom.xml verify` — passed (4 tests); final run applies all 12 migrations and validates the schema using PostgreSQL 17.12 + pgvector.
- TMDB live requests — not run; no token or approved terms/storage policy was configured.

## Phase 1 conclusions

- TMDB is the leading app-catalog candidate, conditional on accepting its developer terms, attribution requirements, permitted caching/derived use and a non-commercial project scope. A future commercial use requires separate permission/license.
- MovieLens is a separate recommendation-evaluation candidate, not a factual movie catalog. Terms vary by release; the exact release's README controls.
- Wikidata can supplement sourced structured facts and identifiers, but is incomplete and does not grant rights to linked source content.
- CMU is a possible plot research source, but its ShareAlike terms and source lineage need to remain explicit.
- No movie dataset has been selected or downloaded; Phase 3 must choose a source and validate its terms before any import. No fabricated titles or claims are present.

## Next phase — Phase 4

Phase 4 may begin after review of the Phase 3 implementation. AI enrichment, embeddings, model downloads, and retrieval remain unimplemented. Review current source terms and retention policy before enabling any live provider persistence. The `ja` two-character title-search example may warrant a dedicated n-gram index only after catalog size and latency are measured.
