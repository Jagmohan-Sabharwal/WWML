import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ActionLink,
  EmptyState,
  PageHeader,
  Panel,
  Unavailable,
} from "@/app/components/ui";
import { isId } from "@/app/features/editor/data";
import { getProductionDashboard } from "@/app/features/editor/dashboard-data";

export const metadata: Metadata = { title: "Production dashboard" };
export const dynamic = "force-dynamic";
function Metric({
  title,
  value,
  note,
}: {
  title: string;
  value: string | number;
  note: string;
}) {
  return (
    <Panel className="p-6">
      <h2 className="text-sm font-medium text-muted">{title}</h2>
      <p className="mt-3 break-words text-2xl font-semibold tabular-nums">
        {value}
      </p>
      <p className="mt-3 text-xs leading-5 text-muted">{note}</p>
    </Panel>
  );
}
export default async function Dashboard({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!isId(id)) notFound();
  const result = await getProductionDashboard(id);
  if (!result.ok)
    return (
      <>
        <PageHeader
          eyebrow="Production desk"
          title="Production dashboard"
          description="Readiness and shared-library activity."
        />
        <Unavailable message="We couldn’t load this production dashboard. The production may be unavailable or no longer exist." />
      </>
    );
  const data = result.data;
  return (
    <>
      <Link
        href="/productions"
        className="mb-5 inline-block text-sm font-medium text-accent underline"
      >
        All productions
      </Link>
      <PageHeader
        eyebrow="Production desk"
        title={data.production.name}
        description="Asset readiness for this production, with activity from your shared library."
      >
        <ActionLink href={"/productions/" + id + "/editor"}>
          Review assets
        </ActionLink>
      </PageHeader>
      <Panel className="mb-6 p-6">
        <h2 className="text-sm font-medium text-muted">Progress</h2>
        <p className="mt-3 text-4xl font-semibold">
          {data.progress_percent === null
            ? "Not planned"
            : data.progress_percent + "%"}
        </p>
        {data.progress_percent !== null && (
          <progress
            aria-label="Asset planning progress"
            className="mt-4 h-3 w-full accent-emerald-700"
            max={100}
            value={data.progress_percent}
          />
        )}
        <p className="mt-3 text-sm text-muted">
          Asset-planning readiness · {data.assets_ready} ready of{" "}
          {data.required_assets} requirements · {data.unplanned_shots} unplanned
          shots · {data.assets_to_review} selections need review.
        </p>
        <p className="mt-2 text-xs text-muted">
          This measures asset planning, not research, editing or publishing
          completion.
        </p>
      </Panel>
      <div className="mb-8 grid gap-4 sm:grid-cols-2">
        <Metric
          title="Assets Ready"
          value={data.assets_ready}
          note="Requirements with an active registry asset matching the locked selection."
        />
        <Metric
          title="Missing Assets"
          value={data.missing_assets}
          note="Requirements without a locked selection. Search the existing library first."
        />
        <Metric
          title="AI Gaps"
          value={data.ai_gaps ?? "Not tracked"}
          note="Missing assets are not automatically AI gaps. No generation decisions are recorded yet."
        />
        <Metric
          title="Credits Saved"
          value={data.credits_saved ?? "Not tracked"}
          note="Savings will appear when credit costs can be measured."
        />
      </div>
      <h2 className="mb-2 text-lg font-semibold">Shared library activity</h2>
      <p className="mb-4 text-sm text-muted">
        Sync and imports serve the entire library and are not attributed to this
        production.
      </p>
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <Metric
          title="Sync Status"
          value={
            data.latest_sync_job?.status.replaceAll("_", " ") ??
            "No recorded runs"
          }
          note="Latest recorded run; current worker activity may differ."
        />
        <Metric
          title="Import Queue"
          value={data.import_queue}
          note={
            "Waiting or being imported · " +
            data.failed_imports +
            " failed imports need attention and are not counted in this queue."
          }
        />
      </div>
      <Panel className="p-6">
        <h2 className="text-lg font-semibold">Latest Imports</h2>
        {data.latest_imports.length ? (
          <ul className="mt-4 divide-y divide-line">
            {data.latest_imports.map((item) => (
              <li key={item.id} className="py-4">
                <p className="break-words font-medium">{item.source_name}</p>
                <p className="mt-1 text-xs text-muted">
                  Completed ·{" "}
                  <time dateTime={item.updated_at}>
                    {new Date(item.updated_at)
                      .toISOString()
                      .replace("T", " ")
                      .slice(0, 19)}{" "}
                    UTC
                  </time>
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No completed imports"
            description="Completed shared-library imports will appear here, newest first."
          />
        )}
      </Panel>
    </>
  );
}
