"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('../.data/browser-tools/node_modules/playwright');
(async()=>{
 const config=JSON.parse(fs.readFileSync(0,'utf8')),browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'}),errors=[];
  await context.route('**/*',r=>new URL(r.request().url()).origin===config.url?r.continue():r.abort());
  await context.addInitScript(token=>sessionStorage.setItem('rpg-token',token),config.token);
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(config.url);await page.waitForFunction(()=>session?.tutorial?.battle?.corpses?.length===2);
  await page.evaluate(()=>{document.body.classList.remove('hud-menu-open');toggleGameMenu(false);});
  await page.locator('.rpg-canvas3d').focus();
  await page.keyboard.press('x');await page.waitForFunction(()=>focusedMob==='harvest-near');
  await page.keyboard.press('g');await page.waitForFunction(()=>session.tutorial.battle.corpses.find(c=>c.id==='harvest-near').harvested.length===1);
  await page.keyboard.press('x');await page.waitForFunction(()=>focusedMob==='harvest-far');
  await page.screenshot({path:path.resolve('.data/harvest-target.png')});
  await page.keyboard.press('g');
  await page.waitForFunction(()=>{const a=session.tutorial,p=a.battle.players[session.me].position,c=a.battle.corpses.find(c=>c.id==='harvest-far');return Math.hypot(p[0]-c.position[0],p[1]-c.position[1])<=a.battle.corpse_interact_range&&!busy&&a.players.find(p=>p.id===session.me).cooldown_real_seconds<=0;});
  await page.keyboard.press('g');await page.waitForFunction(()=>session.tutorial.battle.corpses.every(c=>c.harvested.length));
  await page.keyboard.press('g');
  assert.equal(await page.evaluate(()=>session.tutorial.players.find(p=>p.id===session.me).inventory.peau),5);
  await page.reload();await page.waitForFunction(()=>session?.tutorial?.players?.find(p=>p.id===session.me)?.inventory?.peau===5);
  await page.evaluate(()=>showView('options',{toggle:false}));
  assert.equal(await page.locator('[data-binding="harvest"]').textContent(),'G');assert.equal(await page.locator('[data-binding="harvest_target"]').textContent(),'X');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,checks:['X corpse selection','G nearby harvest','approach distant corpse','ignore already harvested','no duplicate loot','inventory survives reload','rebindable options']}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
