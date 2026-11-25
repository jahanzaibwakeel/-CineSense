# API documentation — Phase 2

The running APIs contain health checks only. Discovery, authentication, catalog, watchlist, and preference APIs in the master specification are planned and must not be treated as available endpoints yet.

## Spring Boot application API

Base URL: `http://localhost:8080`

| Method | Path | Current response |
|---|---|---|
| `GET` | `/health` | `{"status":"ok","service":"api"}` |
| `GET` | `/actuator/health` | Spring Boot readiness, including database status (`UP`/`DOWN` without connection details) |

`/health` is a lightweight liveness response. Use `/actuator/health` to check PostgreSQL readiness; the application starts after Flyway has applied pending migrations.

## FastAPI AI service

Base URL: `http://localhost:8000`

| Method | Path | Current response |
|---|---|---|
| `GET` | `/health` | `{"status":"ok","service":"ai"}` |
| `GET` | `/docs` | FastAPI-generated interactive docs for the current health route |
| `GET` | `/openapi.json` | OpenAPI document for currently implemented routes |

## Future discovery contract principles

- A query interpretation will express required, preferred, excluded, and uncertain conditions separately and include a schema/prompt/model version.
- Refinements reference a search session and preserve prior turns.
- Results include evidence references, source and verification state, and explicit unknowns. A match explanation cannot assert a condition from vector similarity alone.
- Detailed API request/response schemas will be added alongside the Phase 7–10 implementation rather than publishing speculative endpoint behavior as if it worked.
