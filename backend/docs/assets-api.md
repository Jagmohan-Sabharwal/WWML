# Production Asset Registry (WWML-005)

The PAR is the canonical SQL-backed record of documentary assets. It stores
metadata and file locations, with one unique SHA-256 registration per set of file
bytes. It does not upload, download, generate, score or analyze media.

## Run and inspect

```sh
docker compose up --build --wait --wait-timeout 180
docker compose exec -T backend alembic upgrade head
```

Swagger: http://localhost:8000/docs, **assets**.
OpenAPI: http://localhost:8000/openapi.json.
The platform retains its current trusted-network deployment model; this slice
does not add authentication.

## API

| Method | Canonical path | Result |
| --- | --- | --- |
| POST | /api/v1/assets | Register metadata; 201 with Location |
| GET | /api/v1/assets | Paginated active assets |
| GET | /api/v1/assets/search | Search, filter and sort active assets |
| GET | /api/v1/assets/{asset_id} | Read an active UUID; 200 or 404 |
| PATCH | /api/v1/assets/{asset_id} | Partial update; 200, 404 or 409 |
| DELETE | /api/v1/assets/{asset_id} | Soft delete; 204 or 404 |

The static `/search` route precedes the UUID route. The legacy `/assets` paths
remain deprecated aliases to the same repository/service for existing clients.
They also soft delete. Neither API exposes a hard-delete or restore operation.

Malformed UUIDs, unknown query/body fields and invalid values return 422.
PATCH needs at least one editable field. Omitted fields remain unchanged;
description alone may be explicitly null. Updating asset_metadata replaces the
entire JSON object.

### Asset schema

The existing SQLAlchemy `Asset` and `assets` table remain the single registry;
no parallel asset table is introduced.

| Field | Rules |
| --- | --- |
| id | Server-generated UUID primary key |
| name | Required, nonblank, at most 255 characters |
| description | Optional, at most 10,000 characters |
| storage_uri | Required durable location; do not embed credentials or signed URLs |
| media_type | video, audio, image, document or other |
| mime_type | Valid lowercase MIME type, at most 127 characters |
| size_bytes | Integer from 0 to PostgreSQL bigint maximum |
| sha256 | 64 lowercase hex characters; globally unique, including deleted rows |
| asset_metadata | JSON object, defaults to {} |
| created_at / updated_at | Server-managed timestamps with timezone |
| deleted_at | Nullable timestamp with timezone; null for active records |

IDs and lifecycle timestamps cannot be set by POST/PATCH. The service owns write
transactions; the repository owns SQLAlchemy persistence/query construction.
Mutating an existing asset locks its active row until commit to serialize PATCH
and DELETE.

Example registration (replace the illustrative checksum with the actual hash):

```json
{
  "name": "Coastal interview",
  "description": "Marine biologist interview",
  "storage_uri": "s3://wwml/footage/coastal-interview.mp4",
  "media_type": "video",
  "mime_type": "video/mp4",
  "size_bytes": 1048576,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "asset_metadata": {"duration_seconds": 90, "tags": ["coast", "interview"]}
}
```

### Search, sorting and filtering

```text
GET /api/v1/assets/search?q=coastal&media_type=video&sort_by=name&sort_order=asc&page=1&page_size=20
```

List and search accept identical query parameters:

| Parameter | Behavior |
| --- | --- |
| q | Case-insensitive literal substring in name OR description; 1–200 trimmed characters |
| media_type | Exact video, audio, image, document or other |
| mime_type | Exact lowercase MIME type |
| sha256 | Exact lowercase SHA-256 |
| min_size_bytes / max_size_bytes | Inclusive size bounds; minimum cannot exceed maximum |
| created_after / created_before | Inclusive creation bounds; ISO 8601 with timezone; lower cannot exceed upper |
| sort_by | created_at (default), updated_at, name or size_bytes |
| sort_order | desc (default) or asc |
| page | One-based, default 1, maximum 1,000,000 |
| page_size | Default 20, range 1–100 |

All filters combine with AND. Size bounds are nonnegative PostgreSQL bigint values.
Name sorting is case-insensitive. Every sort uses UUID in the same direction as a
deterministic tie-breaker. Sort expressions are allowlisted, values are bound, and
SQL wildcard characters in search text are escaped.

```json
{"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}
```

Totals count matching active records before pagination. Out-of-range pages return
empty items with the matching total preserved. Offset pages can shift during
concurrent writes; this is not a snapshot cursor API.

### Soft deletion and canonical identity

DELETE sets deleted_at and updates updated_at. The row, original UUID, checksum,
metadata, relationships and external file remain intact. Subsequent GET, PATCH,
or DELETE for that UUID returns 404. Deleted rows are excluded from list/search,
including their totals. There is no include_deleted query option.

An active checksum conflict returns 409 with `code: duplicate_asset` and
`existing_asset_id`. A checksum belonging to a tombstone returns 409 with
`code: asset_deleted` and the canonical ID. This applies to both new registrations
and checksum-changing PATCH requests. The unique constraint covers all records,
and the service rolls back and classifies competing-registration conflicts.
Deletion cannot silently release a checksum or create a second canonical record.
Restoration/administrative retention policy is outside this change.

```json
{
  "detail": {
    "code": "asset_deleted",
    "message": "A deleted asset retains this checksum; registration is reserved.",
    "existing_asset_id": "existing-asset-uuid"
  }
}
```

## Migration and deployment

Revision `0004_asset_soft_delete` adds nullable deleted_at and a partial
created_at/id index for active rows. Existing assets remain active and keep their
IDs, checksums and references. Existing indexes and uniqueness constraints remain.

Apply `alembic upgrade head` before directing traffic to the new API version.
Drain writes during schema/app deployment so old application instances cannot
continue performing physical deletes. Building the index can lock writes on large
tables; plan a maintenance window when needed.

`alembic downgrade 0003_drive_imports` removes the index and deleted_at without
deleting asset rows, but loses deletion state and makes tombstones active again.
Only use this rollback after explicitly accepting that lifecycle consequence.
Back up the database before production migrations. Downgrading to base is
destructive and removes the registry itself.

## Verification

Unit tests cover query validation, readonly lifecycle fields, SQL construction,
soft-delete behavior, service transaction/conflict handling, and OpenAPI routes.
PostgreSQL integration tests cover the versioned CRUD flow, retained tombstones,
legacy alias behavior, checksum reservation, all four sorting fields in both
directions, pagination ties, inclusive filters and migration round trips over
populated data. Docker smoke tests use the versioned API in development and
production images and confirm soft-deleted checksums remain reserved.

See [backend development](../README.md) for test commands and the disposable
PostgreSQL test database safeguards. No AQR, AI or Google Drive implementation is
part of this registry change.
