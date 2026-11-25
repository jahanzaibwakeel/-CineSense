# Environment variables

Copy `.env.example` to an ignored `.env` for Docker Compose. Compose reads PostgreSQL settings from that file. Spring reads datasource settings and `API_PORT` from its process environment. The Next.js app and FastAPI health foundation do not currently consume a root `.env` file.

| Variable | Used by | Required now | Notes |
|---|---|---:|---|
| `POSTGRES_DB` | Compose PostgreSQL | No | Default `cinesense`. |
| `POSTGRES_USER` | Compose PostgreSQL | No | Default `cinesense`; development only. |
| `POSTGRES_PASSWORD` | Compose PostgreSQL | No | Replace the example value for local use; never reuse it outside local development. |
| `POSTGRES_PORT` | Compose | No | Host port; container remains on 5432. Example uses 55432 to avoid collisions with a local PostgreSQL installation. |
| `SPRING_DATASOURCE_URL` | Spring Boot API | No | Example uses `jdbc:postgresql://localhost:55432/cinesense`; keep it aligned with the Compose host port and database name. |
| `SPRING_DATASOURCE_USERNAME`, `SPRING_DATASOURCE_PASSWORD` | Spring Boot API | No | Defaults to local Compose credentials; override to match `POSTGRES_USER` and `POSTGRES_PASSWORD`. |
| `API_PORT` | Spring Boot process | No | Defaults to 8080. Root `.env` is not automatically loaded into a standalone JVM process. |
| `TMDB_API_READ_ACCESS_TOKEN` | Python TMDB adapter | No | Preferred Bearer token. Read by the data-platform process, not Compose. Never commit it. |
| `TMDB_API_KEY` | Python TMDB adapter | No | Legacy query-key fallback. Bearer token is preferred. Never commit it. |
| `TMDB_USAGE_SCOPE` | Data-platform policy gate | No | Must be `non-commercial` for current local-use mode; not a legal determination. |
| `TMDB_TERMS_ACKNOWLEDGED`, `TMDB_ATTRIBUTION_ACKNOWLEDGED`, `TMDB_LOGO_ACKNOWLEDGED` | Data-platform policy gate | No | Must be explicitly `true` to make any live provider request; includes the required exact notice and official logo placement. |
| `TMDB_POLICY_REVIEWED_ON` | Data-platform run scope | No | Operator-supplied review date stored with the run. |
| `TMDB_SOURCE_POLICY` | Persistence policy gate | No | Defaults to `UNKNOWN`; set `PERMITTED` only after checking the exact storage/retention scope. |
| `TMDB_PERSISTENCE_ACKNOWLEDGED` | Persistence policy gate | No | Must be explicitly `true` before writes, in addition to `--execute`. |
| `TMDB_TIMEOUT_SECONDS`, `TMDB_MAX_RETRIES`, `TMDB_MIN_REQUEST_INTERVAL_SECONDS` | TMDB HTTP adapter | No | Defaults: 15 seconds, 3 retries, 0.25 seconds between requests. |
| `CINESENSE_DATABASE_URL` | Python data platform | No | Optional PostgreSQL URL; otherwise the Spring datasource settings are translated. |
| `HUGGINGFACE_HUB_TOKEN` | Future private/gated model access | No | Reserved; not read by current code. Public model access may not require one. Never bake it into an image. |
| `AI_SERVICE_URL` | Future API-to-AI client | No | Reserved; not read by current code. |

Do not add provider keys, model credentials, user data, dataset archives, or database passwords to Git. If a secret is accidentally committed, rotate it; deleting the line does not revoke it.
