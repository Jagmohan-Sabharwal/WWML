# Google Drive folder reader

Read existing documentary source files from one configured Google Drive folder.
This endpoint returns metadata only and does not download, generate, register or
modify assets.

## Configure access

1. Enable the Google Drive API in your Google Cloud project.
2. Provide Application Default Credentials (ADC) for a service account or another
   supported identity. Share the source folder with that identity as a viewer, or
   grant the identity access through the shared drive. OAuth scope alone does not
   grant folder access.
3. Set GOOGLE_DRIVE_FOLDER_ID to the ID from the folder URL, not the URL itself.
   Leave it blank to disable the integration without affecting API startup.
4. The adapter requests the drive.metadata.readonly scope. For user ADC, authorize
   the credentials with that scope. Workload identity or attached service-account
   credentials are supported through google-auth's default credential discovery.

For local file-based credentials, store the credential JSON **outside the
repository**, set GOOGLE_DRIVE_CREDENTIALS_FILE to its absolute host path in .env,
and start the optional Compose override:

```sh
docker compose -f docker-compose.yml -f docker-compose.drive.yml up --build --wait --wait-timeout 180
```

The override mounts the credential file read-only as a Compose secret and sets
GOOGLE_APPLICATION_CREDENTIALS inside the backend. Ensure the file is readable by
the backend's non-root user (UID 10001). No credentials are copied into an image.
For production-image smoke testing, include docker-compose.production.yml before
docker-compose.drive.yml. On a host process, set GOOGLE_APPLICATION_CREDENTIALS to
the credential file path directly, or use your deployment's ADC identity.

The credentials are discovered lazily when a scan is requested. google-auth handles
access-token refresh in memory; each scan closes its authorized session afterward.
Credentials, tokens and provider error bodies are never returned in API errors.
The Codex Google Drive connector's login is separate from the deployed platform's
ADC configuration.

## Read files

Swagger is available at http://localhost:8000/docs under google-drive.

```text
GET /integrations/google-drive/files
GET /integrations/google-drive/files?recursive=false
```

recursive defaults to true. false reads only direct child files, while still
following every page of results. The endpoint cannot accept another folder ID or
arbitrary Drive URL; the root is controlled by server configuration.

The response contains folder_id, recursive, total_files and files. Every file
contains:

- id, name, MIME type, description, parent IDs and shared-drive ID;
- size_bytes and created/modified timestamps when supplied by Drive;
- MD5 and SHA-256 checksums when supplied by Drive;
- web_view_link, shortcut details, path_parts and relative_path.

Absent provider values are null, not invented zeros or hashes. Native Google
Docs/Sheets may not supply size or checksums. Use a non-null SHA-256 with the
Assets API's checksum lookup when looking for reusable byte-identical assets.

Folder entries are traversed but excluded from files. Trashed entries are excluded.
Shortcuts are returned as shortcut metadata and are **not followed**, including
shortcuts to folders outside the configured tree. Folder and file IDs are
deduplicated, and repeated folder references cannot produce traversal cycles.

Results sort by case-insensitive path components, then file ID. Drive permits
duplicate names and names containing slashes: path_parts preserves those names,
while relative_path is for display, not a unique identifier or filesystem path.
Use the Drive file ID as identity.

The scan includes only items visible to the configured identity. Google Drive is
not a snapshot filesystem; changes while pagination is in progress may affect the
result. Shared-drive queries use the root folder's driveId and the Drive corpus.

## Limits and errors

| Setting | Default |
| --- | --- |
| GOOGLE_DRIVE_FOLDER_ID | blank (disabled) |
| GOOGLE_DRIVE_MAX_FILES | 10000 |
| GOOGLE_DRIVE_MAX_FOLDERS | 1000, including the root |
| GOOGLE_DRIVE_MAX_REQUESTS | 1000, including root lookup |
| GOOGLE_DRIVE_REQUEST_TIMEOUT_SECONDS | 10 |
| GOOGLE_DRIVE_SCAN_TIMEOUT_SECONDS | 60 |

Settings are validated at startup. Each request uses a timeout capped by remaining
scan time. The scan deadline is checked between requests and before returning.
Transport/authentication operations may finish after the deadline before raising;
this is not a hard process-level cancellation timer. Authentication discovery
occurs before the traversal deadline.

A limit, timeout, incompleteSearch result, repeated page token or child-folder
error fails the entire request rather than returning an apparently complete
partial list. Narrow the configured folder or adjust limits as appropriate.

| Status | Meaning |
| --- | --- |
| 403 | Identity lacks access |
| 404 | Required folder unavailable or trashed |
| 413 | File, folder or request budget exceeded |
| 422 | Invalid query parameter |
| 502 | Malformed/incomplete provider response or rejected page token |
| 503 | Missing configuration, invalid credentials, non-folder root, quota or temporary upstream failure |
| 504 | Request or traversal timeout |

Error bodies have detail.code and detail.message. Transient upstream errors return
Retry-After: 30. No general HTTP retries hide quota errors; credential refresh may
retry a request once. A malformed page token requires starting a fresh scan.

## Tests

The normal backend test suite uses fake paginated Drive data and mocked HTTP/ADC.
It tests recursive and direct-child reads, metadata normalization, empty folders,
shared-drive parameters, duplicates/cycles, shortcut behavior, malformed responses,
access errors, quotas, timeouts, resource limits and credential cleanup.
No Google account or live credentials are needed in CI.

Backend quality, PostgreSQL regression tests, and both Docker image smoke tests
remain required. Docker checks that an unconfigured Drive reader returns 503 while
the platform stays healthy. The optional secret override is syntax-validated with
a dummy credential file; live Google authentication must be verified after an
operator configures a real folder and identity.

No database migration is needed: this slice only reads remote metadata.

## References

- [Drive files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)
- [Drive metadata fields](https://developers.google.com/workspace/drive/api/reference/rest/v3/files)
- [Search and parent-folder queries](https://developers.google.com/workspace/drive/api/guides/search-files)
- [Application Default Credentials](https://google-auth.readthedocs.io/en/latest/reference/google.auth.html)
- [AuthorizedSession](https://google-auth.readthedocs.io/en/latest/reference/google.auth.transport.requests.html)

