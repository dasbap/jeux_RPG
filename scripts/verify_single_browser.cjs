// Credentials arrive over stdin and are never written to the report.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(path.resolve(process.argv[2]));

(async () => {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  const {origin, password, screenshot} = JSON.parse(input);
  const url = new URL(origin);
  assert.equal(url.hostname, '127.0.0.1');
  const errors = [], failures = [];
  let sockets = 0;
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.on('pageerror', error => errors.push(error.name));
    page.on('websocket', ws => { if (ws.url().endsWith('/api/ws')) sockets++; });
    page.on('response', response => { if (response.url().includes('/api/') && response.status() >= 500) failures.push(response.status()); });
    await page.goto(origin, {waitUntil: 'networkidle', timeout: 60000});
    assert.equal(await page.locator('meta[name="rpg-realtime-url"]').getAttribute('content'), '/api/ws');
    await page.click('#registration details summary');
    await page.fill('#login-name', 'OracleTest00');
    await page.fill('#login-password', password);
    await page.click('#restore-form button[type=submit]');
    await page.locator('#character-list button').first().waitFor({state: 'visible', timeout: 60000});
    await page.locator('#character-list button').first().click();
    await page.waitForFunction(() => typeof session !== 'undefined' && Boolean(session?.tutorial), {}, {timeout: 60000});
    await page.waitForFunction(() => globalThis.rpgRealtime?.connected === true, {}, {timeout: 30000});
    await page.locator('#battle').waitFor({state: 'visible'});
    await page.screenshot({path: screenshot, fullPage: true});
    assert.ok(sockets > 0);
    assert.deepEqual(errors, []);
    assert.deepEqual(failures, []);
    const result = {password_login: true, character_selection: true, game_rendered: true, websocket_connected: true, page_errors: errors.length, server_errors: failures.length};
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
