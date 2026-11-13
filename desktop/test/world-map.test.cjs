"use strict";
const assert = require("node:assert/strict");
const {test} = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
test("les lieux superposés de Rosée deviennent distincts sans déplacer les repères uniques", () => {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, "../../jeuxRPG/multiplayer/web/app_world.js"), "utf8"), context);
  const place = {id: "zone_rosee", points: [
    ...["rosee", "forest", "rosee_prairies", "rosee_verger", "rosee_bois", "rosee_carriere"].map(id => ({id, x: 170, y: 175})),
    {id: "mira", x: 170, y: 110}, {id: "forge", x: 430, y: 55},
    {id: "training", x: 560, y: 55}, {id: "rosee_habitations", x: 300, y: 165},
  ]};
  const positions = context.localMapPositions(place);
  assert.equal(positions.size, place.points.length + 1);
  assert.equal(new Set([...positions.values()].map(point => `${point.x},${point.y}`)).size, positions.size);
  for (const id of ["rosee", "mira", "forge", "training", "rosee_habitations"]) {
    const original = place.points.find(point => point.id === id);
    assert.equal(positions.get(id).x, original.x);
    assert.equal(positions.get(id).y, original.y);
  }
  for (const point of positions.values()) {
    for (const other of positions.values()) {
      if (point !== other) assert(Math.abs(point.x - other.x) >= 80 || Math.abs(point.y - other.y) >= 42);
    }
  }
});
