import Link from "next/link";
export function Pagination({
  path,
  page,
  totalPages,
}: {
  path: string;
  page: number;
  totalPages: number;
}) {
  if (totalPages < 2 && page === 1) return null;
  return (
    <nav
      aria-label="Production pagination"
      className="mt-6 flex flex-wrap items-center justify-between gap-4 text-sm"
    >
      <p className="text-muted">
        Page {page} · {totalPages} total pages
      </p>
      <div className="flex gap-4">
        {page > 1 && (
          <Link
            href={path + "?page=" + (page - 1)}
            className="font-medium text-accent underline"
          >
            Previous
          </Link>
        )}
        {page < totalPages && (
          <Link
            href={path + "?page=" + (page + 1)}
            className="font-medium text-accent underline"
          >
            Next
          </Link>
        )}
      </div>
    </nav>
  );
}
