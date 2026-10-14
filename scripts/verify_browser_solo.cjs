"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {execFileSync} = require("node:child_process");
const {indexedDB} = require("../.solo-test/node_modules/fake-indexeddb");
const {loadPyodide} = require("../.solo-test/node_modules/pyodide/pyodide.js");
const archive = execFileSync(process.env.PYTHON || "python", ["-c", "import sys; from jeuxRPG.multiplayer.browser_solo_assets import engine_archive; sys.stdout.buffer.write(engine_archive())"]);
let requests = 0;
function worker() {
  let nextId = 0;
  const pending = new Map(), timers = [];
  const context = {indexedDB, Uint8Array, Promise, JSON, Date, console,
    importScripts(url) { assert.equal(url, "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.js"); },
    loadPyodide: () => loadPyodide(),
    fetch: async url => { requests++; assert.equal(url, "/solo-engine.zip"); return {ok: true, arrayBuffer: async () => new Uint8Array(archive).buffer}; },
    setInterval: (fn, delay) => timers.push({fn, delay}),
    postMessage(message) {
      const task = pending.get(message.id);
      if (!task) return;
      pending.delete(message.id);
      if (message.error) task.reject(new Error(message.error)); else task.resolve(message.result);
    }
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/solo_worker.js", "utf8"), context);
  return {send(type, payload) { const id = ++nextId; return new Promise((resolve, reject) => { pending.set(id, {resolve, reject}); context.onmessage({data: {id, type, payload}}); }); }};
}
(async () => {
  const first = worker();
  await first.send("init");
  const account = await first.send("request", {path: "/api/account/character", body: {action: "create", name: "Navigateur", class_name: "Knight"}});
  assert.equal(account.status, 200);
  const token = account.body.token;
  const before = requests;
  const tutorial = await first.send("request", {path: "/api/commands", token, body: {request_id: "browser-solo-test", action: "tutorial", params: {field_mode: true}}});
  assert.equal(tutorial.status, 200);
  assert(tutorial.body.session.tutorial);
  await first.send("flush");
  assert.equal(requests, before, "Le jeu solo ne doit effectuer aucun appel serveur");
  const second = worker();
  await second.send("init");
  const restored = await second.send("request", {path: "/api/account/me"});
  assert.equal(restored.body.token, token);
  const state = await second.send("request", {path: "/api/state", token});
  assert.equal(state.body.session.id, tutorial.body.session.id);
  console.log("Solo WebAssembly : création, tutoriel, sauvegarde IndexedDB et restauration vérifiés ; aucun appel API pendant le jeu.");
})().catch(error => {console.error(String(error).slice(-5000)); process.exitCode = 1;});
