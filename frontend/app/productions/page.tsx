import type { Metadata } from "next";
import Link from "next/link";
import {
  ActionLink,
  EmptyState,
  PageHeader,
  Panel,
  Unavailable,
} from "@/app/components/ui";
import type { SearchParams } from "@/app/features/assets/data";
import { getProductions, pageQuery } from "@/app/features/editor/data";
import { Pagination } from "@/app/features/editor/pagination";

export const metadata: Metadata = { title: "Productions" };
export const dynamic = "force-dynamic";
export default async function Productions({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const result = await getProductions(pageQuery(await searchParams));
  return (
    <>
      <PageHeader
        eyebrow="From source to story"
        title="Productions"
        description="Open a production to review scenes, shots and the assets selected for your edit."
      />
      {!result.ok ? (
        <Unavailable message="We couldn’t load your productions. Check platform status and try again." />
      ) : (
        <>
          <Panel>
            {result.data.items.length ? (
              <ul className="divide-y divide-line">
                {result.data.items.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-5 p-6"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-xs uppercase tracking-widest text-muted">
                        {item.status.replaceAll("_", " ")}
                      </p>
                      <h2 className="mt-2 break-words text-xl font-semibold">
                        <Link
                          href={"/productions/" + item.id + "/dashboard"}
                          className="underline underline-offset-4"
                        >
                          {item.name}
                        </Link>
                      </h2>
                      {item.description && (
                        <p className="mt-2 break-words text-sm text-muted">
                          {item.description}
                        </p>
                      )}
                    </div>
                    <ActionLink href={"/productions/" + item.id + "/editor"}>
                      Open editor
                    </ActionLink>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title={
                  result.data.page > 1
                    ? "No productions on this page"
                    : "Your next story starts here"
                }
                description="Productions created in WWML appear here with their scene and shot plans."
              >
                <Link
                  href="/assets"
                  className="font-medium text-accent underline"
                >
                  Explore your library
                </Link>
              </EmptyState>
            )}
          </Panel>
          <Pagination
            path="/productions"
            page={result.data.page}
            totalPages={result.data.total_pages}
          />
        </>
      )}
    </>
  );
}
