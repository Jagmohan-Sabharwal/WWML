import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  EmptyState,
  PageHeader,
  Panel,
  Unavailable,
} from "@/app/components/ui";
import type { SearchParams } from "@/app/features/assets/data";
import { getEditor, isId, pageQuery } from "@/app/features/editor/data";
import { Pagination } from "@/app/features/editor/pagination";

export const metadata: Metadata = { title: "Production editor" };
export const dynamic = "force-dynamic";
const badge = {
  READY: "bg-emerald-100 text-emerald-900",
  MISSING: "bg-amber-100 text-amber-900",
  REVIEW: "bg-orange-100 text-orange-900",
  UNPLANNED: "bg-slate-100 text-slate-800",
};
export default async function Editor({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { id } = await params;
  if (!isId(id)) notFound();
  const result = await getEditor(id, pageQuery(await searchParams));
  return (
    <>
      <Link
        href="/productions"
        className="mb-5 inline-block text-sm font-medium text-accent underline"
      >
        All productions
      </Link>
      <PageHeader
        eyebrow="Editor · Asset review"
        title={result.ok ? result.data.production.name : "Production editor"}
        description="Review each scene, shot and required asset before beginning the edit."
      />
      <p className="mb-6 text-sm text-muted">
        READY means the locked selection matches the active registry record.
        Media playback and file availability are not checked here.
      </p>
      {!result.ok ? (
        <Unavailable message="This production could not be loaded. It may be unavailable or no longer exist." />
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">
            {result.data.total} requirement and unplanned-shot entries
          </p>
          {result.data.items.length ? (
            <div className="space-y-5">
              {result.data.items.map((row) => (
                <article
                  key={row.requirement?.id ?? row.shot.id}
                  aria-label={row.shot.name}
                  className="rounded-xl border border-line bg-surface p-6"
                >
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <p className="min-w-0 break-words text-xs uppercase tracking-widest text-muted">
                      Sequence {row.sequence.position} · {row.sequence.name}
                    </p>
                    <span
                      className={
                        "rounded-full px-3 py-1 text-xs font-bold " +
                        badge[row.status]
                      }
                    >
                      {row.status}
                    </span>
                  </div>
                  <dl className="grid gap-5 sm:grid-cols-3">
                    <div className="min-w-0">
                      <dt className="text-xs font-semibold uppercase tracking-wider text-muted">
                        Scene
                      </dt>
                      <dd className="mt-2 break-words text-lg font-semibold">
                        {row.scene.name}
                      </dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-xs font-semibold uppercase tracking-wider text-muted">
                        Shot
                      </dt>
                      <dd className="mt-2 break-words text-lg font-semibold">
                        {row.shot.name}
                      </dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-xs font-semibold uppercase tracking-wider text-muted">
                        Required asset
                      </dt>
                      <dd className="mt-2 break-words text-lg font-semibold">
                        {row.selected_asset?.reference ??
                          row.requirement?.name ??
                          "Not defined"}
                      </dd>
                      {row.selected_asset && row.requirement && (
                        <dd className="mt-1 break-words text-sm text-muted">
                          {row.requirement.name}
                        </dd>
                      )}
                    </div>
                  </dl>
                  <p className="mt-5 border-t border-line pt-4 text-sm text-muted">
                    {row.reason}
                  </p>
                  {row.status === "MISSING" && (
                    <Link
                      href={
                        "/assets?media_type=" +
                        encodeURIComponent(row.requirement?.media_type ?? "")
                      }
                      className="mt-3 inline-block text-sm font-medium text-accent underline"
                    >
                      Find an existing asset
                    </Link>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <Panel>
              <EmptyState
                title={
                  result.data.page > 1
                    ? "No entries on this page"
                    : "No shots planned yet"
                }
                description="Create sequences, scenes and shots for this production to begin reviewing required assets."
              />
            </Panel>
          )}
          <Pagination
            path={"/productions/" + id + "/editor"}
            page={result.data.page}
            totalPages={result.data.total_pages}
          />
        </>
      )}
    </>
  );
}
