"use strict";
let python, database, activeToken = "", subscribed = false, dirty = false;
let queue = Promise.resolve();
function transaction(mode, operation) {
  return new Promise((resolve, reject) => {
    const tx = database.transaction("saves", mode);
    const request = operation(tx.objectStore("saves"));
    tx.oncomplete = () => resolve(request.result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}
async function save() {
  if (!dirty) return;
  const proxy = python.runPython("solo.save()");
  let bytes;
  try { bytes = new Uint8Array(proxy.toJs()); } finally { proxy.destroy(); }
  await transaction("readwrite", store => store.put(bytes, "game"));
  dirty = false;
  postMessage({type: "saved", at: Date.now()});
}
async function initialize() {
  database = await new Promise((resolve, reject) => {
    const request = indexedDB.open("jeux-rpg-solo", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("saves");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  const saved = await transaction("readonly", store => store.get("game"));
  importScripts("https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.js");
  python = await loadPyodide({indexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/"});
  const response = await fetch("/solo-engine.zip");
  if (!response.ok) throw new Error("Moteur solo indisponible.");
  python.unpackArchive(await response.arrayBuffer(), "zip", {extractDir: "/engine"});
  if (saved) python.FS.writeFile("/saved-game.sqlite3", new Uint8Array(saved));
  python.runPython("import sys, json\nsys.path.insert(0, '/engine')\nfrom jeuxRPG.multiplayer.browser_solo import SoloGame\nfrom pathlib import Path\nsaved_path = Path('/saved-game.sqlite3')\nsolo = SoloGame(saved_path.read_bytes() if saved_path.exists() else None)");

}
function request(message) {
  python.globals.set("request_json", JSON.stringify(message));
  return JSON.parse(python.runPython("solo.request(json.loads(request_json))"));
}
onmessage = event => {
  queue = queue.then(async () => {
    const {id, type, payload} = event.data;
    try {
      let result;
      if (type === "init") { await initialize(); result = true; }
      else if (type === "flush") { await save(); result = true; }
      else if (type === "subscribe") { subscribed = payload; result = true; }
      else {
        result = request(payload);
        dirty = true;
        if (payload.path === "/api/account/character" && result.status === 200) activeToken = result.body.token;
        if (payload.path === "/api/state") activeToken = payload.token;
        if (payload.path === "/api/account/logout") { activeToken = ""; subscribed = false; }
        if (payload.path.startsWith("/api/account/")) await save();
        if (payload.path === "/api/commands" && result.status === 200) postMessage({type: "state", result: request({path: "/api/state", token: activeToken})});
      }
      postMessage({id, result});
    } catch (error) { postMessage({id, error: String(error.message || error)}); }
  });
};
setInterval(() => {
  if (!python || !subscribed || !activeToken) return;
  queue = queue.then(() => {
    const result = request({path: "/api/state", token: activeToken});
    dirty = true;
    postMessage({type: "state", result});
  }).catch(error => postMessage({type: "error", error: String(error)}));
}, 250);
setInterval(() => { if (python) queue = queue.then(save).catch(error => postMessage({type: "error", error: String(error)})); }, 5000);
