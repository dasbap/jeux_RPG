"use strict";
const path = require("node:path");
const {spawnSync} = require("node:child_process");
const root = path.resolve(__dirname, "..");
function run(command, args) {
  const env = {...process.env};
  delete env.ELECTRON_RUN_AS_NODE;
  const result = spawnSync(command, args, {cwd: root, stdio: "inherit", env});
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
if (!process.argv.includes("--skip-prepare")) run(process.env.PYTHON || "python", ["-S", "scripts/prepare_desktop_client.py"]);
if (process.argv.includes("--start")) {
  run(require("electron"), [__dirname]);
} else if (!process.argv.includes("--prepare-only")) {
  const linux = process.argv.includes("--linux");
  if (!linux && process.platform !== "win32") throw new Error("Construire le .exe depuis Windows ; utiliser --linux pour Linux.");
  run(process.execPath, [require.resolve("electron-builder/cli.js"), "--projectDir", __dirname, linux?"--linux":"--win", "--x64", "--publish", "never", ...(linux?["--config.directories.output",path.join(root,"dist/linux")]:[])]);
}
