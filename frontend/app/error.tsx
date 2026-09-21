"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-line bg-surface p-10">
      <h1 className="text-2xl font-semibold">
        Something interrupted your workspace
      </h1>
      <p className="mt-3 text-muted">Please try loading this page again.</p>
      <button
        onClick={reset}
        className="mt-6 rounded-lg bg-ink px-5 py-3 text-sm text-surface"
      >
        Try again
      </button>
    </div>
  );
}
