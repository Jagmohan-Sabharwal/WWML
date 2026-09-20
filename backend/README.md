# WWML backend

Python 3.12 / FastAPI foundation for documentary-production features.

## Run

The repository-root README describes the four-service Docker Compose stack.
For an API-only development process, from `backend/`:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

On PowerShell, create the environment with `py -3.12 -m venv .venv`, then
activate it with `.\.venv\Scripts\Activate.ps1`.

`GET /health` returns HTTP 200 and exactly `{"status":"healthy"}`. It does
not open database/cache connections and works before those services are configured.
`GET /health/ready` retains the Docker readiness contract: HTTP 200 with
`{"status":"ok","checks":{"postgres":true,"redis":true}}`, or HTTP 503
with `status: unavailable` and the individual check results. `/docs` and
`/openapi.json` document both endpoints, including the readiness 503 response.

## Layout and feature ownership

```text
app/
  main.py                 Application factory, lifespan, router composition
  api/health/             Health vertical slice: router, schemas, service
  core/                   Validated settings and application logging
  db/                     PostgreSQL and Redis connectivity adapters
  models/                 Shared persistence models (reserved)
  schemas/                Cross-feature contracts (reserved)
  services/               Reusable cross-feature services (reserved)
  workers/                Background jobs (reserved)
tests/                    API, configuration, connectivity and logging tests
```

New feature slices should keep their own routes, schemas and workflows together
under `app/api/<feature>/`. Promote code into shared packages only when multiple
features need it. The reserved packages are importable scaffolding; this bootstrap
does not invent data models, migrations, worker jobs or authentication.

## Configuration

`Settings` reads environment variables first, an optional `.env` in the process
working directory second, and defaults last. Explicit settings passed to
`create_app(settings)` support isolated tests. Unknown dotenv keys are ignored so
the repository-root example can be reused. Copy that example into `backend/.env`
for a host process if needed; do not commit the resulting file.

| Variable | Default | Purpose |
| --- | --- | --- |
| APP_NAME | WWML API | OpenAPI application title |
| LOG_LEVEL | INFO | DEBUG, INFO, WARNING, ERROR or CRITICAL |
| POSTGRES_HOST | postgres | Database hostname |
| POSTGRES_PORT | 5432 | Validated TCP port, 1–65535 |
| POSTGRES_DB | wwml | Database name |
| POSTGRES_USER | wwml | Database role |
| POSTGRES_PASSWORD | empty | Secret; empty makes readiness fail without connecting |
| REDIS_URL | redis://redis:6379/0 | Secret cache connection URL |

Docker Compose supplies the database/cache addresses and credentials and forwards
APP_NAME and LOG_LEVEL. Invalid typed settings fail startup. Settings objects mask
passwords and Redis URLs in their representations; never log raw settings or
credentials. Host processes need reachable services and corresponding addresses;
the default Compose setup does not publish PostgreSQL or Redis ports.

## Logging

At application startup, the `wwml` logger is configured with JSON records on stdout
containing UTC timestamp, level, logger and message. Reconfiguration does not add
duplicate handlers. Startup/shutdown and dependency-failure events are logged;
dependency exceptions and connection strings are intentionally not included.
Uvicorn and third-party loggers retain their own configuration.

## Tests and checks

From `backend/`, with development requirements installed:

```sh
python -m compileall -q app
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

The unit/API tests replace external connections; no running database or Redis is
required. They cover the exact liveness contract, all readiness outcomes, resource
cleanup, secret-safe errors, configuration precedence/validation, application
isolation and JSON log configuration. GitHub Actions runs these checks on Python
3.12. The Docker workflow separately proves actual SQL/cache connectivity and both
development and production container startup.
