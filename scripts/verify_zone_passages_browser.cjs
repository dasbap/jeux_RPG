"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('../.data/browser-tools/node_modules/playwright');
(async()=>{
 const config=JSON.parse(fs.readFileSync(0,'utf8')),browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
  await context.route('**/*',r=>new URL(r.request().url()).origin===config.url?r.continue():r.abort());
  await context.addInitScript(token=>sessionStorage.setItem('rpg-token',token),config.token);
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(config.url);await page.waitForFunction(()=>session?.tutorial?.field_map==='lisiere');
  assert.equal(await page.locator('#hud-minimap .mini-zone-exit').count(),3);
  assert.equal(await page.locator('#hud-minimap .mini-exit:not(.mini-zone-exit)').count(),1);
  await page.evaluate(()=>showView('map',{toggle:false}));
  const point=page.locator('[data-map="detail:zone_lisiere"] [data-zone-passage="lisiere:2"]');await point.waitFor();
  assert((await point.getAttribute('aria-label')).includes('Grotte'));
  assert.equal(await page.locator('[data-map="detail:zone_lisiere"] .zone-passage').count(),3);
  await point.scrollIntoViewIfNeeded();
  await page.screenshot({path:path.resolve('.data/lisiere-detail-passages.png')});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.setViewportSize({width:1440,height:1000});
  await point.click();
  await page.waitForFunction(()=>session?.tutorial?.field_map==='cave_1',null,{timeout:20000});
  assert(!(await page.evaluate(()=>document.body.classList.contains('hud-menu-open'))));
  assert(!(await page.locator('#journey-view').isVisible()));
  await page.reload();await page.waitForFunction(()=>session?.tutorial?.field_map==='cave_1');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,checks:['Lisiere three red zone passages','ordinary exit stays yellow','detailed map destinations','mobile no overflow','click walks to exit','cave first room not boss','no automatic atlas','arrival saved']}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
