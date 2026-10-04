const fs = require("node:fs");
const assert = require("node:assert/strict");
const {JSDOM, VirtualConsole} = require("jsdom");
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", error => errors.push(error.message));
const dom = new JSDOM(fs.readFileSync(process.argv[2], "utf8"), {runScripts:"dangerously", virtualConsole});
const document = dom.window.document;
const payload = JSON.parse(document.getElementById("snapshot").textContent);
const map = payload.maps[payload.selected];
assert(document.querySelector("svg"));
assert.equal(document.querySelectorAll("[data-cell]").length, map.width*map.height);
assert(document.querySelectorAll(".terrain-decoration").length);
for (const item of map.bridge_rotations || []) {
  const cell = document.querySelector(`[data-cell="${item.position.join(",")}"]`);
  assert.equal(cell.dataset.rotation, String(item.rotation));
  assert(cell.style.fill.includes("river-bridge-"+item.rotation));
}
const initial = document.querySelector("svg").getAttribute("viewBox");
document.getElementById("more").click();
assert.notEqual(document.querySelector("svg").getAttribute("viewBox"),initial);
document.getElementById("reset").click();
assert.equal(document.querySelector("svg").getAttribute("viewBox"),initial);
document.getElementById("markers").click();
assert.equal(document.querySelectorAll(".battle-unit").length,0);
assert.equal(errors.length,0,errors.join("\n"));
if (process.argv[3]) fs.writeFileSync(process.argv[3], document.querySelector("svg").outerHTML.replace("<svg ",'<svg xmlns="http://www.w3.org/2000/svg" ').replace(">", "><style>"+document.querySelector("style").textContent+"</style>"));
dom.window.close();
process.stdout.write("Aperçu vérifié : rendu partagé, rotations, zoom et repères.\n");
