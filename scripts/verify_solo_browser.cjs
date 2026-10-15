"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");
const {spawn} = require("node:child_process");
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
