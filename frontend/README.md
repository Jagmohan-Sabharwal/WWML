# WWML frontend

Next.js App Router, strict TypeScript and Tailwind CSS. Run with Node.js 22.

## Start

The repository's Docker Compose setup starts this app with the backend. Apply
database migrations before opening the asset library:

```sh
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

For frontend-only development:

```sh
cd frontend
npm ci
npm run dev
```

Set `BACKEND_URL=http://localhost:8000` in `frontend/.env.local` when the backend
runs on your host. With Compose, the runtime value is `http://backend:8000`.
The setting is server-only; do not prefix it with `NEXT_PUBLIC_`.
Never place credentials in the backend URL.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Redirects to Dashboard |
| `/dashboard` | Live registered asset count and five recently added assets |
| `/assets` | Read-only library with name/description search, media filtering and pagination |
| `/productions` | Paginated production list with links to the editor |
| `/productions/[id]/editor` | Scene/shot requirements and derived asset selection readiness |
| `/settings` | Browser-local light/dark preference and live backend/database/cache readiness |
| `/api/health` | Existing server-side readiness proxy used by Docker |

Asset filters live in the URL and survive pagination and reloads. New searches
start on page one. Lists show 12 assets per page. Unknown media types and invalid
page values are normalized, and search text is bounded to the backend's limit.

The UI displays empty and unavailable states instead of fabricated records or
counts. Productions reads persisted plans; creation and locking use backend APIs. Asset mutation and
upload controls are outside this bootstrap. Appearance saves automatically in
localStorage and remains usable when browser storage is blocked.

## Structure

- `app/components`: shared navigation, layout elements, icons and appearance context
- `app/features/assets`: typed contracts, query normalization and reusable asset table
- `app/features/settings`: platform readiness view
- `app/lib/backend.ts`: server-only, bounded requests to the configured backend
- Route folders compose these components; loading, error and not-found boundaries
  keep navigation available.

Backend requests are uncached and time out after six seconds. Asset payloads are
validated before rendering; upstream error messages and internal URLs are not
shown. Dynamic pages render at request time, so builds do not need a live backend.
No API credentials are stored in browser preferences. This inherits the platform's
trusted-network deployment model; user authentication is not introduced here.

The responsive shell includes active navigation, visible keyboard focus, a skip
link, accessible field labels and table headers. Mobile keeps all four navigation
destinations visible and confines wide asset tables to horizontal scrolling.

## Checks

```sh
npm run format:check
npm run typecheck
npm run build
npx playwright install chromium
npm test
```

Browser tests use the production build, a deterministic local backend fixture
(port 8100), and a Next.js test server (port 3100). They cover desktop/mobile
navigation, filters, pagination, empty/error states, invalid query parameters,
appearance persistence, 404 recovery and the health proxy. No live Drive or
production data is used. Do not run the fixture as a production service.

The Frontend quality workflow runs these checks on pull requests. The existing
Docker workflow continues to build and exercise both development and production
images. The frontend production image still uses Next.js standalone output and a
non-root user.

See [Editor review](../backend/docs/editor-review.md) for readiness rules and optional display references.

Production titles link to `/productions/[id]/dashboard`: progress, assets ready/missing, AI gaps, sync status, import queue, latest imports and credits saved. Unknown AI/cost metrics are explicitly not tracked. See [metric definitions](../backend/docs/production-dashboard.md).
