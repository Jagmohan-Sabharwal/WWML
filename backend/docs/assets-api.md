# Assets API

Register and discover existing documentary source files before requesting any new
generation. The API stores metadata; it never generates, uploads, downloads or
deletes media.

## Start and inspect Swagger

From the repository root:

```sh
docker compose up --build --wait --wait-timeout 180
docker compose exec -T backend alembic upgrade head
```

Open http://localhost:8000/docs and expand **assets**. Request schemas, typed
responses, query bounds, 404/409 responses and validation errors are documented
in Swagger. The OpenAPI document is at http://localhost:8000/openapi.json.

## Endpoints

| Method and path | Result |
| --- | --- |
| POST /assets | Register an existing file; 201 and a Location header |
| GET /assets | Search/filter a page of assets; 200 |
| GET /assets/{asset_id} | Read one UUID; 200 or 404 |
| PATCH /assets/{asset_id} | Update provided fields; 200, 404 or 409 |
| DELETE /assets/{asset_id} | Delete the registration only; 204 or 404 |

Invalid UUIDs, query values or payloads return 422. IDs and timestamps are
server-managed and cannot be supplied in write payloads. Unknown body/query
fields are rejected.

### Register a file

Compute SHA-256 from the actual file bytes first. Example request shape:

```json
{
  "name": "Coastal interview",
  "description": "Marine biologist interview",
  "storage_uri": "gs://wwml/footage/coastal-interview.mp4",
  "media_type": "video",
  "mime_type": "video/mp4",
  "size_bytes": 1048576,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "asset_metadata": {"duration_seconds": 90, "tags": ["coast", "interview"]}
}
```

The example hash illustrates the required format; replace it with the real
checksum. Store durable locations without embedded credentials or expiring signed
URLs. The response includes id, created_at and updated_at in addition to the fields
above. Do an exact checksum lookup before registering:

```text
GET /assets?sha256=<64-character-lowercase-checksum>
```

A duplicate create or checksum-changing update returns 409:

```json
{
  "detail": {
    "code": "duplicate_asset",
    "message": "An asset with this checksum exists; reuse the existing asset.",
    "existing_asset_id": "existing-asset-uuid"
  }
}
```

Reuse the returned ID. A database uniqueness constraint protects against competing
registrations after the initial lookup. If the winning record is deleted before
it can be looked up, existing_asset_id can be null; repeat the checksum search.
This checks identical bytes, not semantic equivalence.

### Search, pagination and filters

```text
GET /assets?q=coastal&media_type=video&mime_type=video%2Fmp4&page=1&page_size=20
```

| Parameter | Behavior |
| --- | --- |
| q | Case-insensitive literal substring in name OR description; 1–200 trimmed characters |
| media_type | Exact video, audio, image, document or other |
| mime_type | Exact lowercase MIME type |
| sha256 | Exact lowercase file checksum |
| page | One-based, default 1; maximum 1,000,000 |
| page_size | Default 20; minimum 1, maximum 100 |

Filters combine with AND. SQL parameters are bound, and %, _ and / in search terms
are treated as literal characters. Sort order is created_at descending, then UUID
descending as a deterministic tie-breaker.

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "total_pages": 0
}
```

total counts all matching records before pagination. Out-of-range pages return
empty items with the matching total preserved. Offset pages may shift when assets
are inserted or deleted between requests; this is not a snapshot cursor API.

### Partial updates and deletion

PATCH requires at least one editable field. Omitted fields remain unchanged.
description may explicitly be null; other fields may not. asset_metadata replaces
the whole JSON object. For example:

```json
{"name": "Interview — selected take", "description": null}
```

DELETE permanently removes only the database registration, leaving the referenced
media file intact. A subsequent lookup or repeated delete returns 404.

## Migration

Revision 0002_asset_discovery builds composite indexes for created_at/id ordering,
media-type ordering and MIME-type ordering. It replaces the old media-type-only
index. Exact checksum lookup uses the existing unique index. Literal substring
search uses PostgreSQL ILIKE and is not accelerated by these B-tree indexes.

Apply with alembic upgrade head. Downgrading only this revision using
alembic downgrade 0001_create_assets restores the previous indexes and preserves
asset rows. Building indexes can lock writes on a large existing table; schedule
the schema deployment accordingly.

## Validation

Unit tests cover request validation and the Swagger contract. PostgreSQL tests
exercise CRUD, literal search, combined filters, checksum lookup, stable pagination,
missing IDs, duplicate conflicts, the competing-insert fallback, and the
data-preserving migration round trip. The Docker workflow registers, reads, searches,
updates and deletes a smoke-test record against both development and production
images after migrations are applied.

See the backend README for commands and safeguards for disposable test databases.
