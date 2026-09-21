import type { Metadata } from "next";
import Link from "next/link";
import {
  ActionLink,
  EmptyState,
  PageHeader,
  Panel,
  Unavailable,
} from "@/app/components/ui";
import { Icon } from "@/app/components/ui-icon";
import { getAssets } from "@/app/features/assets/data";
import { AssetTable } from "@/app/features/assets/asset-table";

export const metadata: Metadata = { title: "Dashboard" };
export const dynamic = "force-dynamic";
export default async function Dashboard() {
  const assets = await getAssets(
    new URLSearchParams({ page: "1", page_size: "5" }),
  );
  return (
    <>
      <PageHeader
        eyebrow="The production desk"
        title="Every story starts here."
        description="Your library, your projects, and the next step in your documentary."
      />
      <section className="relative mb-7 overflow-hidden rounded-xl bg-[#243e32] px-7 py-9 text-white sm:px-10">
        <div
          aria-hidden="true"
          className="absolute -right-12 -top-20 size-80 rounded-full border-[36px] border-white/5"
        />
        <div className="relative max-w-xl">
          <p className="text-xs uppercase tracking-[.2em] text-[#c5dcae]">
            Discover before you create
          </p>
          <h2 className="mt-4 text-2xl font-medium tracking-tight sm:text-3xl">
            Your next scene may already
            <br className="hidden sm:block" /> be in the library.
          </h2>
          <p className="mt-4 max-w-md text-sm leading-6 text-[#c0d0c5]">
            Find the footage, voices, and details you’ve already collected. Give
            existing assets a new part in your next story.
          </p>
          <Link
            href="/assets"
            className="mt-6 inline-flex items-center gap-3 rounded-lg bg-[#d8e8be] px-5 py-3 text-sm font-semibold text-[#182c26] hover:bg-[#e7f1d6]"
          >
            Explore assets <Icon name="arrow" />
          </Link>
        </div>
      </section>
      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <Panel className="p-6">
          <p className="text-sm text-muted">Registered assets</p>
          <p className="mt-3 text-3xl font-semibold tabular-nums">
            {assets.ok ? assets.data.total.toLocaleString("en-US") : "—"}
          </p>
          <p className="mt-2 text-xs text-muted">
            {assets.ok
              ? "Available in your shared library"
              : "Library currently unavailable"}
          </p>
        </Panel>
        <Panel className="p-6">
          <p className="text-sm text-muted">Production workspace</p>
          <p className="mt-3 text-xl font-semibold">
            Ready for the next chapter
          </p>
          <Link
            href="/productions"
            className="mt-3 inline-block text-xs font-semibold text-accent underline underline-offset-4"
          >
            View productions
          </Link>
        </Panel>
        <Panel className="p-6">
          <p className="text-sm text-muted">Your workspace</p>
          <p className="mt-3 text-xl font-semibold">Settle into your studio</p>
          <Link
            href="/settings"
            className="mt-3 inline-block text-xs font-semibold text-accent underline underline-offset-4"
          >
            Preferences & platform status
          </Link>
        </Panel>
      </div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Recently added</h2>
        <Link href="/assets" className="text-sm font-medium text-accent">
          View all assets →
        </Link>
      </div>
      {!assets.ok ? (
        <Unavailable />
      ) : (
        <Panel>
          {assets.data.items.length ? (
            <AssetTable items={assets.data.items} />
          ) : (
            <EmptyState
              title="Your library starts with one asset"
              description="Imported files will appear here, ready to discover and reuse."
            >
              <ActionLink href="/assets">Go to assets</ActionLink>
            </EmptyState>
          )}
        </Panel>
      )}
    </>
  );
}
