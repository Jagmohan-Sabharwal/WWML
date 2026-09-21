import type { Metadata } from "next";
import { ActionLink, EmptyState, PageHeader, Panel } from "@/app/components/ui";

export const metadata: Metadata = { title: "Productions" };
export default function Productions() {
  return (
    <>
      <PageHeader
        eyebrow="From source to story"
        title="Productions"
        description="A dedicated space for the documentaries you’re bringing to life."
      />
      <Panel>
        <EmptyState
          title="The next story is taking shape"
          description="Production planning is coming next. While this workspace takes shape, explore your library and find the material for your next documentary."
        >
          <ActionLink href="/assets">Explore your library</ActionLink>
        </EmptyState>
      </Panel>
      <div className="mt-8 grid gap-6 sm:grid-cols-3">
        {[
          [
            "01",
            "Discover",
            "Begin with the footage and voices already in your library.",
          ],
          [
            "02",
            "Shape",
            "Develop a story around the strongest source material.",
          ],
          ["03", "Produce", "Bring your scenes together into a documentary."],
        ].map(([number, title, text]) => (
          <div key={number} className="border-t border-line pt-5">
            <p className="text-xs font-semibold tracking-widest text-accent">
              {number}
            </p>
            <h2 className="mt-3 font-semibold">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted">{text}</p>
          </div>
        ))}
      </div>
    </>
  );
}
