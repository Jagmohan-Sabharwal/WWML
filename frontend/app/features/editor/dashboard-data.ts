import { readBackend, record } from "@/app/lib/backend";
import { isId, type Production } from "./data";

export type ProductionDashboard = {
  production: Production;
  progress_percent: number | null;
  assets_ready: number;
  missing_assets: number;
  assets_to_review: number;
  unplanned_shots: number;
  required_assets: number;
  ai_gaps: number | null;
  credits_saved: number | null;
  activity_scope: "shared_library";
  latest_sync_job: { status: string } | null;
  import_queue: number;
  failed_imports: number;
  latest_imports: {
    id: string;
    source_name: string;
    updated_at: string;
    status: string;
  }[];
};
const count = (value: unknown) =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
function valid(value: unknown): value is ProductionDashboard {
  if (
    !record(value) ||
    !record(value.production) ||
    !isId(value.production.id) ||
    typeof value.production.name !== "string" ||
    value.activity_scope !== "shared_library"
  )
    return false;
  if (
    ![
      "assets_ready",
      "missing_assets",
      "assets_to_review",
      "unplanned_shots",
      "required_assets",
      "import_queue",
      "failed_imports",
    ].every((key) => count(value[key]))
  )
    return false;
  if (
    value.progress_percent !== null &&
    !(
      typeof value.progress_percent === "number" &&
      Number.isFinite(value.progress_percent) &&
      value.progress_percent >= 0 &&
      value.progress_percent <= 100
    )
  )
    return false;
  if (value.ai_gaps !== null && !count(value.ai_gaps)) return false;
  if (
    value.credits_saved !== null &&
    !(
      typeof value.credits_saved === "number" &&
      Number.isFinite(value.credits_saved) &&
      value.credits_saved >= 0
    )
  )
    return false;
  if (
    value.latest_sync_job !== null &&
    !(
      record(value.latest_sync_job) &&
      [
        "pending",
        "running",
        "completed",
        "completed_with_errors",
        "failed",
      ].includes(String(value.latest_sync_job.status))
    )
  )
    return false;
  return (
    Array.isArray(value.latest_imports) &&
    value.latest_imports.length <= 5 &&
    value.latest_imports.every(
      (item) =>
        record(item) &&
        isId(item.id) &&
        typeof item.source_name === "string" &&
        item.status === "done" &&
        typeof item.updated_at === "string" &&
        Number.isFinite(Date.parse(item.updated_at)),
    )
  );
}
export const getProductionDashboard = (id: string) =>
  readBackend(
    "/api/v1/productions/" + encodeURIComponent(id) + "/dashboard",
    valid,
  );
