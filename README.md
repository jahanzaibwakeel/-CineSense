# CineSense

**Describe the feeling. Discover the film.** CineSense is an AI-powered movie discovery platform, built as a maintainable monorepo. Phases 1 and 2 provide the Next.js foundation and design system, Spring Boot and FastAPI services, plus a provenance-aware PostgreSQL 17 + pgvector schema. No fabricated movie catalog or model weights are included. Discovery features are not connected yet.

## Requirements

- Windows 11 with PowerShell
- Node.js 20.9 or newer and npm
- Java 21
- Maven 3.6.3 or newer (or a Maven Wrapper once generated)
- Python 3.11 or newer
- Docker Desktop with Docker Compose, for PostgreSQL

## Start locally

Follow [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) for the complete Windows setup and per-service commands. Copy `.env.example` to `.env` and change both local database password values together before starting PostgreSQL:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d postgres
```

Start the web app from the repository root in another PowerShell window (first install with `npm ci`):

```powershell
npm run dev
```

The web app runs at `http://localhost:3000`. Start the API in a separate window from the repository root:

```powershell
$envLines = Get-Content .env | Where-Object { $_ -match '^(SPRING_DATASOURCE_URL|SPRING_DATASOURCE_USERNAME|SPRING_DATASOURCE_PASSWORD)=' }
foreach ($line in $envLines) {
    $name, $value = $line -split '=', 2
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
}
mvn -f services/api/pom.xml spring-boot:run
```

The API applies Flyway migrations on startup. Its liveness endpoint is `http://localhost:8080/health`; database readiness is `http://localhost:8080/actuator/health`. Start the AI service in another window from the repository root:

```powershell
py -m venv services/ai/.venv
& .\services\ai\.venv\Scripts\python.exe -m pip install -r services/ai/requirements.txt
& .\services\ai\.venv\Scripts\python.exe -m uvicorn --app-dir services/ai app.main:app --reload
```

The AI health endpoint is at `http://localhost:8000/health`. These initial service health endpoints do not require PostgreSQL.

## Build and test checks

```powershell
npm run build
npm run lint
mvn -f services/api/pom.xml verify
py -m compileall services/ai/app services/ai/tests
$env:PYTHONPATH = 'services/ai'
& .\services\ai\.venv\Scripts\python.exe -m unittest discover -s services/ai/tests -v
docker compose config --quiet
```

The API integration test uses Testcontainers and Docker Desktop. See [architecture](ARCHITECTURE.md), [data dictionary](DATA_DICTIONARY.md), [data-source research](DATA_SOURCES.md), [design system](docs/design-system.md), [database operations](database/README.md), [environment variables](ENVIRONMENT_VARIABLES.md), [current API](API_DOCUMENTATION.md), [roadmap](docs/roadmap.md), and [progress](docs/PROGRESS.md).
