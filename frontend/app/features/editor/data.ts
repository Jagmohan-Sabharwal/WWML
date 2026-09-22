import { readBackend, record } from "@/app/lib/backend";
import type { SearchParams } from "@/app/features/assets/data";

type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};
export type Production = {
  id: string;
  name: string;
  description: string | null;
  status: string;
};
type Node = { id: string; name: string; position: number };
export type EditorRow = {
  sequence: Node;
  scene: Node;
  shot: Node;
  requirement: (Node & { media_type: string }) | null;
  selected_asset: { id: string; name: string; reference: string } | null;
  locked_asset: {
    required_asset_id: string;
    asset_id: string;
    checksum: string;
    storage_uri: string;
    locked_at: string;
  } | null;
  status: "READY" | "MISSING" | "REVIEW" | "UNPLANNED";
  reason: string;
};
export type EditorPage = Page<EditorRow> & { production: Production };
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const isId = (value: unknown): value is string =>
  typeof value === "string" && uuidPattern.test(value);
const nonnegative = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const text = (value: unknown): value is string =>
  typeof value === "string" && value.length > 0;
function production(value: unknown): value is Production {
  return (
    record(value) &&
    isId(value.id) &&
    text(value.name) &&
    (value.description === null || typeof value.description === "string") &&
    ["draft", "in_production", "completed", "archived"].includes(
      String(value.status),
    )
  );
}
function node(value: unknown): value is Node {
  return (
    record(value) &&
    isId(value.id) &&
    text(value.name) &&
    nonnegative(value.position) &&
    value.position > 0
  );
}
function row(value: unknown): value is EditorRow {
  if (
    !record(value) ||
    !node(value.sequence) ||
    !node(value.scene) ||
    !node(value.shot) ||
    !text(value.reason) ||
    !["READY", "MISSING", "REVIEW", "UNPLANNED"].includes(String(value.status))
  )
    return false;
  const requirement = value.requirement;
  if (
    requirement !== null &&
    !(
      record(requirement) &&
      ["video", "audio", "image", "document", "other"].includes(
        String(requirement.media_type),
      ) &&
      node(requirement)
    )
  )
    return false;
  const asset = value.selected_asset;
  if (
    asset !== null &&
    !(
      record(asset) &&
      isId(asset.id) &&
      text(asset.name) &&
      text(asset.reference)
    )
  )
    return false;
  const lock = value.locked_asset;
  if (
    lock !== null &&
    !(
      record(lock) &&
      isId(lock.required_asset_id) &&
      isId(lock.asset_id) &&
      typeof lock.checksum === "string" &&
      /^[0-9a-f]{64}$/.test(lock.checksum) &&
      text(lock.storage_uri) &&
      typeof lock.locked_at === "string" &&
      Number.isFinite(Date.parse(lock.locked_at))
    )
  )
    return false;
  if (value.status === "READY" && (!requirement || !asset || !lock))
    return false;
  return true;
}
function page<T>(
  value: unknown,
  valid: (item: unknown) => item is T,
): value is Page<T> {
  return (
    record(value) &&
    Array.isArray(value.items) &&
    value.items.every(valid) &&
    nonnegative(value.total) &&
    nonnegative(value.page) &&
    value.page > 0 &&
    nonnegative(value.page_size) &&
    value.page_size > 0 &&
    value.page_size <= 100 &&
    nonnegative(value.total_pages) &&
    value.total_pages === Math.ceil(value.total / value.page_size) &&
    value.items.length <= value.page_size
  );
}
function editor(value: unknown): value is EditorPage {
  return record(value) && production(value.production) && page(value, row);
}
export function pageQuery(params: SearchParams): URLSearchParams {
  const raw = typeof params.page === "string" ? params.page : "";
  const number = /^\d+$/.test(raw) ? Number(raw) : 1;
  return new URLSearchParams({
    page: String(
      Number.isSafeInteger(number) && number >= 1 && number <= 1000000
        ? number
        : 1,
    ),
    page_size: "20",
  });
}
export const getProductions = (query: URLSearchParams) =>
  readBackend(
    "/api/v1/productions?" + query,
    (value): value is Page<Production> => page(value, production),
  );
export const getEditor = (id: string, query: URLSearchParams) =>
  readBackend(
    "/api/v1/productions/" + encodeURIComponent(id) + "/editor?" + query,
    editor,
  );
