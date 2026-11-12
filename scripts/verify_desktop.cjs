"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {_electron} = require("../.ui-test/node_modules/playwright");
const root = path.resolve(__dirname, "..");
const packaged = process.argv.includes("--packaged");
const executablePath = process.env.RPG_DESKTOP_EXECUTABLE || (packaged ? path.join(root, "dist/client/win-unpacked/Jeux-RPG.exe") : require("../desktop/node_modules/electron"));
fs.mkdirSync(path.join(root, ".data"), {recursive: true});
const profile = fs.mkdtempSync(path.join(root, ".data/desktop-verification-"));
const env = {...process.env, RPG_DESKTOP_TEST: "1", RPG_DESKTOP_DATA_DIR: profile};
delete env.ELECTRON_RUN_AS_NODE;
const errors = [];
async function launch() {
  const args = packaged ? [] : [path.join(root, "desktop")];
  if (process.platform === "linux") args.push("--no-sandbox", "--ozone-platform=headless");
  const app = await _electron.launch({executablePath, args, env, timeout: 60000});
  await app.evaluate(({session}) => {
    // Block native requests too, including the main process API bridge.
    session.fromPartition("persist:jeux-rpg").webRequest.onBeforeRequest({urls: ["https://*/*", "http://*/*", "wss://*/*", "ws://*/*"]}, (_details, callback) => callback({cancel: true}));
  });
  const page = await app.firstWindow();
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && /Content Security Policy|Traceback/.test(message.text())) errors.push(message.text()); });
  await page.waitForLoadState("domcontentloaded");
  return {app, page};
}
(async () => {
  let current;
  try {
    current = await launch();
    const page = current.page;
    assert.equal(page.url(), "rpg://client/");
    assert.equal(await page.evaluate(() => typeof require), "undefined");
    assert.equal(await page.evaluate(() => isSecureContext && Boolean(navigator.locks)), true);
    await page.click("#solo-entry");
    await page.locator("#characters:not([hidden])").waitFor({timeout: 60000});
    await page.fill("#new-character-name", "Bureau hors ligne");
    await page.selectOption("#new-character-class", "Knight");
    await page.click("#character-create button");
    await page.click("#tutorial");
    await page.waitForFunction(() => Boolean(session?.tutorial), null, {timeout: 30000});
    const world = await page.evaluate(() => session.tutorial.world);
    assert.equal(world.zone_entries.zone_rosee, "rosee");
    assert(world.graph.clearing.includes("forest"));
    assert(world.graph.forest.includes("rosee"));
    assert(!world.graph.zone_lisiere.includes("forest"));
    const enemyToggle = await page.locator("#mob-list-toggle").boundingBox();
    assert(enemyToggle.x > (await page.evaluate(()=>innerWidth))/2,"Le bouton cheval est à droite dans le client compilé");
    const id = await page.evaluate(() => session.id);
    // Close immediately after starting: the native close hook must flush IndexedDB.
    const closed = current.app.waitForEvent("close");
    await current.app.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows()[0].close());
    await closed;
    current = await launch();
    await current.page.waitForFunction(expected => session?.id === expected, id, {timeout: 60000});
    assert.equal(await current.page.evaluate(() => gameMode), "solo");
    const result = await current.page.evaluate(async () => (await fetch("/api/classes")).json());
    assert(result.some(item => item.id === "Knight"));
    await current.page.screenshot({path: path.join(root, ".data/desktop-offline.png")});
    assert.deepEqual(errors, []);
    console.log(`Client ${packaged ? "compilé" : "source"} : réseau bloqué, tutoriel solo, sauvegarde à la fermeture, reprise après redémarrage et isolation Node vérifiés.`);
  } finally { if (current) await current.app.close().catch(() => {}); }
})().catch(error => {console.error(error); process.exitCode = 1;});
