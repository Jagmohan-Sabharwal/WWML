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
  db/                     SQLAlchemy base, engine/session factory and probes
  models/                 Assets persistence model
  schemas/                Cross-feature contracts (reserved)
  services/               Reusable cross-feature services (reserved)
  workers/                Background jobs (reserved)
tests/                    API, configuration, connectivity and logging tests
```

New feature slices should keep their own routes, schemas and workflows together
under `app/api/<feature>/`. Promote code into shared packages only when multiple
features need it. The reserved packages are importable scaffolding; this bootstrap
does not invent worker jobs or authentication. SQLAlchemy models and Alembic migrations
provide the shared persistence foundation.

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

## PostgreSQL and migrations

The API and Alembic share the POSTGRES_* settings above. SQLAlchemy uses psycopg
with a lazy connection pool, connection validation before reuse, bounded pool and
connection waits, and parameter hiding in SQL errors. Credentials are assembled
with SQLAlchemy URL.create so reserved characters in passwords are handled safely.
Do not log rendered URLs with hide_password=False.

The application owns one engine per lifespan and disposes it at shutdown.
get_session is a FastAPI dependency that supplies a request-scoped Session,
rolls back on failure and always closes it. Feature services explicitly commit
successful writes. There is no import-time connection or automatic create_all.

After building the stack, from the repository root:

```sh
docker compose up --build --wait --wait-timeout 180
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend alembic current
```

Run migrations once per deployment before enabling features that use the schema.
They are an explicit release step, not run concurrently by each API worker.
The production image includes Alembic and migrations; use the same commands with
the production Compose override. Rebuild backend images after migration changes.
For a host process, run python -m alembic upgrade head from backend/ with
POSTGRES_* configured for a reachable database.

To author a migration from backend/:

```sh
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
python -m alembic check
```

Review autogenerated migrations before committing. Base.metadata uses stable
constraint names, and app/models/__init__.py registers all models for Alembic.
The first revision is 0001_create_assets. On a disposable database only,
`python -m alembic downgrade base` reverses it and **deletes the assets table and
its registered records**. It does not delete the referenced media files.

### Assets schema

| Column | Contract |
| --- | --- |
| id | UUID primary key, generated by the ORM on insert |
| name | Required nonblank name, up to 255 characters |
| description | Optional text |
| storage_uri | Required nonblank durable file location; no credentials or expiring signed URLs |
| media_type | video, audio, image, document or other; indexed |
| mime_type | Required MIME type string, up to 127 characters |
| size_bytes | Required nonnegative byte count |
| sha256 | Required canonical lowercase 64-character hash; globally unique |
| asset_metadata | JSONB, defaults to an empty object |
| created_at / updated_at | Time-zone-aware timestamps with PostgreSQL defaults |

Hash the actual file bytes before registration and look up sha256 before creating
an asset. The unique constraint also prevents duplicates during concurrent writes;
handle IntegrityError with a rollback and reuse the existing record. This is exact
file deduplication, not semantic equivalence detection. Multiple source locations,
perceptual similarity can be added in later slices. Asset registration and discovery APIs are documented below.
The ORM updates updated_at on changes; raw SQL writers must set it explicitly.
Replace asset_metadata with a new dictionary when editing it so SQLAlchemy tracks
the change. Media files are referenced, not stored as database blobs.

### PostgreSQL integration tests

The PostgreSQL migrations workflow runs the first migration against PostgreSQL 17,
tests upgrade/downgrade/upgrade and metadata drift, persists and updates assets,
and verifies all integrity constraints and exact-file deduplication.

Local integration tests require an **empty disposable** database whose name ends
in _test. Set POSTGRES_* to that database and RUN_DB_TESTS=1, then run:

```sh
python -m pytest -m integration
```

The test fixture refuses non-test names or databases containing tables. It removes
its tables after each test. Never point this suite at a shared or production
database. Without RUN_DB_TESTS=1 these tests are skipped; unit tests and offline
migration SQL generation still run without PostgreSQL.

## Assets CRUD and discovery

See [Assets API](docs/assets-api.md) for CRUD, search, pagination, filtering,
Swagger examples, conflict handling and the discovery-index migration.

## Google Drive folder discovery

See [Google Drive reader](docs/google-drive.md) for configured-folder reads,
recursive metadata discovery, read-only ADC setup and tests.

## Synchronization history schema

See [sync jobs](docs/sync-jobs.md) for the run-level model, lifecycle, counters and migration. This schema change does not start or modify the watcher.

## Asset import provenance

See [asset imports](docs/asset-imports.md) for source-to-Asset relationships, sync-job links, checksum history and migration details.

See [Workspace read APIs](docs/workspace-api.md) for dashboard, productions, sync jobs and statistics.

See [Production planning](docs/production-planning.md) for sequences, scenes, shots, required assets and explicit registry asset locks.

See [Editor review](docs/editor-review.md) for production-scoped scene/shot selection readiness.

See [Production dashboard](docs/production-dashboard.md) for readiness metrics and shared-library import activity.
