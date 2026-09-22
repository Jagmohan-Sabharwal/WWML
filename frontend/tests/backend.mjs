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
  const id = (n) => "00000000-0000-0000-0000-" + String(n).padStart(12, "0");
  const production = {
    id: id(1),
    name: "Video6",
    description: "Morning routine documentary",
    status: "draft",
  };
  const pageOf = (items, extra = {}) => {
    const page = Number(url.searchParams.get("page") || 1);
    const size = Number(url.searchParams.get("page_size") || 20);
    response.end(
      JSON.stringify({
        items: items.slice((page - 1) * size, page * size),
        total: items.length,
        page,
        page_size: size,
        total_pages: Math.ceil(items.length / size),
        ...extra,
      }),
    );
  };
  if (url.pathname === "/api/v1/productions") {
    pageOf([production]);
    return;
  }
  if (url.pathname.endsWith("/editor")) {
    if (url.pathname.includes(id(2))) {
      pageOf([], { production: { ...production, id: id(2) } });
      return;
    }
    if (url.pathname.includes(id(3))) {
      response.writeHead(503).end('{"detail":"private-editor-error"}');
      return;
    }
    if (url.pathname.includes(id(4))) {
      response.end('{"items":[{"status":"READY"}]}');
      return;
    }
    if (!url.pathname.includes(id(1))) {
      response.writeHead(404).end("{}");
      return;
    }
    const label = (n, name, position = 1) => ({ id: id(n), name, position });
    const rows = Array.from({ length: 21 }, (_, index) => {
      const status = ["READY", "MISSING", "REVIEW", "UNPLANNED"][index % 4];
      const locked = ["READY", "REVIEW"].includes(status);
      const requirement =
        status === "UNPLANNED"
          ? null
          : { ...label(100 + index, "Bedroom footage"), media_type: "video" };
      return {
        sequence: label(10, "Opening"),
        scene: label(11, "Morning Routine"),
        shot: label(
          20 + index,
          index === 0 ? "Luxury Bedroom" : "Shot " + (index + 1),
          index + 1,
        ),
        requirement,
        selected_asset: locked
          ? {
              id: id(500 + index),
              name: "Bedroom master",
              reference: "WWML-VID-000045",
            }
          : null,
        locked_asset: locked
          ? {
              required_asset_id: requirement.id,
              asset_id: id(500 + index),
              checksum: "a".repeat(64),
              storage_uri: "file:///private/assets/bedroom.mp4",
              locked_at: "2026-01-15T12:00:00Z",
            }
          : null,
        status,
        reason:
          status === "READY"
            ? "The locked selection matches the active registry record."
            : "Selection requires attention.",
      };
    });
    pageOf(rows, { production });
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
