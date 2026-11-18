"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),{chromium}=require("../.data/browser-tools/node_modules/playwright");
(async()=>{
 const config=JSON.parse(fs.readFileSync(0,"utf8")),browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:"block"});
  await context.route("**/*",route=>new URL(route.request().url()).origin===config.url?route.continue():route.abort());
  await context.addInitScript(token=>sessionStorage.setItem("rpg-token",token),config.token);
  const page=await context.newPage(),errors=[];page.on("pageerror",error=>errors.push(error.message));
  await page.goto(config.url);await page.waitForFunction(()=>Boolean(session?.tutorial?.coaches?.nearby?.length));
  await page.evaluate(()=>toggleGameMenu(false));
  const button=page.locator('[data-coach-route="rosee_lisiere"]');await button.waitFor();
  await page.screenshot({path:path.resolve('.data/coach-relay.png')});
  await button.click();await page.locator('#journey-view.coach-journey').waitFor();
  assert(await page.locator('#journey-coach').isVisible());assert(!(await page.locator('#journey-player').isVisible()));
  assert(!(await page.locator('#world-map').isVisible()));
  assert(!(await page.evaluate(()=>document.body.classList.contains('hud-menu-open'))));
  await page.screenshot({path:path.resolve('.data/coach-journey.png')});
  await page.reload();await page.waitForFunction(()=>Boolean(session?.tutorial));
  await page.waitForFunction(()=>session?.tutorial?.field_map==='lisiere' && !session.tutorial.moving,{},{timeout:20000});
  assert(await page.locator('#coach-view').isVisible());
  assert.equal(await page.locator('#coach-view button').count(),0);
  assert((await page.locator('#coach-view').textContent()).includes('aucune diligence'));
  assert(!(await page.evaluate(()=>document.body.classList.contains('hud-menu-open'))));
  await page.screenshot({path:path.resolve('.data/coach-dropoff.png')});
  await page.evaluate(()=>renderJourney({moving:true,battle:null,world:{routes:[]},transit:{mode:'walk'},travel_progress:.5,travel_remaining_real_seconds:3,location:'A',travel_destination_name:'B'}));
  assert(await page.locator('#journey-player').isVisible());assert(!(await page.locator('#journey-coach').isVisible()));
  await page.reload();await page.waitForFunction(()=>session?.tutorial?.field_map==='lisiere');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,checks:['boarding menu','animated horse and carriage','no automatic atlas','reload mid-trip','physical dropoff','no return service','old walking animation preserved','arrival persistence']}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
