"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

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
  let authenticatedSocket = false;
  const context = async (mobile = false) => {
    const value = await browser.newContext({viewport: mobile ? {width: 390, height: 844} : {width: 1440, height: 900}, isMobile: mobile, hasTouch: mobile});
    // Short-lived protection credentials go only to the verified deployment.
    const response = await value.request.get(base, {headers: {...auth, "x-vercel-set-bypass-cookie": "true"}, maxRedirects: 0});
    assert.equal(response.status(), 200, "Accès preview refusé : vérifier les Trusted Sources Vercel");
    await value.route("**/*", async route => {
      if (new URL(route.request().url()).origin === base && Object.keys(auth).length) {
        const response = await route.fetch({headers: {...route.request().headers(), ...auth}, maxRedirects: 0});
        return route.fulfill({response});
      }
      return route.continue();
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
    await page.fill("#account-name", credentials.username);
    await page.fill("#account-password", credentials.password);
    await page.fill("#name", "Recette Vercel");
    await page.selectOption("#class-name", "Knight");
    await page.click("#register-form button[type=submit]");
    await page.locator("#tutorial").waitFor({state: "visible", timeout: 60000});
    await page.click("#tutorial"); await adventure(page); await saved(page);
    const sessionId = await page.evaluate(() => session.id);
    await page.screenshot({path: path.join(output, "online.png")});
    await current.close();

    current = await context(); page = await current.newPage(); await page.goto(base);
    await page.click("#registration details summary");
    await page.fill("#login-name", credentials.username); await page.fill("#login-password", credentials.password);
    await page.click("#restore-form button[type=submit]");
    await page.locator("#character-list button").first().waitFor({state: "visible", timeout: 60000});
    await page.locator("#character-list button").first().click(); await adventure(page);
    assert.equal(await page.evaluate(() => session.id), sessionId); await saved(page);
    assert(authenticatedSocket, "Le WebSocket doit s'authentifier sur Vercel");
    await current.close();

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
    await current.close();
    assert.deepEqual(errors, []); assert.deepEqual(failures, []);
    const report = {release, base, signup: true, online: true, passwordResume: true, websocket: true, soloResume: true, landscape: true, pageErrors: errors.length, serverErrors: failures.length};
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally { await browser.close(); }
}

module.exports = {verifiedOrigin};
if (require.main === module) verify().catch(error => {console.error(error.message); process.exitCode = 1;});
