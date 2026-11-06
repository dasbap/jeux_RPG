"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");
const {spawn, execFileSync} = require("node:child_process");
const {chromium} = require("../.ui-test/node_modules/playwright");
(async () => {
  const listener = net.createServer();
  await new Promise(resolve => listener.listen(0, "127.0.0.1", resolve));
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const server = spawn(process.env.PYTHON || "python", ["-c", `import uvicorn; from jeuxRPG.multiplayer.realtime import create_app; uvicorn.run(create_app({'VERCEL_URL': '127.0.0.1:${port}'}), host='127.0.0.1', port=${port}, log_level='error')`], {stdio: ["ignore", "ignore", "pipe"]});
  let serverError = "";
  server.stderr.on("data", data => {serverError += data;});
  let browser;
  try {
    const base = `http://127.0.0.1:${port}`;
    for (let attempt = 0; attempt < 100; attempt++) {
      try { if ((await fetch(base + "/health")).ok) break; } catch {}
      if (server.exitCode !== null) throw new Error(serverError);
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    browser = await chromium.launch({headless: true});
    const context = await browser.newContext();
    await context.route("https://cdn.jsdelivr.net/pyodide/v314.0.7/full/**", async route => {
      const name = path.basename(new URL(route.request().url()).pathname);
      const file = path.join(__dirname, "../.solo-test/node_modules/pyodide", name);
      const contentType = name.endsWith(".wasm") ? "application/wasm" : name.endsWith(".zip") ? "application/zip" : name.endsWith(".json") ? "application/json" : "text/javascript";
      await route.fulfill({status: 200, body: fs.readFileSync(file), contentType, headers: {"Access-Control-Allow-Origin": "*"}});
    });
    let apiCalls = 0;
    await context.route("**/api/**", route => {
      apiCalls++;
      if (new URL(route.request().url()).pathname === "/api/classes") return route.continue();
      return route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({error: "unavailable", message: "Quota Redis épuisé"})});
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    page.on("console", message => {
      if (message.type() === "error" && /Content Security Policy|Traceback|Stat value must be an integer/.test(message.text())) errors.push(message.text());
    });
    const home = await page.goto(base);
    assert.equal(home.status(), 200);
    await page.locator("#solo-entry").click();
    await page.locator("#characters:not([hidden])").waitFor({timeout: 60000});
    const before = apiCalls;
    await page.locator("#new-character-name").fill("Navigateur");
    await page.locator("#new-character-class").selectOption("Knight");
    await page.locator("#character-create button").click();
    await page.locator("#tutorial").click();
    await page.waitForFunction(() => Boolean(session?.tutorial), null, {timeout: 30000});
    const sessionId = await page.evaluate(() => session.id);
    await page.evaluate(() => soloTransport.flush());
    assert.equal(apiCalls, before);
    // Resume a progressed save: the packaged boss has decimal stat bases.
    const saved = await page.evaluate(async () => {
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open("jeux-rpg-solo", 1);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      try {
        return await new Promise((resolve, reject) => {
          const tx = db.transaction("saves", "readonly");
          const request = tx.objectStore("saves").get("game");
          tx.oncomplete = () => resolve(Array.from(request.result));
          tx.onerror = () => reject(tx.error);
        });
      } finally { db.close(); }
    });
    const progressed = execFileSync(process.env.PYTHON || "python", ["-c", [
      "import json, sqlite3, sys",
      "db = sqlite3.connect(':memory:')",
      "db.deserialize(sys.stdin.buffer.read())",
      "row = db.execute('SELECT session_id, data FROM tutorials').fetchone()",
      "party = json.loads(row[1])",
      "party['seen_mobs'] = ['goblin', 'gobelin_boss']",
      "db.execute('UPDATE tutorials SET data=? WHERE session_id=?', (json.dumps(party), row[0]))",
      "db.commit()",
      "sys.stdout.buffer.write(db.serialize())",
      "db.close()"
    ].join("\n")], {input: Buffer.from(saved)});
    // Close the worker before replacing the fixture so autosave cannot overwrite it.
    await page.evaluate(() => soloTransport.close());
    await page.evaluate(async bytes => {
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open("jeux-rpg-solo", 1);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      try {
        await new Promise((resolve, reject) => {
          const tx = db.transaction("saves", "readwrite");
          tx.objectStore("saves").put(new Uint8Array(bytes), "game");
          tx.oncomplete = resolve;
          tx.onerror = () => reject(tx.error);
        });
      } finally { db.close(); }
    }, Array.from(progressed));
    await page.reload();
    await page.waitForFunction(expected => session?.id === expected && session.tutorial?.world?.bestiary.some(mob => mob.id === "gobelin_boss"), sessionId, {timeout: 60000});
    const other = await context.newPage();
    await other.goto(base);

    await other.waitForFunction(() => document.getElementById("message").textContent.includes("autre onglet"));
    await other.close();
    await page.reload();
    await page.waitForFunction(expected => session?.id === expected, sessionId, {timeout: 60000});
    assert.equal(await page.evaluate(() => gameMode), "solo");
    assert.equal(await page.locator("#registration").isVisible(), false);
    await page.locator("#game-menu-toggle").click();
    await page.locator("#show-options").click();
    await page.locator("#choose-character-options").click();
    await page.locator("#mode-online").click();
    await page.locator("#registration:not([hidden])").waitFor();
    assert.deepEqual(errors, []);
    console.log("Navigateur : solo avec API 503, CSP WebAssembly, tutoriel, sauvegarde après rechargement, verrou entre onglets et retour en ligne vérifiés.");
  } finally { if (browser) await browser.close(); server.kill(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
