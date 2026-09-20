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

The repository includes minimal runnable apps; Smart Sync, Asset Registry,
Command Center, and application authentication are not implemented yet.

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
