"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {spawnSync} = require("node:child_process");
const {JSDOM} = require(require.resolve("jsdom", {paths: [path.join(__dirname, "..", ".ui-test")]}));
const root = path.join(__dirname, "..");
const fixture = spawnSync(process.env.PYTHON || "python", ["-c", `
import json
from jeuxRPG.multiplayer import fields, tutorial
p = tutorial.new_party([{'id':'p', 'name':'Test', 'class_name':'Knight'}])
fields.start(p, 0)
fields.transition(p, fields.MAPS['clearing']['exits'][0], 'p', 1)
def snapshot(revision):
    v = tutorial.view(p, 'p', revision)
    return {'id':'room', 'me':'p', 'state':'running', 'revision':revision, 'players':v['players'], 'events':[], 'tutorial':v}
before = snapshot(2)
fields.transition(p, fields.MAPS['forest']['exits'][0], 'p', 3)
after = snapshot(4)
print(json.dumps({'before':before, 'after':after}))
`], {cwd:root, encoding:"utf8", env:{...process.env, RPG_MAPS_FILE:path.join(root,"jeuxRPG/maps")}});
assert.equal(fixture.status, 0, fixture.stderr);
const states = JSON.parse(fixture.stdout);
const dom = new JSDOM(fs.readFileSync(path.join(root,"jeuxRPG/multiplayer/web/index.html"),"utf8"), {url:"https://rpg.test/",runScripts:"outside-only"});
const w = dom.window;
w.structuredClone = structuredClone;
w.fetch = async () => ({ok:true,json:async()=>[]});
w.setTimeout = () => 1;
w.setInterval = () => 1;
w.eval(fs.readFileSync(path.join(root,"jeuxRPG/multiplayer/web/map_artwork.js"),"utf8"));
w.eval(require("./client_source.cjs")() + '; scheduleRefresh = () => {}; refresh = async () => {}; window.mount = value => {token="local"; session=value; renderGame(value.tutorial);}; window.stubTravel = () => {tutorialCommand = (action, params) => {window.requested = {action, params};};};');
w.mount(states.before);
w.mount(states.after);
assert.equal(w.document.querySelector("#world-map .battle-map"), null);
assert(w.document.querySelector('#world-map [data-destination="zone_rosee"]'));
assert.match(w.document.getElementById("tutorial-actions").textContent, /Rejoindre Village de Rosée/);
w.stubTravel();
[...w.document.querySelectorAll("#tutorial-actions button")].find(button => button.textContent === "Rejoindre Village de Rosée").click();
assert.equal(w.requested.action, "travel");
assert.equal(w.requested.params.destination, "rosee");
const missingPoint = structuredClone(states.after);
missingPoint.tutorial.world.places.forEach(place => {place.points = place.points.filter(point => point.id !== "rosee");});
w.mount(missingPoint);
assert.match(w.document.getElementById("tutorial-actions").textContent, /Sentier de Rosée/);
console.log("Sortie réelle de la forêt : rendu de la carte rapide sans ancien terrain conservé vérifié.");
dom.window.close();
