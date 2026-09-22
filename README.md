# WWML

WWML (Wealthy Wellness Machine Learning / World-Class Multimedia Library) is the production platform for documentary creation.

## Milestone 1
- FastAPI backend
- Next.js frontend
- PostgreSQL
- Smart Sync
- Asset Registry
- Command Center

## Start the development platform

Install Docker Engine or Docker Desktop (Linux containers) with Docker Compose
**2.24.4 or newer**. No host Python, Node.js, PostgreSQL, or Redis installation is needed.

From the repository root, copy the example environment:

```sh
cp .env.example .env
docker compose up --build --wait --wait-timeout 180
```

On Windows PowerShell, use `Copy-Item .env.example .env` for the copy step.
The first build downloads dependencies and can take several minutes.

- Frontend: http://localhost:3000
- Backend OpenAPI docs: http://localhost:8000/docs
- Backend liveness: http://localhost:8000/health
- Full readiness: http://localhost:8000/health/ready
- Frontend-to-backend connectivity: http://localhost:3000/api/health

The repository includes runnable apps, an Assets API and optional Google Drive
ingestion. The frontend includes Dashboard, Assets, Productions and Settings pages.
Production planning APIs support sequences, scenes, shots and explicit asset selections.
The Productions frontend remains a placeholder; application authentication is not implemented.

## Services and configuration

| Service | Runtime | Internal address | Host access |
| --- | --- | --- | --- |
| frontend | Next.js / Node.js 22 | frontend:3000 | localhost:3000 |
| backend | FastAPI / Python 3.12 | backend:8000 | localhost:8000 |
| postgres | PostgreSQL 17 | postgres:5432 | Compose network only |
| redis | Redis 7.4 with AOF persistence | redis:6379 | Compose network only |

`.env.example` documents `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `BACKEND_PORT`, and `FRONTEND_PORT`.
Change host ports in `.env` if the defaults are occupied. Container-to-container
ports remain unchanged. The sample password is for local development only;
`.env` is ignored by Git and excluded from application image build contexts.

The backend receives database settings and a Redis URL at runtime. Credentials
are passed as separate PostgreSQL connection parameters, not embedded in a URL.
The frontend receives only the internal backend URL, used server-side by
`/api/health`; no database credentials or Docker hostnames are sent to the browser.
Readiness runs an actual SQL query and Redis ping, returning HTTP 503 when either
dependency is unavailable. Compose waits for healthy dependencies before starting
the application services. PostgreSQL and Redis are not published to host ports.

## Daily development

Edits under `backend/app` reload Uvicorn; edits under `frontend/app` reload Next.js.
Only source directories are mounted, so container dependencies and Next.js build
artifacts are not overwritten by host files. Polling supports Docker Desktop mounts.
After changing dependencies, Dockerfiles, or Next.js configuration, rebuild:

```sh
docker compose up --build --wait --wait-timeout 180
docker compose ps
docker compose logs -f backend frontend
docker compose down
```

Named volumes retain PostgreSQL and Redis data across container recreation and
`docker compose down`. To deliberately delete **all local database/cache data**:

```sh
docker compose down --volumes
```

PostgreSQL initialization variables apply only to an empty volume. Changing the
password or database in `.env` does not update an existing database; keep its
existing settings, alter it explicitly, or reset disposable local volumes.

## Deployable images

Both Dockerfiles default to a `production` target. The frontend uses a compiled
Next.js standalone server; the backend runs Uvicorn without reload. Both run as
non-root users. Development Compose explicitly selects the development targets.

Build the standalone images:

```sh
docker build --target production -t wwml-backend ./backend
docker build --target production -t wwml-frontend ./frontend
```

To verify production images together locally, stop the development stack and use
the override (it removes source mounts and the backend reload command):

```sh
docker compose down
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build --wait --wait-timeout 180
```

The same local URLs and persistent volumes apply. This is a local deployment
smoke test. For hosting, provide runtime database settings, `REDIS_URL`, and
`BACKEND_URL` appropriate to the deployment network, managed secrets, TLS ingress,
and backups. The sample Compose credentials and unauthenticated starter endpoints
are intended for local development.

## Validation

The Docker platform GitHub Actions workflow builds and starts all four services,
checks the frontend, SQL/Redis readiness and frontend proxy, then repeats against
production images without source mounts. It prints container logs and cleans up
volumes on completion.


## Backend development

See [backend/README.md](backend/README.md) for the Python 3.12 application layout, configuration, logging and tests. GET /health returns status healthy; dependency readiness remains at /health/ready.

## Initialize the Assets database

After starting the stack, run `docker compose exec -T backend alembic upgrade head`.
See [backend database documentation](backend/README.md#postgresql-and-migrations)
for configuration, the Assets schema, migrations and PostgreSQL integration tests.

## Assets API

Use `/api/v1/assets` to register and discover reusable footage. CRUD, soft deletion,
search, sorting, filters and pagination are documented in [Assets API](backend/docs/assets-api.md) and
Swagger at http://localhost:8000/docs. Apply migrations before using these routes.

## Google Drive sources

The optional [Google Drive reader](backend/docs/google-drive.md) returns files and
metadata from a configured folder recursively. Configure the folder and ADC
credentials before calling `/integrations/google-drive/files`.

## Google Drive: watch → import → rename → register → done

The opt-in worker recursively polls the configured Drive folder. It imports ordinary
uploaded files (video, audio, images, PDFs, etc.) into the persistent `asset_data`
volume. Only imported copies are renamed. Native Google Workspace files and
shortcuts appear as `skipped`; export and shortcut traversal are not implemented.

Set `GOOGLE_DRIVE_FOLDER_ID` and `GOOGLE_DRIVE_CREDENTIALS_FILE` in your local
environment or .env. Enable the Drive API and grant the credential identity read
access to the source folder. The importer requests
`https://www.googleapis.com/auth/drive.readonly`; credentials previously authorized
only for metadata must be reauthorized for downloads. The metadata endpoint keeps
its narrower metadata scope. Credentials are mounted as a secret, never stored in
Assets, progress rows, images, or logs. No Drive write permissions are requested.

Start the platform and apply migration 0003 before starting the worker:

```sh
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.import.yml up --build -d
```

For production images, include overrides in this order so the shared asset mount
is added after the production override removes development source mounts:

```sh
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
docker compose exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.production.yml -f docker-compose.import.yml up --build -d
```

Use `docker compose -f docker-compose.yml -f docker-compose.import.yml logs -f importer`
for worker logs. Add `-f docker-compose.drive.yml` if the backend metadata reader
also needs file-based credentials. The backend sees imported storage read-only.

Run one scan instead of a continuous watcher:

```sh
docker compose -f docker-compose.yml -f docker-compose.import.yml run --rm importer python -m app.workers.drive_import --once
```

The watcher performs a full bounded scan, processes files serially, then waits
`IMPORT_POLL_SECONDS` (default 60). It is polling, not a Drive push subscription.
A PostgreSQL session advisory lock allows one importer per database. All replicas
must share the same storage volume. No Redis queue or separate broker is needed.

Progress is persisted in `drive_imports`, uniquely keyed by Drive file ID and
provider version. `GET /integrations/google-drive/imports?status=done&page=1&page_size=20`
returns paginated progress; `GET /integrations/google-drive/imports/{id}` returns
one import. Swagger at `/docs` documents both endpoints. Progress includes status,
attempt count, safe error code and registered Asset ID. These endpoints inherit
the platform's current trusted-network deployment model; application user
authentication has not yet been added.

Downloads stream into private staging while calculating SHA-256. Size, provider
checksum when available, download deadline and source version are checked before
registration. Files changed during transfer fail that attempt; a subsequent scan
discovers the new version. Default maximum size is 10 GiB and download deadline is
30 minutes (plus at most an in-flight request timeout). Neither file bytes nor
credentials are held in the database.

The stored name is `asset-<sanitized-original-stem>-<12-character-SHA256><extension>`,
inside a directory named by the full SHA-256. For example,
`Interview take.mp4` becomes `asset-Interview_take-a1b2c3d4e5f6.mp4`.
Path separators and unsafe characters are removed, names are bounded, and files
are atomically published on the same storage volume. Assets retain the original
Drive ID, name, version and relative path as source metadata.

An existing Asset with the same SHA-256 is reused. When Drive supplies SHA-256,
the download can be avoided entirely; otherwise bytes are compared after download.
Asset registration and `done` commit together. Interrupted intermediate stages
retry on a later scan while the source remains in the configured folder. Errors
are retried up to `IMPORT_MAX_ATTEMPTS` (default 3), once per scan; increasing this
setting permits further attempts after correcting permissions, capacity or other
configuration. Exhausted jobs remain visibly failed. Inspect progress after
`--once`: individual file failures are recorded even if the scan itself succeeds.

Staging files left by a terminated worker are cleared by the next worker while it
holds the exclusive lock. A crash after publication or a concurrent Asset
registration can leave an unreferenced content file; files are intentionally not
garbage-collected automatically. Soft-deleting an Asset preserves the progress reference and stored bytes. It does
not automatically reimport a completed source version.
Back up PostgreSQL and `asset_data` together. Never use `down --volumes` on data
you need to retain.

Migration 0003 adds only ingestion tracking; downgrade removes tracking while
preserving Assets and stored files. Stop the importer before downgrading.
Tests cover naming, streaming failures, integrity checks, retry limits, restart
recovery, duplicate reuse, migration round trips and progress API pagination.
The PostgreSQL and Docker workflows exercise the real database and both images;
live Drive access requires your configured credentials.

## Frontend workspace

Open http://localhost:3000 for Dashboard, Assets, Productions and Settings.
See [frontend documentation](frontend/README.md) for local setup, Tailwind styling,
TypeScript conventions, runtime configuration and browser tests.

## Architecture documentation

- [REST API v1](docs/architecture/WWML-101-REST-API-v1.md)
- [Database ERD v1](docs/architecture/WWML-102-Database-ERD-v1.md)
- [Asset Metadata v1](docs/architecture/WWML-103-Asset-Metadata-v1.md)
- [Video6 Asset Register template](docs/architecture/WWML-104-Video6-Asset-Register-v1.md)
- [Architecture Decisions](docs/architecture/WWML-Architecture-Decisions.md)
