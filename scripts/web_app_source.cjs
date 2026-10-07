const fs = require("node:fs");
const path = require("node:path");

module.exports = root => [
  "core.js",
  "skills.js",
  "world.js",
  "combat.js",
  "ui.js",
  "camera.js",
  "app.js",
].map(name => fs.readFileSync(path.join(root, "jeuxRPG/multiplayer/web", name), "utf8")).join("\n");
