# Production editor review

Open Productions in the frontend, then Open editor for a production. The workspace
shows Sequence → Scene → Shot → Required asset → Status using persisted planning
and registry data. The user's example is covered by test fixtures:
Morning Routine → Luxury Bedroom → WWML-VID-000045 → READY.
No example production or asset is seeded into the real database.

## API

GET `/api/v1/productions/{production_id}/editor` returns the production plus
`items`, `total`, `page`, `page_size`, `total_pages`. Each item includes sequence,
scene, shot, nullable requirement, nullable selected_asset, nullable locked_asset,
status and reason. The endpoint is read-only and documented in Swagger.

Pagination counts requirement rows. A shot with no requirements contributes one
UNPLANNED row, so it never appears ready by omission. A shot with several requirements
can span pages. Ordering follows sequence, scene, shot and requirement positions.
Empty scenes/sequences do not contribute rows; a production without shots is empty.
Page defaults to 1, page_size to 20; existing bounds (1,000,000 / 100) apply.
Missing production returns 404; invalid parameters return 422. Parent joins scope
every row to the selected production. No per-row database calls are made.

| Status | Meaning |
| --- | --- |
| READY | Locked asset is active; required media type, locked checksum and URI match the current registry |
| MISSING | Requirement exists but has no locked selection |
| REVIEW | Locked asset is deleted/missing, or media type/hash/URI changed |
| UNPLANNED | Shot has no required assets |

Status is derived on each read, not a persisted editable field. It describes each
requirement, not an aggregate claim that the entire shot or production is ready.
READY does not verify physical file availability, bytes, rights or editorial fitness.
Changed registry records do not mutate the original lock. REVIEW asks the editor
to inspect the difference before using or explicitly replacing the selection.

## Display references

The editor reads optional `asset_metadata.asset_code`, such as
`WWML-VID-000045`, when it matches `WWML-(VID|AUD|IMG|DOC|OTH)-` plus six digits.
Otherwise it displays the registry name. This is a manually supplied display label,
not a generated or unique key, and it is not interpreted as a media-type constraint.
The asset UUID remains authoritative. All joins and locking use UUIDs.
Names/codes are current registry metadata; checksum and URI come from the lock.
Updating metadata through PATCH replaces the complete metadata object, so preserve
other keys when adding an asset_code.

## Frontend behavior and scope

The production list and editor use server-side, uncached reads and validate payloads
before rendering. Malformed/unavailable responses show an unavailable state rather
than false readiness. Pagination works on desktop and mobile. Missing requirements
link to the existing asset library. Storage URIs are not rendered as browser media
links; this review workspace does not play, edit, export or render video.
Planning and locking writes remain available through the existing backend APIs.
No new schema migration is needed. No authentication behavior changes.

Tests cover status transitions, ordering, isolation, pagination, missing productions,
input validation, the example card, all four UI states and upstream failures.
