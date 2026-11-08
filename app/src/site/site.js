// Website pages: the home page at /, the live board at /board (and /live), a client view of one
// case at /case/<id>, the Mac collector at /download, and the favicon. Read-only and public;
// case data comes from the existing /api/board endpoints. Everything else returns null and
// falls through to the app's own routes (/tickets, /connect, /api/...).
import { BOARD_HTML } from "../board.js";
import { HOME_HTML } from "./home.js";
import { CASE_HTML, DOWNLOAD_HTML, FAVICON_SVG, collectorZip } from "./pages.js";
import { DEMO_HTML, DEMO_HOME_SNIPPET } from "./demo.js";

const page = (body) =>
  new Response(body, { headers: { "content-type": "text/html; charset=utf-8" } });

export function handleSite(request) {
  if (request.method !== "GET") return null;
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";

  // Demo mode (demo.js): /?demo=1#start keeps the home page but its form opens the in-browser walkthrough
  // at /demo instead of creating a ticket. Nothing reaches Naive or the database.
  if (path === "/" && url.searchParams.has("demo")) return page(HOME_HTML.replace("</body>", DEMO_HOME_SNIPPET + "</body>"));
  if (path === "/") return page(HOME_HTML);
  if (path === "/demo") return page(DEMO_HTML);
  if (path === "/board" || path === "/live") return page(BOARD_HTML);
  if (path === "/case" || /^\/case\/[A-Za-z0-9-]{1,40}$/.test(path)) return page(CASE_HTML);
  if (path === "/download") return page(DOWNLOAD_HTML);
  if (path === "/download/datacare-collect.zip") {
    const asked = url.searchParams.get("case") || "";
    const caseId = /^C-\d{4}$/.test(asked) ? asked : "";
    const name = caseId ? `datacare-collect-${caseId}.zip` : "datacare-collect.zip";
    return new Response(collectorZip(caseId), {
      headers: {
        "content-type": "application/zip",
        "content-disposition": `attachment; filename="${name}"`,
        "cache-control": "no-store",
      },
    });
  }
  if (path === "/favicon.svg" || path === "/favicon.ico") {
    return new Response(FAVICON_SVG, {
      headers: { "content-type": "image/svg+xml", "cache-control": "public, max-age=86400" },
    });
  }
  return null;
}
