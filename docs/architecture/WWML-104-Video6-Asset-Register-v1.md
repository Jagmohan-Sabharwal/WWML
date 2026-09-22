# WWML-104 — Video6 Asset Register v1

Version 1.0 · 2026-09-22

**Status: unpopulated planning template.** No Video6 script, production UUID,
shot list, asset inventory or approved selections were supplied.
Video6 is the requested document label, not an existing database identifier.
This document creates no records and asserts no registered or locked assets.

Use [REST API v1](WWML-101-REST-API-v1.md) and
[Asset Metadata v1](WWML-103-Asset-Metadata-v1.md) to populate verified values.
The database remains the canonical source of truth.

## Production identity

| Item | Value |
| --- | --- |
| Working label | Video6 |
| Production UUID | Not supplied |
| Approved title/brief | Not supplied |
| Script revision | Not supplied |
| Editorial owner | Not supplied |
| Delivery specification | Not supplied |
| Registry review date | Not performed |

## Shot requirements

Copy one row per required asset slot. Human labels supplement actual database IDs.

| Sequence / ID | Scene / ID | Shot / ID | Requirement ID / position | Description | Media type | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | Template only; replace with a verified requirement | — | — |

## Candidate reuse review

A candidate is not a lock. Multiple candidates may be reviewed for one requirement.

| Requirement UUID | Candidate Asset UUID | Registry name | SHA-256 | Provenance reference | Suitability review | Rights evidence | Decision / reviewer |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | Not reviewed | Not supplied | — |

These are manual planning fields, not extra API request fields or persisted
review entities. Automatic ranking, AQR and rights enforcement are not implemented.

## Confirmed locks

Populate only after a successful lock API response. Copy returned values exactly.

| Requirement UUID | Asset UUID | Locked checksum | Locked storage URI | locked_at | Verified on |
| --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | No confirmed locks supplied |

Reconcile against GET /api/v1/required-assets/{requirement_id}/locked-asset.
When a selection is unlocked, remove the confirmed row or explicitly mark it stale.
Do not infer a lock from a candidate review or a filename.

## Population workflow

1. Confirm brief/script; create the production and record its returned UUID.
2. Create ordered sequences, scenes and shots beneath the correct parents.
3. Create one required asset slot per need, with explicit media_type.
4. Search the active registry first; record real candidates and review evidence.
5. Record missing acquisition needs when no candidate is suitable. This template
   does not authorize AI generation or invent an available asset.
6. Register acquired files with verified metadata and source provenance.
7. PUT the selected asset_id to the requirement's locked-asset endpoint.
8. Record the returned snapshot and reconcile before use.

A requirement has one selection; create more requirements for multiple files.
The same asset can serve several requirements. Replacement requires explicit unlock.
A lock checks active registration and media type, not editorial fitness.

## Outstanding inputs and change log

The script, concrete hierarchy, media inventory and ownership assignments remain
unknown. Video6 is not asserted to be production-ready.

| Version | Change |
| --- | --- |
| 1.0 | Initial template; no assets or selections asserted |
