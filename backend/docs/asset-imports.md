# Asset import provenance

The `asset_imports` table records the relationship between a canonical Asset, its
Google Drive source and the synchronization run that imported it.

| Column | Type | Meaning |
| --- | --- | --- |
| asset_id | UUID, non-null FK to assets.id | Canonical Asset |
| google_drive_file_id | varchar(256), non-null | Source identifier; letters, digits, underscores and hyphens |
| checksum | varchar(64), non-null | Lowercase SHA-256 captured at import time |
| import_date | timestamp with timezone, non-null | Database current timestamp by default |
| sync_job_id | UUID, non-null FK to sync_jobs.id | Importing synchronization run |

All five requested fields are retained; no synthetic ID column is needed.
The composite primary key is `(sync_job_id, google_drive_file_id)`: a source file
may appear only once in one run, but may have history in multiple runs. Different
source IDs may reference the same canonical Asset and checksum, supporting reuse.
If a source changes repeatedly during a run, record the successful import once;
use a subsequent run to record later content.

Foreign keys use RESTRICT for physical parent deletion. PAR soft deletion remains
supported and preserves provenance. A sync job with linked history cannot be
physically removed until that history is explicitly handled. No cascading deletes
or automatic parent creation are introduced.

Checksum is a historical snapshot, not a unique key or a live reference to
assets.sha256. Later edits to registry metadata must not rewrite past import
history. Future writers are responsible for recording the actual imported hash.
The database validates checksum format but cannot verify source-file bytes.
Indexes support Asset/date and source/date history lookups; the primary key
supports per-run queries.

## Migration

Apply `alembic upgrade head` using the updated backend image.
Revision `0006_asset_imports` follows `0005_sync_jobs` and only adds this table,
its constraints and indexes. Existing data is not backfilled.

`alembic downgrade 0005_sync_jobs` removes import provenance while preserving
Assets and sync jobs. Back up history before a production downgrade.

## Scope and validation

This is a persistence-only change. The existing `drive_imports` table remains
per-file workflow progress; `asset_imports` is provenance. No watcher wiring,
automatic population, API endpoints, Google Drive operations or AI are added.

Unit tests cover registered metadata and offline migration SQL. PostgreSQL tests
cover timezone defaults, foreign keys, duplicate prevention, source/Asset reuse,
historical checksums, retained provenance after PAR soft deletion and migration
round trips.
