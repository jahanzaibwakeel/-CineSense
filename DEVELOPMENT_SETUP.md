# Development setup

This guide describes the current Windows 11 / PowerShell foundation. It does not imply that catalog search, sign-in, AI models, or user features are implemented yet.

## Prerequisites

- Windows 11 and PowerShell 7 or Windows PowerShell 5.1.
- Node.js 20.9 or newer with npm.
- Java 21 and Maven 3.6.3 or newer.
- Python 3.11 or newer with the Python launcher (`py`).
- Docker Desktop with Docker Compose.

## First-time setup

From the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm ci
docker compose up -d postgres
```

The example binds PostgreSQL to host port `55432` to avoid common Windows PostgreSQL port conflicts. The container still listens on 5432. Compose reads `.env`; standalone app processes do not automatically inherit its settings. The Spring datasource URL in `.env` is already aligned with this port. When changing the port or credentials, update the matching `SPRING_DATASOURCE_*` values too.

## Run the services

Run each service in its own PowerShell window.

**Frontend, from the repository root:**

```powershell
npm run dev
```

Open `http://localhost:3000`.

**Spring Boot API, from the repository root:**

```powershell
$envLines = Get-Content .env | Where-Object { $_ -match '^(SPRING_DATASOURCE_URL|SPRING_DATASOURCE_USERNAME|SPRING_DATASOURCE_PASSWORD)=' }
foreach ($line in $envLines) {
    $name, $value = $line -split '=', 2
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
}
mvn -f services/api/pom.xml spring-boot:run
```

Health: `http://localhost:8080/health`; database readiness: `http://localhost:8080/actuator/health`. Flyway applies schema migrations on startup, then Hibernate validates the schema. Set `API_PORT` in the API process environment to change its port. Set `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, and `SPRING_DATASOURCE_PASSWORD` to match any non-default Compose settings.

**FastAPI service, from the repository root:**

```powershell
py -m venv services/ai/.venv
& .\services\ai\.venv\Scripts\python.exe -m pip install -r services/ai/requirements.txt
& .\services\ai\.venv\Scripts\python.exe -m uvicorn --app-dir services/ai app.main:app --reload
```

Health: `http://localhost:8000/health`. The current service has no model or catalog dependency. No model download is required.

**Python data platform, from the repository root:**

```powershell
py -3.14 -m venv data-platform/.venv
& .\data-platform\.venv\Scripts\python.exe -m pip install -r data-platform/requirements-test.txt
& .\data-platform\.venv\Scripts\python.exe -m pytest data-platform/tests -v
```

Set `TMDB_API_READ_ACCESS_TOKEN` (or legacy `TMDB_API_KEY`) in the data-platform process environment for provider calls. Review current TMDB terms and complete the logo/attribution requirement before setting acknowledgement variables; the provider gate requires all acknowledgements. For persistence, set `TMDB_SOURCE_POLICY=PERMITTED`, `TMDB_PERSISTENCE_ACKNOWLEDGED=true`, and the database variables only after confirming the planned storage/retention is allowed. Use `python -m data_platform.cli tmdb discover --limit 20 --dry-run` for a bounded preview. See [data-platform/README.md](data-platform/README.md) for exact commands and gates.

## Build and test

```powershell
npm run lint
npm run build
mvn -f services/api/pom.xml verify
py -m compileall services/ai/app services/ai/tests
$env:PYTHONPATH = 'services/ai'
& .\services\ai\.venv\Scripts\python.exe -m unittest discover -s services/ai/tests -v
docker compose config --quiet
py -3.14 -m pytest data-platform/tests -v
```

The API database integration test uses Testcontainers and requires Docker Desktop to be running. To run it alone, use `mvn -f services/api/pom.xml -Dtest=DatabaseSchemaIntegrationTest test`.

## Windows notes

- Use `Copy-Item`, `Set-Location`, and the service-local `services/ai/.venv/Scripts/python.exe` in PowerShell; activation is optional.
- `npm ci` uses the checked-in root lockfile. Run `npm install` after changing workspace package manifests, then review the lockfile diff.
- Maven writes build output under `services/api/target`; Python environments are under the ignored `.venv` path.
- `.env`, model weights, and raw/processed datasets are ignored. Never put credentials in tracked files.
- Do not run bulk downloads during setup. Provider ingestion and model setup will be documented after their rights and model-version choices are reviewed.
