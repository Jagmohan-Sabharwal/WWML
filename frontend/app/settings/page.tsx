import type { Metadata } from "next";
import { PageHeader, Panel } from "@/app/components/ui";
import { AppearanceSettings } from "@/app/components/appearance";
import { PlatformStatus } from "@/app/features/settings/platform-status";

export const metadata: Metadata = { title: "Settings" };
export const dynamic = "force-dynamic";
export default function Settings() {
  return (
    <>
      <PageHeader
        eyebrow="Make yourself at home"
        title="Settings"
        description="Personalize your workspace and check the services behind your library."
      />
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Panel className="p-6 sm:p-8">
            <AppearanceSettings />
          </Panel>
          <Panel className="p-6 sm:p-8">
            <h2 className="text-lg font-semibold">Workspace</h2>
            <dl className="mt-5 space-y-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Name</dt>
                <dd>WWML</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Focus</dt>
                <dd>Documentary production</dd>
              </div>
            </dl>
          </Panel>
        </div>
        <Panel className="p-6 sm:p-8">
          <PlatformStatus />
        </Panel>
      </div>
    </>
  );
}
