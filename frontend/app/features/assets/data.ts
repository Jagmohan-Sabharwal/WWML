import { readBackend, record } from "@/app/lib/backend";

export const mediaTypes = [
  "video",
  "audio",
  "image",
  "document",
  "other",
] as const;
export type MediaType = (typeof mediaTypes)[number];
export type Asset = {
  id: string;
  name: string;
  description: string | null;
  media_type: MediaType;
  mime_type: string;
  size_bytes: number;
  created_at: string;
};
export type AssetPage = {
  items: Asset[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};
export type SearchParams = Record<string, string | string[] | undefined>;
const single = (value: string | string[] | undefined) =>
  typeof value === "string" ? value : "";
export function assetQuery(params: SearchParams): URLSearchParams {
  const query = new URLSearchParams({ page_size: "12" });
  const page = single(params.page);
  query.set(
    "page",
    /^\d+$/.test(page) && Number(page) >= 1 && Number(page) <= 1000000
      ? String(Number(page))
      : "1",
  );
  const q = single(params.q).trim().slice(0, 200);
  if (q) query.set("q", q);
  const media = single(params.media_type);
  if (mediaTypes.includes(media as MediaType)) query.set("media_type", media);
  return query;
}
function isAsset(value: unknown): value is Asset {
  return (
    record(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    (value.description === null || typeof value.description === "string") &&
    mediaTypes.includes(value.media_type as MediaType) &&
    typeof value.mime_type === "string" &&
    typeof value.size_bytes === "number" &&
    Number.isFinite(value.size_bytes) &&
    value.size_bytes >= 0 &&
    typeof value.created_at === "string" &&
    !Number.isNaN(Date.parse(value.created_at))
  );
}
function isAssetPage(value: unknown): value is AssetPage {
  return (
    record(value) &&
    Array.isArray(value.items) &&
    value.items.every(isAsset) &&
    ["total", "total_pages", "page", "page_size"].every(
      (key) =>
        typeof value[key] === "number" &&
        Number.isSafeInteger(value[key]) &&
        value[key] >= 0,
    ) &&
    Number(value.page) >= 1 &&
    Number(value.page_size) >= 1
  );
}
export const getAssets = (query: URLSearchParams) =>
  readBackend("/assets?" + query, isAssetPage);
export function pageHref(query: URLSearchParams, page: number): string {
  const next = new URLSearchParams(query);
  next.set("page", String(page));
  next.delete("page_size");
  return "/assets?" + next;
}
export function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  const units = ["KB", "MB", "GB", "TB"];
  const power = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 4);
  return (bytes / 1024 ** power).toFixed(1) + " " + units[power - 1];
}
