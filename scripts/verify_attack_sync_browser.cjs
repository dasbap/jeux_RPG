"use strict";
const assert=require("node:assert/strict"),readline=require("node:readline");
const {chromium}=require("../.data/browser-tools/node_modules/playwright");
const reader=readline.createInterface({input:process.stdin}),input=reader[Symbol.asyncIterator]();
const receive=async()=>JSON.parse((await input.next()).value),emit=value=>process.stdout.write(JSON.stringify(value)+"\n");
(async()=>{
 const config=await receive(),browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],strikes=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.route("**/*",route=>new URL(route.request().url()).origin===config.url?route.continue():route.abort());
  await page.goto(config.url);await page.locator("#registration details summary").click();
  await page.locator("#login-name").fill("WorldLocalTest");await page.locator("#login-password").fill(config.password);
  await page.locator('#restore-form button[type="submit"]').click();await page.locator("#character-list button").first().click();
  await page.waitForFunction(()=>Boolean(document.querySelector(".rpg-canvas3d")?.scene3D));
  const fixture=async(kind,at)=>{emit({advance:at,scene_fixture:kind});await receive();await page.evaluate(async()=>{await refresh(true);RPGMotion.rebase();renderGame(session.tutorial);});};
  page.on("request",request=>{if(request.url().endsWith("/api/commands")&&request.postDataJSON()?.action==="strike")strikes.push(request.postDataJSON());});
  await fixture("near",1);
  await page.locator(".rpg-canvas3d").focus();
  await page.route(`${config.url}/api/commands`,async route=>{if(["move_axis","stop_move"].includes(route.request().postDataJSON()?.action))await new Promise(resolve=>setTimeout(resolve,350));await route.continue();});
  await page.keyboard.down("ArrowLeft");
  await page.waitForFunction(()=>RPGMotion.position(session.tutorial,session.me)?.[0]<32.4,null,{timeout:5000}).catch(async error=>{console.error(JSON.stringify(await page.evaluate(()=>({position:session.tutorial.battle.players[session.me].position,local:RPGMotion.position(session.tutorial,session.me),axis:RPGMotion.axis,active:document.activeElement?.id,classes:document.body.className,me:session.tutorial.players[0],errors:document.getElementById("message").textContent}))));throw error;});
  await page.keyboard.press("Space");assert.equal(strikes.length,0,"A displayed retreat must not attack from an older nearby position");
  await page.keyboard.up("ArrowLeft");await page.waitForFunction(()=>!RPGMotion.pending);
  assert(await page.evaluate(()=>Math.hypot(...session.tutorial.mobs[0].position.map((v,i)=>v-session.tutorial.battle.players[session.me].position[i]))>session.tutorial.players[0].attack_range));
  emit({check:"Retreat under 350 ms movement latency blocks the out-of-range attack",result:"passed"});
  await fixture("far",3);
  await page.locator(".rpg-canvas3d").focus();
  await page.keyboard.down("ArrowRight");
  await page.waitForFunction(()=>RPGMotion.position(session.tutorial,session.me)?.[0]>32.57);
  await page.keyboard.press("Space");await page.keyboard.up("ArrowRight");
  await page.waitForFunction(()=>!busy&&!RPGMotion.pending);
  await page.evaluate(()=>refresh(true));
  assert.equal(strikes.length,1);assert(strikes[0].params.position[0]>32.5);assert(Number.isInteger(strikes[0].params.position_seq));
  assert(await page.evaluate(()=>session.tutorial.mobs[0].stats.hp.current<100),"The engine must validate the position carried with the legal attack");
  assert.deepEqual(errors,[]);
  emit({check:"Approach carries a speed-validated position with the attack; delayed older movement cannot rewind it",result:"passed"});
 }finally{await browser.close();reader.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
