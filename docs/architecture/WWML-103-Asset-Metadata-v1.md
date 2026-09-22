# WWML-103 — Asset Metadata v1

Version 1.0 · 2026-09-22

Implementation baseline: `f82655903a5e8b107e7bbbd93dbe9372cc66bfe9` (PR #12).
Proposed conventions below are explicitly separate from implemented validation.

## Canonical identity and fields

The [Asset model](../../backend/app/models/asset.py) and
[API schemas](../../backend/app/api/assets/schemas.py) define the contract.
UUID identifies a row; SHA-256 identifies exact file bytes. Semantically similar
clips with different bytes are not automatically deduplicated.

| Field | API rule / storage |
| --- | --- |
| id | Response-only UUID; generated in Python |
| name | Required; trimmed, 1–255 characters; varchar(255) |
| description | Optional/null; max 10,000 API characters; text |
| storage_uri | Required; trimmed, 1–4096 API characters; text |
| media_type | Required: video/audio/image/document/other; varchar(16) |
| mime_type | Required lowercase type/subtype syntax; max 127 characters |
| size_bytes | Required strict integer, 0–9223372036854775807; bigint |
| sha256 | Required lowercase 64-hex; unique including tombstones |
| asset_metadata | JSON object, default {}; JSONB |
| created_at | Response-only timezone-aware database timestamp |
| updated_at | Database insert default; ORM updates set current time |
| deleted_at | Response-only nullable UTC soft-delete timestamp |

POST requires the six fields name, storage_uri, media_type, mime_type, size_bytes,
sha256. Unknown top-level fields are rejected. Metadata values may be nested JSON.
Direct registry writes do not download the file to verify supplied hashes/sizes.
The importer computes the downloaded hash and checks provider data where available.

PATCH changes supplied fields only. Description alone accepts null.
asset_metadata replaces the entire JSON object, without recursive merging.

## Existing importer metadata

New Drive-imported assets currently use these flat keys:

```json
{
  "source": "google_drive",
  "file_id": "<provider-file-id>",
  "version": "<provider-version>",
  "original_name": "<original filename>",
  "relative_path": "<path within configured folder>"
}
```

Values above are illustrative placeholders. Imported copies are renamed using a
sanitized original name and checksum suffix. Drive originals are not renamed.
Reusing a checksum does not overwrite the canonical row's source metadata.

asset_imports is intended for durable source/run provenance; it exists but the
worker does not populate it or sync_jobs yet. drive_imports tracks file progress.
The current worker checksum lookup can resolve a tombstoned row; normal registry
reads and new planning locks still require an active asset. Active-only importer
reuse is not an implemented guarantee.

## Proposed documentary metadata namespaces

**Proposal only:** these keys are arbitrary JSON today. They are not required,
automatically extracted, indexed or semantically validated by the API.
Preserve existing flat importer keys until a reviewed compatibility change.

| Namespace | Suggested fields | Evidence |
| --- | --- | --- |
| technical | duration_seconds, width_px, height_px, frame_rate numerator/denominator, video_codec, audio_codec, sample_rate_hz, channels | Probe of actual bytes |
| editorial | tags, transcript_uri, language, location_label, capture_date | Reviewed source/human metadata |
| rights | owner, license_reference, evidence_uri, usage_notes, review_status | Supplied records and editorial review |
| provenance | source_reference, capture_device, derivation_note | Verified acquisition/derivation records |

Use explicit units, rational frame rates, and omit unknown measurements instead of
inventing zeroes. A proposed review_status is neither an API enum nor an access
control. Do not put credentials, access tokens, signed URLs or secret-bearing
provider responses in storage_uri or metadata.

## Requirements versus selections

A RequiredAsset is a shot's editorial need: name, description, position, media_type
and shot_id. It has no file checksum or URI.
A LockedAsset records required_asset_id, asset_id, checksum, storage_uri, locked_at.
It snapshots file selection, not all mutable asset_metadata.

Registry edits or soft deletion do not rewrite existing locks. Explicit unlock
removes the selection; no separate audit history exists.
For reproducible bytes, use immutable/versioned locations and verify checksums
when consuming media. The lock API does not enforce physical storage retention.

## Reuse procedure

1. Query by actual SHA-256 when available, then search active metadata for candidates.
2. Review suitability; automatic semantic matching/AQR is not implemented.
3. Register only new bytes. A duplicate returns the existing identity; a tombstone
   still reserves its checksum.
4. Lock the chosen active matching-media asset against the requirement.
5. Preserve provenance and review evidence separately from the selection.

The [Video6 register](WWML-104-Video6-Asset-Register-v1.md) is an unpopulated
template for this process, not an inventory of existing media.

## Editor display label extension

The editor now consumes optional `asset_metadata.asset_code` matching `WWML-(VID|AUD|IMG|DOC|OTH)-` plus six digits, falling back to the registry name. It is a manual, non-unique label; UUID remains canonical. This does not implement the proposed technical/editorial/rights namespaces. See [editor review](../../backend/docs/editor-review.md).
