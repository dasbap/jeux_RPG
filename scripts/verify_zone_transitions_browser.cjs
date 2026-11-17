"use strict";
const assert=require("node:assert/strict"),readline=require("node:readline");
const {chromium}=require("../.data/browser-tools/node_modules/playwright");
const input=readline.createInterface({input:process.stdin})[Symbol.asyncIterator]();
const receive=async()=>JSON.parse((await input.next()).value),emit=value=>process.stdout.write(JSON.stringify(value)+"\n");
(async()=>{
 const config=await receive(),browser=await chromium.launch({headless:true});let closing=false;
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960},serviceWorkers:"block"}),errors=[],external=[],commands=[];
  page.on("pageerror",e=>errors.push(e.message));
  await page.route("**/*",route=>{const url=new URL(route.request().url());if(url.origin===config.url)return route.continue();external.push(url.origin);return route.abort();});
  await page.goto(config.url);await page.locator("#registration details summary").click();
  await page.locator("#login-name").fill("WorldLocalTest");await page.locator("#login-password").fill(config.password);
  await page.locator('#restore-form button[type="submit"]').click();await page.locator("#character-list button").first().click();
  await page.waitForFunction(()=>document.querySelector(".rpg-canvas3d")?.scene3D.stats.frames>3);
  await page.route(`${config.url}/api/commands`,async route=>{
   try{const body=route.request().postDataJSON(),response=await route.fetch(),data=await response.json();
    commands.push({action:body.action,encounter:body.params.encounter,position:body.params.position,status:response.status(),error:data.error});
    await new Promise(resolve=>setTimeout(resolve,180));await route.fulfill({response});
   }catch(error){if(!closing)errors.push(error.message.split("\n")[0]);}
  });
  await page.locator(".rpg-canvas3d").focus();
  const resets=await page.evaluate(()=>RPGMotion.diagnostics.hardResets),crossings=[];
  for(const [code,destination,entry,axis] of [["ArrowUp","rosee_caserne",30,-1],["ArrowDown","rosee",1,1],["ArrowUp","rosee_caserne",30,-1]]){
   const previous=await page.evaluate(()=>session.tutorial.encounter_number);
   await page.keyboard.down(code);
   await page.waitForFunction(({destination,previous})=>session.tutorial.field_map===destination&&session.tutorial.encounter_number>previous,{destination,previous},{timeout:20000});
   // Hold the same physical key: no click, second keydown, focus change or pointer movement.
   await page.waitForFunction(({destination,entry,axis})=>session.tutorial.field_map===destination&&(session.tutorial.battle.players[session.me].position[1]-entry)*axis>1,{destination,entry,axis},{timeout:15000});
   crossings.push(await page.evaluate(()=>({map:session.tutorial.field_map,encounter:session.tutorial.encounter_number,position:session.tutorial.battle.players[session.me].position})));
   await page.keyboard.up(code);
   try{await page.waitForFunction(()=>!RPGMotion.pending&&session.tutorial.battle.players[session.me].motion_axis?.every(v=>v===0),null,{timeout:8000});}
   catch(error){console.error(JSON.stringify({commands,crossings,state:await page.evaluate(()=>({map:session.tutorial.field_map,encounter:session.tutorial.encounter_number,axis:RPGMotion.axis,pending:RPGMotion.pending,unit:session.tutorial.battle.players[session.me],diagnostics:RPGMotion.diagnostics,message:document.querySelector("#message").textContent}))}));throw error;}
  }
  const stopped=await page.evaluate(()=>session.tutorial.battle.players[session.me].position);
  await page.waitForTimeout(650);assert.deepEqual(await page.evaluate(()=>session.tutorial.battle.players[session.me].position),stopped);
  const diagnostics=await page.evaluate(()=>RPGMotion.diagnostics);
  assert.equal(diagnostics.hardResets,resets);assert.equal(diagnostics.maxCorrectionStep,0);
  assert(commands.filter(c=>c.action==="move_axis").every(c=>Array.isArray(c.position)),"Every first command in a new zone carries its arrival position");
  assert.deepEqual(commands.filter(c=>c.status!==200&&!["stale_encounter","movement_speed"].includes(c.error)),[]);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  await page.screenshot({path:".data/zone-transitions.png"});
  emit({check:"Real-time local engine: three zone crossings with a held key, no extra click, delayed replies, arrival position sent and no correction",result:"passed",crossings,diagnostics});
 }finally{closing=true;await browser.close();}
})().then(()=>process.exit(0),error=>{console.error(error);process.exit(1);});
