const MAX_BODY_SIZE = 25 * 1024 * 1024;
const ALLOWED_ORIGIN = "https://hoppscotch.io";
const PAGE_SIZE = 25;
const PUBLIC_BASE = "https://tangthu.pages.dev";

function xmlEscape(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"
  })[ch]);
}

function atomLink(rel, href, type = "application/atom+xml;profile=opds-catalog") {
  return `<link rel="${xmlEscape(rel)}" href="${xmlEscape(href)}" type="${xmlEscape(type)}"/>`;
}

function feedStart(title, id, updated) {
  return `<?xml version="1.0" encoding="UTF-8"?>` +
    `<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">` +
    `<id>${xmlEscape(id)}</id><title>${xmlEscape(title)}</title>` +
    `<updated>${xmlEscape(updated || new Date().toISOString())}</updated>`;
}

function safeSegment(value) {
  return encodeURIComponent(String(value));
}

async function readJSON(bucket, key) {
  const object = await bucket.get(key);
  if (!object) return null;
  return object.json();
}

function mimeFor(item) {
  if (item.mime) return item.mime;
  const ext = String(item.name || "").split(".").pop().toLowerCase();
  const map = {
    epub: "application/epub+zip", pdf: "application/pdf",
    mobi: "application/x-mobipocket-ebook", azw3: "application/vnd.amazon.ebook",
    txt: "text/plain", zip: "application/zip", rar: "application/vnd.rar",
    cbz: "application/vnd.comicbook+zip", cpfont: "application/octet-stream",
    ttf: "font/ttf", otf: "font/otf"
  };
  return map[ext] || "application/octet-stream";
}

function fileInfo(item) {
  const size = Number(item.size || 0);
  const formatted = size < 1024 ? `${size} B` :
    size < 1024 * 1024 ? `${(size / 1024).toFixed(1)} KB` :
    size < 1024 * 1024 * 1024 ? `${(size / 1048576).toFixed(1)} MB` :
    `${(size / 1073741824).toFixed(2)} GB`;
  return `${formatted} · ${mimeFor(item)} · Modified: ${item.modified || ""}`;
}

function renderFeed({ title, id, updated, folders, books, page, branchId, feedPath }) {
  const pages = Math.max(1, Math.ceil(books.length / PAGE_SIZE));
  const current = Math.min(Math.max(1, page), pages);
  const start = (current - 1) * PAGE_SIZE;
  const chunk = books.slice(start, start + PAGE_SIZE);
  let xml = feedStart(title, id, updated);
  if (feedPath.endsWith("/index.xml")) {
    xml += atomLink("start", `${PUBLIC_BASE}/opds/index.xml`);
  }
  if (current > 1) xml += atomLink("previous", `${PUBLIC_BASE}${feedPath}?page=${current - 1}`);
  if (current < pages) xml += atomLink("next", `${PUBLIC_BASE}${feedPath}?page=${current + 1}`);

  for (const folder of folders) {
    const href = `${PUBLIC_BASE}/opds/branch/${safeSegment(branchId)}/${safeSegment(folder.id)}.xml`;
    xml += `<entry><title>${xmlEscape(folder.name)}</title><id>${xmlEscape(`urn:tangthu:folder:${folder.id}`)}</id>${atomLink("subsection", href)}</entry>`;
  }
  for (const item of chunk) {
    const modified = item.modified || updated || new Date().toISOString();
    const acquisition = `https://drive.usercontent.google.com/download?id=${encodeURIComponent(item.id)}&export=download&confirm=t`;
    xml += `<entry><title>${xmlEscape(item.name)}</title><id>${xmlEscape(`urn:tangthu:file:${item.id}`)}</id>` +
      `<updated>${xmlEscape(modified)}</updated><content type="text">${xmlEscape(fileInfo(item))}</content>` +
      `<link rel="http://opds-spec.org/acquisition" href="${xmlEscape(acquisition)}" length="${Number(item.size || 0)}" mtime="${xmlEscape(modified)}" type="${xmlEscape(mimeFor(item))}"/></entry>`;
  }
  return xml + "</feed>";
}

async function serveOPDS(request, env, url) {
  const path = url.pathname.replace(/\/+$/, "") || "/opds";
  const headers = {
    "Content-Type": "application/atom+xml; charset=utf-8",
    "Cache-Control": "public, max-age=60",
    "Access-Control-Allow-Origin": "*"
  };

  if (path === "/opds" || path === "/opds/index.xml") {
    const catalog = await readJSON(env.BUCKET, "opds/branches.json");
    if (!catalog || !Array.isArray(catalog.branches)) {
      return new Response("OPDS catalog is not published", { status: 503, headers });
    }
    const now = new Date().toISOString();
    let xml = feedStart("TÀNG THƯ", "urn:tangthu:catalog", now);
    const orderedBranches = catalog.branches.slice().sort((a, b) => {
      const aName = String(a.name || "").trim();
      const bName = String(b.name || "").trim();
      const aVN = /^VN/i.test(aName);
      const bVN = /^VN/i.test(bName);
      if (aVN !== bVN) return aVN ? -1 : 1;
      return aName.localeCompare(bName, "vi", { sensitivity: "base" });
    });
    for (const branch of orderedBranches) {
      const href = `${PUBLIC_BASE}/opds/branch/${safeSegment(branch.id)}/index.xml`;
      xml += `<entry><title>${xmlEscape(branch.name)}</title><id>${xmlEscape(`urn:tangthu:shelf:${branch.id}`)}</id>${atomLink("subsection", href)}</entry>`;
    }
    return new Response(xml + "</feed>", { headers });
  }

  const match = path.match(/^\/opds\/branch\/([^/]+)\/([^/]+)$/);
  if (!match) return new Response("Not found", { status: 404, headers });
  let branchId, leaf;
  try {
    branchId = decodeURIComponent(match[1]);
    leaf = decodeURIComponent(match[2]);
  } catch {
    return new Response("Invalid path", { status: 400, headers });
  }

  const index = await readJSON(env.BUCKET, `opds/branches/${branchId}.json`);
  if (!index || index.branch_id !== branchId || !Array.isArray(index.items)) {
    return new Response("Shelf index not found", { status: 404, headers });
  }

  const parentId = leaf === "index.xml" ? index.root_folder_id : leaf.endsWith(".xml") ? leaf.slice(0, -4) : "";
  if (!parentId) return new Response("Invalid feed path", { status: 400, headers });

  const children = index.items.filter(item => item.parent_id === parentId);
  const folders = children.filter(item => item.folder);
  const books = children.filter(item => !item.folder);
  const folderMeta = index.items.find(item => item.folder && item.id === parentId);
  const title = leaf === "index.xml" ? (index.name || branchId) :
    `${index.name || branchId} / ${folderMeta ? folderMeta.name : parentId}`;
  const pageRaw = Number(url.searchParams.get("page") || "1");
  const page = Number.isInteger(pageRaw) && pageRaw > 0 ? pageRaw : 1;
  const xml = renderFeed({
    title, id: `urn:tangthu:shelf:${branchId}:folder:${parentId}`,
    updated: index.updated_at, folders, books, page, branchId,
    feedPath: `/opds/branch/${safeSegment(branchId)}/${safeSegment(leaf)}`
  });
  return new Response(xml, { headers });
}

async function cleanupSnapshotGenerations(request, env, json, path) {
  const match = path.match(/^\/v1\/snapshots\/([^/]+)\/cleanup$/);
  if (!match) return json({ error: "Not found" }, 404);
  if (request.method !== "POST") {
    return json({ error: "Method not allowed" }, 405, { Allow: "POST, OPTIONS" });
  }

  let branchId;
  try {
    branchId = decodeURIComponent(match[1]);
  } catch {
    return json({ error: "Invalid branch id" }, 400);
  }
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(branchId)) {
    return json({ error: "Invalid branch id" }, 400);
  }

  let body;
  try {
    const raw = await request.text();
    if (raw.length > 4096) return json({ error: "Request body too large" }, 413);
    body = JSON.parse(raw);
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  const generationId = String(body && body.generation_id || "");
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(generationId)) {
    return json({ error: "Invalid generation_id" }, 400);
  }

  // Never trust a caller-supplied generation alone: the current manifest must
  // point to it and explicitly mark it complete before any deletion is allowed.
  const manifestKey = `snapshots/${branchId}/manifest.json`;
  let manifest;
  try {
    manifest = await readJSON(env.BUCKET, manifestKey);
  } catch (error) {
    return json({ error: "Could not read snapshot manifest", detail: String(error.message || error) }, 500);
  }
  if (!manifest || manifest.branch_id !== branchId ||
      manifest.generation_id !== generationId || manifest.complete !== true) {
    return json({ error: "Manifest does not confirm this completed generation", branch_id: branchId }, 409);
  }

  const generationsPrefix = `snapshots/${branchId}/generations/`;
  const keepPrefix = `${generationsPrefix}${generationId}/`;
  let cursor;
  let deleted = 0;
  let scanned = 0;
  let pages = 0;

  do {
    const listed = await env.BUCKET.list({ prefix: generationsPrefix, limit: 1000, cursor });
    pages++;
    const objects = Array.isArray(listed.objects) ? listed.objects : [];
    scanned += objects.length;
    const oldKeys = objects
      .map(object => object.key)
      .filter(key => typeof key === "string" && key.startsWith(generationsPrefix) && !key.startsWith(keepPrefix));

    // R2 accepts up to 1,000 keys per bulk delete; list pages are capped at 1,000.
    if (oldKeys.length) {
      await env.BUCKET.delete(oldKeys);
      deleted += oldKeys.length;
    }

    cursor = listed.truncated ? listed.cursor : undefined;
  } while (cursor);

  return json({
    success: true,
    branch_id: branchId,
    kept_generation: generationId,
    scanned_objects: scanned,
    deleted_objects: deleted,
    list_pages: pages
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": origin === ALLOWED_ORIGIN ? ALLOWED_ORIGIN : "null",
      "Access-Control-Allow-Methods": "GET, PUT, DELETE, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin"
    };
    const json = (data, status = 200, extra = {}) =>
      Response.json(data, { status, headers: { ...cors, ...extra } });

    if (request.method === "OPTIONS") {
      if (origin !== ALLOWED_ORIGIN) return new Response(null, { status: 403 });
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname.startsWith("/opds")) {
      if (!env.BUCKET) return new Response("R2 bucket binding BUCKET is missing", { status: 500 });
      try {
        return await serveOPDS(request, env, url);
      } catch (error) {
        return new Response(`OPDS error: ${error.message}`, { status: 500 });
      }
    }

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ status: "ok", service: "tangthu-storage-api" });
    }

    const auth = request.headers.get("Authorization");
    if (!env.TANGTHU_API_TOKEN || auth !== `Bearer ${env.TANGTHU_API_TOKEN}`) {
      return json({ error: "Unauthorized" }, 401);
    }
    if (!env.BUCKET) return json({ error: "R2 bucket binding BUCKET is missing" }, 500);

    const path = url.pathname;
    if (path.startsWith("/v1/snapshots/")) {
      return cleanupSnapshotGenerations(request, env, json, path);
    }
    if (!path.startsWith("/v1/objects/")) return json({ error: "Not found" }, 404);

    let key;
    try {
      key = decodeURIComponent(path.slice("/v1/objects/".length));
    } catch {
      return json({ error: "Invalid object key" }, 400);
    }

    const allowed = key.startsWith("snapshots/") ||
      key.startsWith("checkpoints/") || key.startsWith("opds/");
    if (!allowed || key.length > 512 || key.includes("..") ||
        key.startsWith("/") || key.endsWith("/")) {
      return json({ error: "Invalid or disallowed object key" }, 400);
    }

    if (request.method === "GET") {
      const object = await env.BUCKET.get(key);
      if (!object) return json({ error: "Object not found", key }, 404);
      const headers = new Headers(cors);
      object.writeHttpMetadata(headers);
      headers.set("ETag", object.httpEtag);
      headers.set("Cache-Control", "no-store");
      return new Response(object.body, { status: 200, headers });
    }

    if (request.method === "PUT") {
      const contentType = request.headers.get("Content-Type") || "";
      if (!contentType.includes("application/json")) {
        return json({ error: "Content-Type must be application/json" }, 415);
      }
      const body = await request.arrayBuffer();
      if (body.byteLength > MAX_BODY_SIZE) {
        return json({ error: "Object exceeds 25 MB limit" }, 413);
      }
      try { JSON.parse(new TextDecoder().decode(body)); }
      catch { return json({ error: "Invalid JSON" }, 400); }

      const result = await env.BUCKET.put(key, body, {
        httpMetadata: { contentType: "application/json; charset=utf-8" }
      });
      return json({ success: true, key, etag: result.httpEtag });
    }

    if (request.method === "DELETE") {
      await env.BUCKET.delete(key);
      return json({ success: true, deleted: key });
    }

    return json({ error: "Method not allowed" }, 405, {
      Allow: "GET, PUT, DELETE, OPTIONS"
    });
  }
};
