"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),{chromium}=require("../.data/browser-tools/node_modules/playwright");
(async()=>{
 const config=JSON.parse(fs.readFileSync(0,"utf8")),browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:940}}),errors=[];
  await context.route("**/*",route=>new URL(route.request().url()).origin===config.url?route.continue():route.abort());
  await context.addInitScript(token=>sessionStorage.setItem("rpg-token",token),config.token);
  const page=await context.newPage();page.on("pageerror",error=>errors.push(error.message));
  const ready=async()=>{await page.waitForFunction(()=>typeof session!=="undefined"&&session?.tutorial&&globalThis.RPGKeybindings);await page.evaluate(()=>{refresh=async()=>{};scheduleRefresh=()=>{};globalThis.keyboardCalls=[];command=async(action,params)=>{keyboardCalls.push({action,params});};});};
  const show=async id=>{
   await page.evaluate(adventure=>{session={...session,tutorial:adventure};RPGMotion.rebase();fieldCamera={x:adventure.battle.players[session.me].position[0],y:adventure.battle.players[session.me].position[1],span:22,follow:true};focusedMob="";combatTarget="";renderGame(adventure);},config.snapshots[id]);
   await page.locator(".rpg-canvas3d").focus();
  };
  await page.goto(config.url);await ready();await show("cave_1");
  const nearest=await page.evaluate(()=>{const a=session.tutorial,position=a.battle.players[session.me].position;return a.mobs.filter(m=>m.stats.hp.current>0&&m.hostile!==false).sort((x,y)=>Math.hypot(x.position[0]-position[0],x.position[1]-position[1])-Math.hypot(y.position[0]-position[0],y.position[1]-position[1])||x.combat_id.localeCompare(y.combat_id))[0].combat_id;});
  await page.keyboard.press("Tab");assert.equal(await page.evaluate(()=>focusedMob),nearest);
  await page.keyboard.press("Tab");assert.notEqual(await page.evaluate(()=>focusedMob),nearest);
  await page.keyboard.press("Shift+Tab");assert.equal(await page.evaluate(()=>focusedMob),nearest);
  await page.keyboard.press("Space");assert.equal(await page.evaluate(()=>keyboardCalls.filter(c=>c.action==="strike").length),1);
  assert.equal(await page.evaluate(()=>keyboardCalls.find(c=>c.action==="strike").params.target),nearest);
  await page.keyboard.press("i");await page.locator("#inventory-view").waitFor({state:"visible"});
  await page.keyboard.press("i");assert.equal(await page.evaluate(()=>document.body.classList.contains("hud-menu-open")),false);
  await page.keyboard.press("h");await page.locator("#keybindings").waitFor({state:"visible"});
  await page.locator('[data-binding="attack"]').click();await page.keyboard.press("v");assert.equal(await page.locator('[data-binding="attack"]').textContent(),"V");
  await page.screenshot({path:path.resolve(".data/keybindings-desktop.png")});
  await page.keyboard.press("Escape");await page.locator(".rpg-canvas3d").focus();
  await page.keyboard.press("Space");assert.equal(await page.evaluate(()=>keyboardCalls.filter(c=>c.action==="strike").length),1);
  await page.keyboard.press("v");assert.equal(await page.evaluate(()=>keyboardCalls.filter(c=>c.action==="strike").length),2);
  assert((await page.locator(".scene3d-help").textContent()).includes("V : attaque"));
  await page.reload();await ready();assert.equal(await page.evaluate(()=>RPGKeybindings.label("attack")),"V");
  await show("rosee");assert(config.snapshots.rosee.field_interactions.some(s=>s.id==="mira"));
  await page.keyboard.press("f");assert.equal(await page.evaluate(()=>keyboardCalls.find(c=>c.action==="talk")?.params.npc),"mira");
  await page.keyboard.press("t");await page.locator("#chat-message").fill("bonjour ");await page.keyboard.type("i v f");
  assert.equal(await page.locator("#chat-message").inputValue(),"bonjour i v f");assert.equal(await page.evaluate(()=>keyboardCalls.filter(c=>c.action==="talk").length),1);
  await page.locator("#chat-message").blur();await page.keyboard.press("h");
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.resolve(".data/keybindings-mobile.png")});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,checks:["target order and Shift+Tab", "Space sends one strike for selected target", "inventory toggle", "custom binding and browser reload", "F uses real NPC proximity", "typing does not trigger actions", "desktop and mobile settings", "no browser errors"]}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
