import type { Metadata } from "next";
import Link from "next/link";
import {
  EmptyState,
  PageHeader,
  Panel,
  Unavailable,
} from "@/app/components/ui";
import {
  assetQuery,
  getAssets,
  mediaTypes,
  pageHref,
  type SearchParams,
} from "@/app/features/assets/data";
import { AssetTable } from "@/app/features/assets/asset-table";

export const metadata: Metadata = { title: "Assets" };
export const dynamic = "force-dynamic";
export default async function Assets({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const query = assetQuery(await searchParams);
  const result = await getAssets(query);
  const filtered = query.has("q") || query.has("media_type");
  return (
    <>
      <PageHeader
        eyebrow="The shared library"
        title="Assets"
        description="Find a familiar scene. Discover a new possibility. Reuse the right asset for your next story."
      />
      <form
        key={query.toString()}
        action="/assets"
        method="get"
        role="search"
        className="mb-6 flex flex-wrap items-end gap-3"
      >
        <div className="min-w-48 flex-1">
          <label
            htmlFor="asset-search"
            className="mb-2 block text-xs font-semibold text-muted"
          >
            Search library
          </label>
          <input
            id="asset-search"
            name="q"
            type="search"
            maxLength={200}
            defaultValue={query.get("q") || ""}
            placeholder="Search names and descriptions…"
            className="w-full rounded-lg border border-line bg-surface px-4 py-3 text-sm"
          />
        </div>
        <div>
          <label
            htmlFor="asset-type"
            className="mb-2 block text-xs font-semibold text-muted"
          >
            Media type
          </label>
          <select
            id="asset-type"
            name="media_type"
            defaultValue={query.get("media_type") || ""}
            className="rounded-lg border border-line bg-surface px-4 py-3 text-sm"
          >
            <option value="">All types</option>
            {mediaTypes.map((type) => (
              <option key={type} value={type}>
                {type[0].toUpperCase() + type.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="rounded-lg bg-ink px-5 py-3 text-sm font-medium text-surface hover:opacity-85"
        >
          Search
        </button>
        {filtered && (
          <Link
            href="/assets"
            className="px-2 py-3 text-sm text-accent underline underline-offset-4"
          >
            Clear filters
          </Link>
        )}
      </form>
      {!result.ok ? (
        <Unavailable />
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">
            {result.data.total.toLocaleString("en-US")}{" "}
            {result.data.total === 1 ? "asset" : "assets"}
            {filtered ? " matching your search" : " in your library"}
          </p>
          <Panel>
            {result.data.items.length ? (
              <AssetTable items={result.data.items} />
            ) : (
              <EmptyState
                title={
                  filtered
                    ? "No matching assets"
                    : Number(query.get("page")) > 1
                      ? "No assets on this page"
                      : "A home for your source material"
                }
                description={
                  filtered
                    ? "Try another keyword or media type to explore your library."
                    : "Files registered or imported into WWML appear here. Start with the material you already have."
                }
              >
                {(filtered || Number(query.get("page")) > 1) && (
                  <Link
                    href="/assets"
                    className="font-medium text-accent underline"
                  >
                    Show all assets
                  </Link>
                )}
              </EmptyState>
            )}
          </Panel>
          {result.data.total_pages > 1 && (
            <nav
              aria-label="Asset pagination"
              className="mt-5 flex flex-wrap items-center justify-between gap-3 text-sm"
            >
              <p className="text-muted">
                Page {result.data.page} of {result.data.total_pages}
              </p>
              <div className="flex gap-3">
                {result.data.page > 1 && (
                  <Link
                    href={pageHref(query, result.data.page - 1)}
                    className="rounded-lg border border-line bg-surface px-4 py-2"
                  >
                    Previous
                  </Link>
                )}
                {result.data.page < result.data.total_pages && (
                  <Link
                    href={pageHref(query, result.data.page + 1)}
                    className="rounded-lg border border-line bg-surface px-4 py-2"
                  >
                    Next
                  </Link>
                )}
              </div>
            </nav>
          )}
        </>
      )}
    </>
  );
}
