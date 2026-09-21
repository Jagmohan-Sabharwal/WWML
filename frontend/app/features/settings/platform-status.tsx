import { readBackend, record } from "@/app/lib/backend";

type Health = { status: "ok"; checks: { postgres: boolean; redis: boolean } };
const getHealth = () =>
  readBackend(
    "/health/ready",
    (value): value is Health =>
      record(value) &&
      value.status === "ok" &&
      record(value.checks) &&
      typeof value.checks.postgres === "boolean" &&
      typeof value.checks.redis === "boolean",
  );
export async function PlatformStatus() {
  const result = await getHealth();
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Platform status</h2>
        <span className="rounded-full bg-soft px-3 py-1 text-xs font-medium">
          {result.ok ? "Connected" : "Needs attention"}
        </span>
      </div>
      <p className="mt-2 text-sm text-muted">
        Service availability at the time this page was loaded.
      </p>
      <dl className="mt-6 divide-y divide-line">
        {["Backend", "Database", "Cache"].map((label, index) => (
          <div key={label} className="flex justify-between py-4 text-sm">
            <dt>{label}</dt>
            <dd className="font-medium">
              {result.ok
                ? index === 0 ||
                  (index === 1
                    ? result.data.checks.postgres
                    : result.data.checks.redis)
                  ? "Available"
                  : "Unavailable"
                : "Unavailable"}
            </dd>
          </div>
        ))}
      </dl>
      {!result.ok && (
        <p role="status" className="mt-3 text-sm text-muted">
          The platform is not ready. Your library will be available when its
          services reconnect.
        </p>
      )}
    </div>
  );
}
