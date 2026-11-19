"use strict";
// Invoked by the Python driver; no accounts or secrets from .env are used.
const assert = require("node:assert/strict");
const readline = require("node:readline");
const {chromium} = require("../.data/browser-tools/node_modules/playwright");
const input = readline.createInterface({input:process.stdin})[Symbol.asyncIterator]();
const receive = async () => JSON.parse((await input.next()).value);
const emit = value => process.stdout.write(JSON.stringify(value)+"\n");
(async () => {
  const config = await receive(), browser = await chromium.launch({headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1365,height:900},serviceWorkers:"block"});
    const external = [], errors = [];
    await context.route("**/*", route => {
      const url = new URL(route.request().url());
      if (url.origin === config.url) return route.continue();
      external.push(url.origin); return route.abort();
    });
    const page = await context.newPage();
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(config.url);
    await page.locator("#registration details summary").click();
    await page.locator("#login-name").fill("WorldLocalTest");
    await page.locator("#login-password").fill(config.password);
    await page.locator('#restore-form button[type="submit"]').click();
    await page.locator("#character-list button").first().click();
    await page.waitForFunction(() => Boolean(session?.tutorial?.living_world));
    await page.evaluate(() => showView("map",{toggle:false}));
    const market = page.locator("#world-life-market button").first();
    await market.waitFor({state:"visible"});
    assert(await market.isEnabled(), "Caravan should be reachable at its physical anchor");
    const before = await page.evaluate(() => ({stock:session.tutorial.living_world.merchant.stock[0].quantity,gold:session.tutorial.players.find(p=>p.id===session.me).gold}));
    await market.click();
    await page.waitForFunction(stock => session.tutorial.living_world.merchant.stock[0].quantity === stock - 1, before.stock);
    assert(await page.evaluate(gold => session.tutorial.players.find(p=>p.id===session.me).gold < gold,before.gold));
    if (!await page.locator('.world-life-actor').count()) emit({diagnostic:await page.evaluate(()=>({field:session.tutorial.field_map,map:session.tutorial.battle?.map.id,nearby:session.tutorial.living_world.nearby,svg:document.querySelector('#world-map svg')?.getAttribute('viewBox')})),errors});
    assert(await page.locator('.world-life-actor').count() > 0, "Nearby NPC markers should render");
    emit({check:"Login, character, shared stock purchase, gold and NPC markers",result:"passed"});
    emit({advance:7200}); await receive();
    await page.evaluate(() => refresh(true));
    await page.waitForFunction(town => session.tutorial.living_world.towns.find(t=>t.id===town).status === "warning", config.town);
    const defend = page.locator(`[data-town="${config.town}"] [data-kind="defend"]`);
    await defend.click();
    await page.waitForFunction(town => session.tutorial.living_world.towns.find(t=>t.id===town).raid.support === 5,config.town);
    emit({advance:7500}); await receive();
    await page.evaluate(() => refresh(true));
    await page.waitForFunction(town => session.tutorial.living_world.towns.find(t=>t.id===town).status === "siege",config.town);
    emit({advance:7680}); await receive();
    await page.evaluate(() => refresh(true));
    await page.waitForFunction(town => !session.tutorial.living_world.towns.find(t=>t.id===town).raid,config.town);
    await page.screenshot({path:".data/living-world-local.png",fullPage:true});
    assert.deepEqual(errors, [], "Browser JavaScript errors");
    assert.deepEqual(external, [], "Unexpected external requests");
    emit({check:"Warning, player defense contribution, siege and resolution; no external requests or JS errors",result:"passed"});
    await context.close();
  } finally { await browser.close(); }
})().then(()=>process.exit(0),error=>{process.stderr.write(error.stack+"\n");process.exit(1);});
