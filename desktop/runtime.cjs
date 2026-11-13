"use strict";
const {readFile} = require("node:fs/promises");
const path = require("node:path");
const APP_ORIGIN = "rpg://client";
const TYPES = {".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json", ".map": "application/json", ".wasm": "application/wasm", ".zip": "application/zip"};
const VENDOR = ["pyodide.mjs", "pyodide.mjs.map", "pyodide.asm.mjs", "pyodide.asm.wasm", "pyodide-lock.json", "python_stdlib.zip"];
const FORWARDED = ["authorization", "content-type", "accept", "x-rpg-chat-connection", "x-rpg-command-ack", "x-rpg-bundles", "x-rpg-bundle-hashes"];
function response(status, body, headers = {}) {
  return new Response(body, {status, headers: {"Content-Type": "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", ...headers}});
}
function createHandler({root, manifest, fetchOnline}) {
  const assets = new Set([...Object.keys(manifest.web_assets), "solo-engine.zip", ...VENDOR.map(name => "vendor/pyodide/" + name)]);
  const server = new URL(manifest.server);
  if (server.protocol !== "https:" || server.origin !== manifest.server) throw new Error("Origine du serveur invalide.");
  return async request => {
    try {
      const url = new URL(request.url);
      if (url.protocol !== "rpg:" || url.host !== "client" || url.username || url.password) return response(403, "{}");
      if (!["GET", "HEAD", "POST"].includes(request.method)) return response(405, "{}");
      if (url.pathname === "/api/classes" && request.method === "GET") {
        return response(200, await readFile(path.join(root, "classes.json")));
      }
      if (url.pathname.startsWith("/api/")) {
        const origin = request.headers.get("origin");
        if (origin && origin !== APP_ORIGIN) return response(403, "{}");
        if (!["GET", "POST"].includes(request.method)) return response(405, "{}");
        const headers = new Headers({Origin: server.origin});
        for (const key of FORWARDED) {
          const value = request.headers.get(key);
          if (value) headers.set(key, value);
        }
        const body = request.method === "POST" ? await request.arrayBuffer() : undefined;
        if (body && body.byteLength > 4096) return response(413, "{}");
        const result = await fetchOnline(server.origin + url.pathname + url.search, {
          method: request.method, headers, body, redirect: "error", credentials: "omit", signal: AbortSignal.timeout(30000),
        });
        const returned = new Headers({"Content-Type": "application/json", "Cache-Control": "no-store"});
        for (const key of ["retry-after", "server-timing", "x-rpg-save-pending", "x-rpg-runtime"]) {
          if (result.headers.has(key)) returned.set(key, result.headers.get(key));
        }
        return new Response(result.body, {status: result.status, headers: returned});
      }
      if (request.method === "POST") return response(405, "{}");
      const name = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
      if (!assets.has(name)) return response(404, "{}");
      const mime = TYPES[path.extname(name)] || "application/octet-stream";
      return response(200, request.method === "HEAD" ? null : await readFile(path.join(root, name)), {
        "Content-Type": mime + (/^(text\/|application\/json)/.test(mime) ? "; charset=utf-8" : ""),
        "Content-Security-Policy": name === "solo_worker.js" ? manifest.worker_csp : manifest.csp,
      });
    } catch {
      return response(503, JSON.stringify({error: "unavailable", message: "Serveur en ligne inaccessible. Le mode solo reste disponible sur cet appareil."}));
    }
  };
}
module.exports = {APP_ORIGIN, createHandler};
