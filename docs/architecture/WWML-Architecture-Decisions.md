# WWML Architecture Decisions

Version 1.0 · 2026-09-22

Implemented entries describe commit
`f82655903a5e8b107e7bbbd93dbe9372cc66bfe9` (PR #12), not deployment/merge status.
This register records current rationale; it does not invent historical approvals.

## Document map

- [WWML-101 — REST API v1](WWML-101-REST-API-v1.md)
- [WWML-102 — Database ERD v1](WWML-102-Database-ERD-v1.md)
- [WWML-103 — Asset Metadata v1](WWML-103-Asset-Metadata-v1.md)
- [WWML-104 — Video6 Asset Register v1](WWML-104-Video6-Asset-Register-v1.md)

## ADR-001 — Feature slices in one deployable backend

**Implemented.** FastAPI/Python 3.12 composes feature routers under app/api.
Registry, workspace and planning use repositories/services; shared settings and
database code live under core/db. Legacy integration code keeps its existing shape.
This groups deployable functionality without splitting each entity into a service.
Business rules and transactions stay on the backend.
Evidence: [application](../../backend/app/main.py).

## ADR-002 — Canonical registry, checksum reuse and tombstones

**Implemented.** UUIDs identify assets; unique SHA-256 prevents byte-identical
duplicates. Source bytes live outside PostgreSQL. Productions reference reusable
assets rather than owning copies of registry records.
Soft deletion preserves identities, checksum reservations, provenance and locks.
There is no restore/hard-delete endpoint or semantic deduplication.
Evidence: [model](../../backend/app/models/asset.py),
[service](../../backend/app/api/assets/service.py).

## ADR-003 — Ordered production hierarchy

**Implemented.** Production → Sequence → Scene → Shot → Required Asset uses separate
tables with required parent FKs and unique positive sibling positions.
Requirements represent editorial needs. Current APIs create/read nodes;
moving/editing/deletion is deferred. Production status is descriptive, not an
enforced transition state machine.
Evidence: [models](../../backend/app/models/production_structure.py).

## ADR-004 — Explicit selection snapshots

**Implemented.** Each requirement has at most one locked registry asset. First
selection checks active state and media type; row locks serialize selection/unlock.
Checksum, URI and timestamp preserve the chosen snapshot. Same-asset retries are
idempotent; replacement requires explicit unlock.
This is not physical storage immutability, editorial approval or a lock audit trail.
Evidence: [service](../../backend/app/api/production_structure/service.py),
[integration tests](../../backend/tests/integration/test_production_structure_api.py).

## ADR-005 — Discovery, progress, runs and provenance are distinct

**Partially implemented; writer integration pending.** The optional Drive worker
copies imports, renames only copies, registers assets and records drive_imports.
File/version identity supports retries; checksums support reuse.
sync_jobs and asset_imports exist but are not populated by that worker.
Only sync_jobs has a read endpoint. Per-file progress must not be presented as
recorded run history. Current checksum reuse can resolve tombstoned rows; active-only
handling needs a deliberate follow-up compatible with checksum reservations.
Evidence: [importer](../../backend/app/api/imports/service.py),
[sync model](../../backend/app/models/sync_job.py),
[provenance](../../backend/app/models/asset_import.py).

## ADR-006 — Versioned contracts with compatibility aliases

**Implemented.** New application APIs use /api/v1. Deprecated /assets CRUD/search
aliases and original health/Drive prefixes remain. OpenAPI derives from the app.
Stable ordering and bounded offset pagination do not provide a snapshot.
Legacy errors/pagination retain documented differences.
Evidence: [REST contract](WWML-101-REST-API-v1.md).

## ADR-007 — Server credentials versus caller authentication

**Credentials implemented; application identity/authorization pending.**
SecretStr settings and separate database parameters keep credentials server-side.
Drive uses application default credentials; Next.js receives the backend URL,
not Drive credentials. Provider credentials are not WWML user sessions.
No WWML login/JWT/session/API-key/RBAC or tenant boundary is implemented.
Identity provider, ownership model, roles and deployment access policy require a
separate implementation decision.
Evidence: [settings](../../backend/app/core/config.py),
[Drive client](../../backend/app/api/drive/client.py).

## ADR-008 — Migrations and deployability verification

**Implemented.** Alembic evolves the schema. Compose runs backend, frontend,
PostgreSQL and Redis, with optional importer configuration.
CI checks compilation, lint, types, unit tests, PostgreSQL migrations/integration,
frontend build/browser tests and Docker development/production startup.
Downgrades can remove data. Successful CI verifies a commit, not a production
deployment or validity of external credentials.
Evidence: [workflows](../../.github/workflows),
[migrations](../../backend/alembic/versions).

## ADR-009 — Documentary metadata namespaces

**Proposed, not enforced.** WWML-103 proposes technical/editorial/rights/provenance
fields. asset_metadata currently accepts arbitrary JSON. Automatic extraction,
namespace validation, rights gates and semantic search are not implemented.
Add versioned validation and compatibility rules before automated consumers rely
on these proposed fields.

## ADR-010 — Video6 register is a template

**Template only.** No actual Video6 inventory was provided. WWML-104 therefore has
empty tables and a population workflow. IDs, checksums, URIs and timestamps must
come from verified records. The document is a review aid, not a second registry.

## Pending decisions

| Area | Decision needed |
| --- | --- |
| Authentication | Identity provider, production ownership, roles and enforcement |
| Lock history | Audit events and actor identity for unlock/replacement |
| Storage | Immutable/versioned locations, retention and byte verification |
| Ingestion | Transactions/recovery for sync_jobs and asset_imports writers |
| Tombstones | Explicit handling of deleted checksum matches during import |
| Editing | Reorder/move/delete semantics without orphaning selections |
| Search scale | Measured need for indexes or cursor pagination |
| Metadata | Versioned validation and evidence-based extraction |

AI generation, AQR and automatic editorial scoring are outside implemented
registry/planning scope. These documents do not authorize or claim those features.

## Maintenance

Record status, rationale, consequences and source evidence for material changes.
Update the related contract/ERD and link the implementing PR. Supersede decisions
explicitly rather than describing proposed behavior as shipped.

## ADR-011 — Derived editor readiness

**Implemented by the editor extension after the baseline above.** A read-only workspace presents each shot requirement with its locked registry selection. READY requires an active matching-media asset whose checksum and URI match the snapshot; missing or changed selections need attention. Unplanned shots remain visible. This is selection readiness, not proof of physical bytes or editorial approval. Optional catalog labels are metadata, not canonical IDs. See [editor review](../../backend/docs/editor-review.md).
