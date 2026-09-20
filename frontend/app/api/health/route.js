export const dynamic = "force-dynamic";

export async function GET() {
  try {
    // Runtime-only server configuration: never expose internal URLs to the browser.
    const backend = process.env.BACKEND_URL || "http://backend:8000";
    const response = await fetch(new URL("/health/ready", backend), {
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    return Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json({ status: "unavailable" }, { status: 503 });
  }
}
