const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../jeuxRPG/multiplayer/web/app_battle.js"), "utf8");
const start = source.indexOf("function requestTravel(");
const end = source.indexOf("\nfunction selectEntity", start);
assert(start >= 0 && end > start);

const calls = [];
const context = {
  session: {
    me: "p0",
    tutorial: {
      field_map: "rosee",
      players: [{id: "p0"}],
      battle: {
        hostiles_alive: false,
        map: {sites: [{id: "forge", position: [44, 12]}]}
      }
    }
  },
  moveControlled: (adventure, me, destination) => calls.push(["moveControlled", me.id, destination]),
  tutorialCommand: (action, params) => calls.push([action, params]),
  message: text => calls.push(["message", text])
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);

context.requestTravel("forge");
assert.equal(JSON.stringify(calls.shift()), JSON.stringify(["moveControlled", "p0", [44, 12]]));

context.session.tutorial.battle.hostiles_alive = true;
context.requestTravel("training");
assert.match(calls.shift()[1], /Terminez le combat/);

context.session.tutorial.battle = null;
context.session.tutorial.field_map = null;
context.requestTravel("rosee");
assert.equal(JSON.stringify(calls.shift()), JSON.stringify(["move", {destination: "rosee"}]));

const maps = JSON.parse(fs.readFileSync(path.join(__dirname, "../jeuxRPG/maps/world.json"), "utf8"));
const forge = maps.rosee.sites.find(site => site.id === "forge");
assert.equal(forge.name, "Garrik · maître forgeron");
assert.match(forge.dialogue, /forge de Rosée/);

const html = fs.readFileSync(path.join(__dirname, "../jeuxRPG/multiplayer/web/index.html"), "utf8");
assert.match(html, /id="npc-title"/);

console.log("Carte détaillée : déplacement vers les sites et dialogue du forgeron vérifiés.");
