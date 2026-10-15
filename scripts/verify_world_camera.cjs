"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {JSDOM} = require(require.resolve("jsdom", {paths:[path.join(__dirname,"../.ui-test")]}));
const dom = new JSDOM('<div id="world-map"></div><div id="region-map"></div><div id="field-zoom-in"></div><div id="field-zoom-out"></div><div id="field-center"></div>', {runScripts:"outside-only"});
const w = dom.window;
w.eval(`const $ = id => document.getElementById(id); let session = {tutorial:{battle:null}}; const worldCameras = new Map(); let activeWorldMap = "general"; let fieldCamera = null; function renderGame() {}\n` + fs.readFileSync(path.join(__dirname,"../jeuxRPG/multiplayer/web/app_camera.js"),"utf8") + '\n' + fs.readFileSync(path.join(__dirname,"../jeuxRPG/multiplayer/web/app_world.js"),"utf8") + '; window.mount = mountWorldMap; window.adjust = adjustFieldCamera; window.combat = () => {session.tutorial.battle = {}; fieldCamera = {span:12};}; window.span = () => fieldCamera.span;');
const primary = w.document.getElementById("world-map"), panel = w.document.getElementById("region-map");
function fresh(key) {
  const node = w.document.createElementNS("http://www.w3.org/2000/svg","svg");
  node.dataset.map = key;
  node.setAttribute("viewBox","0 0 690 245");
  const point = w.document.createElementNS(node.namespaceURI,"g");
  point.dataset.point = "mira";
  point.onclick = () => {w.mount(fresh(key), primary); w.mount(fresh(key), panel);};
  node.append(point);
  return node;
}
const general = w.mount(fresh("general"), primary);
const background = w.mount(fresh("detail:rosee"), primary);
const detail = w.mount(fresh("detail:rosee"), panel);
const box = node => node.getAttribute("viewBox");
function wheel(node, deltaY) {node.dispatchEvent(new w.WheelEvent("wheel",{deltaY,bubbles:true,cancelable:true}));}
const initial = box(detail);
wheel(detail, -100);
assert.notEqual(box(detail), initial, "La carte visée doit zoomer immédiatement");
assert.equal(box(detail), box(background), "Les deux vues doivent rester synchronisées");
assert.equal(box(general), initial, "La carte générale doit garder son cadrage");
const zoomed = box(detail);
for (let index=0; index<5; index++) {
  detail.querySelector('[data-point="mira"]').dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
  assert.equal(box(detail), zoomed, "Cliquer sur un point ne doit pas modifier le zoom");
  assert.equal(box(background), zoomed);
}
w.adjust("out");
assert.equal(box(detail), box(background));
assert.notEqual(box(detail), zoomed);
wheel(background, -100);
assert.equal(box(detail), box(background));
w.combat();
const beforeCombatWheel = box(detail);
wheel(detail, -100);
assert.notEqual(box(detail), beforeCombatWheel, "Une carte régionale reste contrôlable pendant un combat");
assert.equal(w.span(), 12, "Le zoom régional ne doit pas modifier la caméra du combat");
dom.window.close();
console.log("Caméra : zoom immédiat sur la carte visée, vues synchronisées, clics sans saut et caméra de combat indépendante vérifiés.");
