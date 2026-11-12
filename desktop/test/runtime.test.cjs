"use strict";
const assert = require("node:assert/strict");
const {test} = require("node:test");
const path = require("node:path");
const {createHandler} = require("../runtime.cjs");
const manifest = require("../assets/manifest.json");
const root = path.resolve(__dirname, "../assets");
test("client et catalogue disponibles sans accès réseau, aucun fichier privé servi", async () => {
  const handle = createHandler({root, manifest, fetchOnline: () => {throw new Error("Hors ligne");}});
  const index = await handle(new Request("rpg://client/"));
  assert.equal(index.status, 200);
  assert.match(await index.text(), /rpg-realtime-url/);
  const classes = await handle(new Request("rpg://client/api/classes"));
  assert((await classes.json()).some(item => item.id === "Knight"));
  for (const url of ["rpg://client/.env", "rpg://client/admin.html", "rpg://client/%2e%2e/package.json", "rpg://client/vendor/pyodide/../../main.cjs"]) {
    assert.equal((await handle(new Request(url))).status, 404);
  }
  assert.equal((await handle(new Request("rpg://other/"))).status, 403);
  const offline = await handle(new Request("rpg://client/api/state"));
  assert.equal(offline.status, 503);
  assert.match((await offline.json()).message, /mode solo/);
});
test("seul le serveur prévu reçoit la requête, sans cookies ni redirection", async () => {
  let received;
  const handle = createHandler({root, manifest, fetchOnline: async (url, options) => {
    received = {url, options};
    return new Response('{"ok":true}', {headers: {"Set-Cookie": "private=1", "X-RPG-Save-Pending": "0"}});
  }});
  const result = await handle(new Request("rpg://client/api/commands?compact=1", {
    method: "POST", headers: {Authorization: "Bearer fixture", Cookie: "do-not-forward=1", Origin: "rpg://client", "Content-Type": "application/json"}, body: '{"action":"rest"}',
  }));
  assert.equal(received.url, manifest.server + "/api/commands?compact=1");
  assert.equal(received.options.headers.get("authorization"), "Bearer fixture");
  assert.equal(received.options.headers.get("origin"), manifest.server);
  assert.equal(received.options.headers.get("cookie"), null);
  assert.equal(received.options.redirect, "error");
  assert.equal(result.headers.get("set-cookie"), null);
  assert.equal(result.headers.get("x-rpg-save-pending"), "0");
  assert.equal((await handle(new Request("rpg://client/api/state", {headers: {Origin: "https://other.example"}}))).status, 403);
});
