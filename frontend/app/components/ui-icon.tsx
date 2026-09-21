import type { CSSProperties } from "react";

export type IconName =
  | "dashboard"
  | "assets"
  | "productions"
  | "settings"
  | "arrow"
  | "film"
  | "search";
const paths: Record<IconName, string> = {
  dashboard: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  assets: "M3 6h7l2 3h9v11H3z M3 6V4h7l2 2h9v3",
  productions: "M3 7h18v14H3z M3 7V3h18v4 M7 3l3 4 M14 3l3 4",
  settings: "M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  film: "M4 3h16v18H4z M4 8h16 M4 16h16 M8 3v18 M16 3v18",
  search: "M21 21l-6-6 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
};
export function Icon({
  name,
  className = "",
  style,
}: {
  name: IconName;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      style={style}
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  );
}
