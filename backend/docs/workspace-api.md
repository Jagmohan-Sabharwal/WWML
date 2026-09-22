# Workspace read APIs

Run `alembic upgrade head` before starting the backend. Compose runs migrations
automatically. Swagger at `/docs` and `/openapi.json` describe all response schemas.

| GET endpoint | Response |
| --- | --- |
| `/api/v1/dashboard` | Asset statistics, production and sync-job status totals |
| `/api/v1/assets/statistics` | `total_assets`, `total_size_bytes`, `by_media_type` |
| `/api/v1/productions` | Paginated persisted productions |
| `/api/v1/sync/jobs` | Paginated persisted synchronization jobs |

Asset statistics exclude soft-deleted registrations and include all five media groups,
including zero-count groups. Each group has `count` and `size_bytes`. Bytes describe
registered logical file sizes, not measured disk usage.

Production and sync lists accept `page` (default 1, maximum 1,000,000),
`page_size` (default 20, maximum 100), and optional `status`.
Responses contain `items`, `total`, `page`, `page_size`, `total_pages`.
Invalid or unknown query parameters return 422. Out-of-range pages return empty items
while retaining the filtered total. Empty lists have zero total pages.

Productions sort by `created_at DESC, id DESC`. The new `productions` table contains
UUID `id`, required nonblank `name` (255 characters), nullable `description`,
`status` (draft, in_production, completed, archived), and timezone-aware
`created_at`/`updated_at`. Status defaults to draft; database timestamps default
to the current time. SQLAlchemy updates updated_at on ORM updates.
Create productions and their sequence/scene/shot hierarchy through the
[production planning API](production-planning.md). No sample records are seeded.

Sync jobs sort by `started_at DESC NULLS LAST, id DESC`: pending jobs appear last.
Statuses are pending, running, completed, completed_with_errors, failed.
Items expose all eight [sync job fields](sync-jobs.md), including counters and errors.
The existing importer does not yet write sync_jobs; an empty response is expected
until a writer records runs. Existing per-file import history remains separate.

Dashboard `productions` and `sync_jobs` summaries contain `total` and `by_status`,
including zero-count statuses; `assets` matches the asset statistics response.
Each SQL query reads committed data; under concurrent writes the component
totals and list counts can reflect slightly different instants.

Examples: `/api/v1/productions?status=draft&page_size=20` and
`/api/v1/sync/jobs?status=failed&page=1`.

Migration `0007_productions` follows `0006_asset_imports`. Downgrading removes only
the productions table and its records; existing asset and import tables remain.
No frontend requests or existing API contracts change.
