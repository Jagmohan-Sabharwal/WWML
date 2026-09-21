import type { Asset } from "./data";
import { formatSize } from "./data";
import { Icon } from "@/app/components/ui-icon";

export function AssetTable({ items }: { items: Asset[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] text-left text-sm">
        <caption className="sr-only">
          Registered assets available for reuse
        </caption>
        <thead className="border-b border-line text-xs uppercase tracking-wider text-muted">
          <tr>
            <th scope="col" className="px-6 py-4 font-medium">
              Asset
            </th>
            <th scope="col" className="px-4 py-4 font-medium">
              Type
            </th>
            <th scope="col" className="px-4 py-4 font-medium">
              Size
            </th>
            <th scope="col" className="px-6 py-4 font-medium text-right">
              Added
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {items.map((asset) => (
            <tr key={asset.id} className="hover:bg-canvas">
              <td className="max-w-xs px-6 py-5">
                <div className="flex items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-soft text-accent">
                    <Icon name="film" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium" title={asset.name}>
                      {asset.name}
                    </p>
                    <p className="mt-1 truncate text-xs text-muted">
                      {asset.mime_type}
                    </p>
                  </div>
                </div>
              </td>
              <td className="px-4 py-5">
                <span className="rounded-full border border-line px-2.5 py-1 text-xs capitalize">
                  {asset.media_type}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-5 tabular-nums text-muted">
                {formatSize(asset.size_bytes)}
              </td>
              <td className="whitespace-nowrap px-6 py-5 text-right text-muted">
                <time dateTime={asset.created_at}>
                  {new Date(asset.created_at).toLocaleDateString("en-GB", {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                    timeZone: "UTC",
                  })}
                </time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
