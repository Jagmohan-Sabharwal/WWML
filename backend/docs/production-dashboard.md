# Production dashboard

Open a production's name in the Productions list to view
`/productions/{id}/dashboard`. The title uses the saved production name, including
Video #6 when that record exists. The illustrative Video #6 data is test-only.
The existing platform-wide `/dashboard` page remains available.

GET `/api/v1/productions/{production_id}/dashboard` returns the production and
the metrics below; missing production returns 404. This read-only projection uses
the existing tables and requires no new migration. Swagger documents the response.

| Field | Scope / definition |
| --- | --- |
| progress_percent | Production asset-planning readiness; null when no requirements or unplanned shots exist |
| assets_ready | Requirement slots with active matching-media assets and matching locked checksum/URI |
| missing_assets | Requirement slots without locks |
| assets_to_review | Locked slots whose current registry records no longer match or are deleted |
| unplanned_shots | Shots with no required assets |
| required_assets | All requirement slots in this production, not unique file count |
| ai_gaps | Null: no recorded decision that an unmet requirement needs AI generation |
| credits_saved | Null: no cost/savings ledger or verified baseline exists |
| activity_scope | Always shared_library for sync/import activity below |
| latest_sync_job | Latest recorded run by started_at DESC NULLS LAST, id DESC; null if none |
| import_queue | Shared drive_imports rows in watch/import/rename/register |
| failed_imports | Shared rows in failed, outside the queue count |
| latest_imports | At most five done rows, ordered updated_at DESC then UUID DESC |

Progress is `100 × assets_ready / (required_assets + unplanned_shots)`, rounded to
one decimal place. Incomplete plans are capped at 99.9% to avoid rounding to 100%.
This is asset-planning progress, not progress through research, script, editing,
review or publishing. Unplanned shots prevent an incomplete storyboard from
appearing complete, but empty scenes/sequences have no inferred shot count.
Readiness does not verify file availability, rights or editorial approval.

Assets Ready counts ready requirement slots: reuse in two slots counts twice.
Missing Assets is not an AI backlog; search and acquisition decisions may resolve
requirements without generation. AI Gaps and Credits Saved render **Not tracked**,
not zero or estimated savings. No AI services or credit calculations are invoked.

The importer does not yet populate sync_jobs; No recorded runs is expected until
a writer records runs. A latest job status is not a live worker heartbeat, and
queue counts can include stalled items. Shared imports are not attributed to
the selected production. Done records indicate completed import workflows and
can include deduplicated reuse, not necessarily newly downloaded bytes.

The API aggregates the complete plan independently of editor pagination. Each
query reads committed data; concurrent updates may change counts between queries.
The frontend reads uncached data on page load, validates it, and shows unavailable
states for failed/malformed responses. It does not poll or claim live synchronization.

Unit tests cover progress and empty-plan behavior. PostgreSQL tests compare editor
readiness with dashboard totals, isolate production counts, verify shared scope,
empty states and latest-import limits. Desktop/mobile tests cover all eight sections,
progress, unknown metrics, empty/error states and responsive layout.
