// Deterministic contract fixture used only by browser tests; never bundled into app.
import { createServer } from "node:http";
const assets = Array.from({ length: 14 }, (_, index) => ({
  id: "asset-" + index,
  name: index === 13 ? "Forest soundscape" : "Coast interview " + (index + 1),
  description: "Documentary source material",
  media_type: index === 13 ? "audio" : "video",
  mime_type: index === 13 ? "audio/wav" : "video/mp4",
  size_bytes: 1024 * 1024 * 24,
  created_at: "2026-01-15T12:00:00Z",
}));
const server = createServer((request, response) => {
  const url = new URL(request.url || "/", "http://localhost");
  response.setHeader("Content-Type", "application/json");
  if (url.pathname === "/health/ready") {
    response.end(
      JSON.stringify({ status: "ok", checks: { postgres: true, redis: true } }),
    );
    return;
  }
  if (url.pathname !== "/assets") {
    response.writeHead(404).end("{}");
    return;
  }
  const q = url.searchParams.get("q") || "";
  if (q === "unavailable") {
    response.writeHead(503).end('{"detail":"private-upstream-error"}');
    return;
  }
  if (q === "malformed") {
    response.end('{"items":[{"name":"broken"}]}');
    return;
  }
  const media = url.searchParams.get("media_type");
  const items = assets.filter(
    (asset) =>
      (!media || asset.media_type === media) &&
      asset.name.toLowerCase().includes(q.toLowerCase()),
  );
  const page = Number(url.searchParams.get("page") || 1);
  const size = Number(url.searchParams.get("page_size") || 12);
  response.end(
    JSON.stringify({
      items: items.slice((page - 1) * size, page * size),
      total: items.length,
      page,
      page_size: size,
      total_pages: Math.ceil(items.length / size),
    }),
  );
});
server.listen(8100, "127.0.0.1");
process.on("SIGTERM", () => server.close());
