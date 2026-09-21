import "server-only";

export type Result<T> = { ok: true; data: T } | { ok: false };
/** Fixed server-controlled origin. Never return credentials, internal URLs or upstream errors. */
export async function readBackend<T>(
  path: string,
  validate: (value: unknown) => value is T,
): Promise<Result<T>> {
  try {
    const response = await fetch(
      new URL(path, process.env.BACKEND_URL || "http://backend:8000"),
      {
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(6000),
      },
    );
    if (!response.ok) return { ok: false };
    const data: unknown = await response.json();
    return validate(data) ? { ok: true, data } : { ok: false };
  } catch {
    return { ok: false };
  }
}
export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
