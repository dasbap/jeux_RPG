"use strict";
const fs = require("node:fs");
const path = require("node:path");

const files = [
  "app_core.js",
  "app_world.js",
  "app_skills.js",
  "app_tutorial.js",
  "app_battle.js",
  "app_camera.js",
  "app_social.js",
  "app.js",
  "app_bootstrap.js",
  "app_session.js",
];

function clientSource(root = path.join(__dirname, "..", "jeuxRPG", "multiplayer", "web")) {
  return files.map(file => fs.readFileSync(path.join(root, file), "utf8")).join("\n");
}

clientSource.files = files;
module.exports = clientSource;
