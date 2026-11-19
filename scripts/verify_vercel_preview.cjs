"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const privateValues = new Set();
function privateValue(value) {
  if (!value || privateValues.has(value)) return;
  privateValues.add(value);
  if (process.env.GITHUB_ACTIONS === "true") process.stdout.write(`::add-mask::${value}\n`);
}
privateValue(process.env.VERCEL_OIDC_TOKEN);
privateValue(process.env.VERCEL_TOKEN);
function safeMessage(error) {
  let value = String(error?.message || error).split("\n")[0];
  for (const secret of privateValues) value = value.split(secret).join("[redacted]");
  return value.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, "[redacted token]")
    .replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
}
function scopedHeaders(headers, url, base, auth) {
  const result = {...headers};
  for (const key of Object.keys(result)) {
    if (key.toLowerCase() === "x-vercel-trusted-oidc-idp-token") delete result[key];
  }
  return new URL(url).origin === base ? {...result, ...auth} : result;
}

function verifiedOrigin(metadata, release) {
  assert.match(release, /^[a-f0-9]{40}$/);
  assert.equal(metadata.projectId, "prj_fVH6vG7RCXf5OP3MIfTngxeCN8U2");
  assert.equal(metadata.ownerId, "team_qde9V6kikwwSvLtNrjAsAkRY");
  assert([null, "preview"].includes(metadata.target), "La recette accepte uniquement Preview");
  assert.equal(metadata.readyState, "READY");
  assert.equal(metadata.meta?.githubCommitSha, release);
  const url = new URL("https://" + metadata.url);
  assert(url.hostname.endsWith("-dasbaps-projects.vercel.app"));
  assert.equal(url.origin, "https://" + metadata.url);
  return url.origin;
}

async function verify() {
  const metadata = JSON.parse(fs.readFileSync(process.env.RPG_PREVIEW_METADATA || ".data/vercel-preview-metadata.json", "utf8"));
  const release = process.env.RPG_RELEASE_SHA;
  const base = verifiedOrigin(metadata, release);
  const {chromium} = require("../.ui-test/node_modules/playwright");
  const browser = await chromium.launch({headless: true, executablePath: process.env.RPG_BROWSER_EXECUTABLE});
  const errors = [], failures = [];
  const output = path.resolve(".data/vercel-preview-report");
  fs.mkdirSync(output, {recursive: true});
  const auth = process.env.VERCEL_OIDC_TOKEN ? {"x-vercel-trusted-oidc-idp-token": process.env.VERCEL_OIDC_TOKEN} : {};
  const credentials = {username: "vc_" + crypto.randomBytes(7).toString("hex"), password: crypto.randomBytes(24).toString("hex")};
  privateValue(credentials.password);
  let authenticatedSocket = false;
  const closing = new WeakSet();
  const closeContext = async value => {
    closing.add(value);
    await value.unrouteAll({behavior: "ignoreErrors"});
    await value.close();
  };
  const context = async (mobile = false) => {
    const value = await browser.newContext({viewport: mobile ? {width: 390, height: 844} : {width: 1440, height: 900}, isMobile: mobile, hasTouch: mobile, serviceWorkers: "block", extraHTTPHeaders: auth});
    // Chromium also needs the temporary header on the WebSocket handshake.
    // Block foreign sockets and remove it from all foreign HTTP requests.
    await value.routeWebSocket(url => url.origin !== base.replace(/^http/, "ws"), socket => socket.close({code: 1008, reason: "Outside verified preview"}));
    // Short-lived protection credentials go only to the verified deployment.
    const response = await value.request.get(base, {headers: {...auth, "x-vercel-set-bypass-cookie": "true"}, maxRedirects: 0});
    assert.equal(response.status(), 200, "Accès preview refusé : vérifier les Trusted Sources Vercel");
    await value.route("**/*", async route => {
      try {
        if (new URL(route.request().url()).origin === base && Object.keys(auth).length) {
          const headers = scopedHeaders(route.request().headers(), route.request().url(), base, auth);
          privateValue(headers.authorization?.replace(/^Bearer /i, ""));
          const response = await route.fetch({headers, maxRedirects: 0});
          const location = response.headers().location;
          if (location && new URL(location, base).origin !== base) {
            failures.push("Redirect outside verified preview");
            await route.abort();
            return;
          }
          await route.fulfill({response});
          return;
        }
        await route.continue({headers: scopedHeaders(route.request().headers(), route.request().url(), base, auth)});
      } catch (error) {
        if (!closing.has(value)) failures.push("Navigation: " + error.name);
        await route.abort().catch(() => {});
      }
    });
    value.on("page", page => {
      page.on("pageerror", error => errors.push(error.name + ": " + error.message));
      page.on("response", response => {
        if (new URL(response.url()).origin === base && response.status() >= 500) failures.push(new URL(response.url()).pathname + ":" + response.status());
      });
      page.on("websocket", socket => socket.on("framereceived", frame => {
        try { if (JSON.parse(String(frame.payload)).type === "authenticated") authenticatedSocket = true; } catch {}
      }));
    });
    return value;
  };
  const adventure = page => page.waitForFunction(() => typeof session !== "undefined" && Boolean(session?.tutorial), null, {timeout: 60000});
  const saved = async page => {
    await page.waitForFunction(async () => {
      const result = await fetch("/api/state", {headers: {Authorization: "Bearer " + sessionStorage.getItem("rpg-token")}});
      return result.ok && result.headers.get("X-RPG-Save-Pending") === "0";
    }, null, {timeout: 60000, polling: 1000});
  };
  try {
    let current = await context(), page = await current.newPage();
    await page.goto(base);
    const health = await page.evaluate(() => fetch("/health").then(result => result.json()));
    assert.equal(health.release, release); assert.equal(health.database_backend, "d1");
    assert.equal(health.runtime, "d1-transaction", "La preview doit utiliser D1 sans Redis");
    await page.fill("#account-name", credentials.username);
    await page.fill("#account-password", credentials.password);
    await page.fill("#name", "Recette Vercel");
    await page.selectOption("#class-name", "Knight");
    await page.click("#register-form button[type=submit]");
    await page.locator("#tutorial").waitFor({state: "visible", timeout: 60000});
    await page.click("#tutorial"); await adventure(page); await saved(page);
    console.log("Vercel : aventure en ligne et sauvegarde confirmees.");
    const sessionId = await page.evaluate(() => session.id);
    await page.screenshot({path: path.join(output, "online.png")});
    await closeContext(current);

    current = await context(); page = await current.newPage(); await page.goto(base);
    await page.click("#registration details summary");
    await page.fill("#login-name", credentials.username); await page.fill("#login-password", credentials.password);
    await page.click("#restore-form button[type=submit]");
    await page.locator("#character-list button").first().waitFor({state: "visible", timeout: 60000});
    await page.locator("#character-list button").first().click(); await adventure(page);
    assert.equal(await page.evaluate(() => session.id), sessionId); await saved(page);
    assert(authenticatedSocket, "Le WebSocket doit s'authentifier sur Vercel");
    console.log("Vercel : connexion par mot de passe, reprise et WebSocket verifies.");
    await closeContext(current);

    current = await context(true); page = await current.newPage(); await page.goto(base);
    await page.locator("#landscape-required").waitFor({state: "visible"});
    await page.keyboard.press("Escape"); assert(await page.locator("#landscape-required").isVisible());
    await page.screenshot({path: path.join(output, "portrait.png")});
    await page.setViewportSize({width: 844, height: 390});
    await page.locator("#landscape-required").waitFor({state: "hidden"});
    await page.click("#solo-entry");
    await page.locator("#characters:not([hidden])").waitFor({timeout: 90000});
    await page.fill("#new-character-name", "Solo Vercel"); await page.selectOption("#new-character-class", "Knight");
    await page.click("#character-create button"); await page.click("#tutorial"); await adventure(page);
    const soloId = await page.evaluate(async () => { await soloTransport.flush(); return session.id; });
    await page.reload(); await adventure(page);
    assert.equal(await page.evaluate(() => session.id), soloId);
    await page.screenshot({path: path.join(output, "solo-landscape.png")});
    await closeContext(current);
    assert.deepEqual(errors, []); assert.deepEqual(failures, []);
    const report = {release, base, signup: true, online: true, passwordResume: true, websocket: true, soloResume: true, landscape: true, pageErrors: errors.length, serverErrors: failures.length};
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally {
    await Promise.all(browser.contexts().map(closeContext));
    await browser.close();
  }
}

module.exports = {verifiedOrigin, safeMessage, scopedHeaders};
if (require.main === module) verify().catch(error => {console.error(safeMessage(error)); process.exitCode = 1;});
