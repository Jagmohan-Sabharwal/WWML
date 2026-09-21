import Link from "next/link";
export default function NotFound() {
  return (
    <div className="py-14">
      <p className="text-sm text-accent">404</p>
      <h1 className="mt-3 text-3xl font-semibold">
        This page isn’t in the workspace
      </h1>
      <Link
        href="/dashboard"
        className="mt-6 inline-block text-accent underline"
      >
        Return to dashboard
      </Link>
    </div>
  );
}
