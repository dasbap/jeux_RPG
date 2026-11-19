"use strict";
const assert=require("node:assert/strict"),readline=require("node:readline");
const {chromium}=require("../.data/browser-tools/node_modules/playwright");
const input=readline.createInterface({input:process.stdin})[Symbol.asyncIterator]();
const receive=async()=>JSON.parse((await input.next()).value),emit=v=>process.stdout.write(JSON.stringify(v)+"\n");
(async()=>{
 const config=await receive(),browser=await chromium.launch({headless:true});let closing=false;
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960},serviceWorkers:"block"}),errors=[],external=[],commands=[];
  page.on("response",async response=>{if(response.url().endsWith("/api/commands")){const body=await response.json();commands.push({status:response.status(),action:response.request().postDataJSON()?.action,position:response.request().postDataJSON()?.params?.position,error:body.error,message:body.message});}});
  page.on("pageerror",e=>errors.push(e.message));
  await page.route("**/*",route=>{const url=new URL(route.request().url());if(url.origin===config.url)return route.continue();external.push(url.origin);return route.abort();});
  await page.goto(config.url);await page.locator("#registration details summary").click();
  await page.locator("#login-name").fill("WorldLocalTest");await page.locator("#login-password").fill(config.password);
  await page.locator('#restore-form button[type="submit"]').click();await page.locator("#character-list button").first().click();
  await page.waitForFunction(()=>document.querySelector(".rpg-canvas3d")?.scene3D.stats.frames>3);
  const delays=[40,160,65,240,110,190];let packets=0;
  await page.route(`${config.url}/api/state`,async route=>{try{const response=await route.fetch();await new Promise(resolve=>setTimeout(resolve,delays[packets++%delays.length]));await route.fulfill({response});}catch(error){if(!closing)errors.push(error.message.split("\n")[0]);}});
  await page.locator(".rpg-canvas3d").focus();
  const before=await page.evaluate(()=>({x:document.querySelector(".rpg-canvas3d").scene3D.items.find(a=>a.hero).display[0],resets:RPGMotion.diagnostics.hardResets}));
  await page.evaluate(()=>{const original=api;globalThis.commandTimes=[];api=async(path,body,...rest)=>{if(body?.params?.position)commandTimes.push({at:performance.now(),position:body.params.position});return original(path,body,...rest);};});
  await page.evaluate(()=>{globalThis.motionFrames=[];globalThis.recordMotion=true;function record(t){if(!globalThis.recordMotion)return;const a=document.querySelector(".rpg-canvas3d")?.scene3D.items.find(a=>a.hero);if(Array.isArray(a?.display))motionFrames.push([t,...a.display]);requestAnimationFrame(record);}requestAnimationFrame(record);});
  await page.keyboard.down("ArrowRight");
  await page.waitForFunction(()=>motionFrames.length>=80&&motionFrames.at(-1)[0]-motionFrames[0][0]>=6000,null,{timeout:20000});
  const running=await page.evaluate(()=>motionFrames.slice());
  await page.keyboard.up("ArrowRight");
  await page.waitForFunction(()=>!RPGMotion.pending);
  const summary=await page.evaluate(()=>{globalThis.recordMotion=false;return {frames:motionFrames,diagnostics:RPGMotion.diagnostics,unit:session.tutorial.battle.players[session.me].position};});
  if(summary.diagnostics.hardResets)console.error(JSON.stringify({commands,times:await page.evaluate(()=>commandTimes),summary:summary.diagnostics,unit:summary.unit}));
  assert(packets>=4);assert(running.at(-1)[1]>before.x+.5);
  let largestBackstep=0;
  for(let i=1;i<running.length;i++)largestBackstep=Math.max(largestBackstep,running[i-1][1]-running[i][1]);
  assert(largestBackstep<.012,`Visible backward step while walking: ${largestBackstep}`);
  assert.equal(summary.diagnostics.hardResets,before.resets);
  assert(summary.diagnostics.maxCorrectionStep<=.65*.05+1e-6);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  emit({check:"Real-time local engine, response jitter 40–240 ms: no teleport or visible rollback during held movement",result:"passed",packets,frames:running.length,largestBackstep,correctionMax:summary.diagnostics.maxCorrectionStep});
 }finally{closing=true;await browser.close();}
})().then(()=>process.exit(0),error=>{process.stderr.write(error.stack+"\n");process.exit(1);});
