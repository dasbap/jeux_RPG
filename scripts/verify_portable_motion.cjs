"use strict";
// Exercise the distributed NSIS portable itself, using an isolated save profile.
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),net=require("node:net");
const {spawn}=require("node:child_process"),{once}=require("node:events");
const {chromium}=require("../.ui-test/node_modules/playwright");
const root=path.resolve(__dirname,".."),exe=process.env.RPG_DESKTOP_EXECUTABLE||path.join(root,"dist/windows/Jeux-RPG-correctif.exe");
const profile=fs.mkdtempSync(path.join(root,".data/portable-motion-"));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const errors=[];let current;
async function launch(){
 const server=net.createServer();server.listen(0,"127.0.0.1");await once(server,"listening");const port=server.address().port;await new Promise(r=>server.close(r));
 const env={...process.env,RPG_DESKTOP_TEST:"0",RPG_DESKTOP_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
 const child=spawn(exe,[`--remote-debugging-port=${port}`,"--remote-debugging-address=127.0.0.1","--disable-background-timer-throttling","--disable-renderer-backgrounding","--disable-backgrounding-occluded-windows"],{env,cwd:root,windowsHide:true,stdio:"ignore"});
 current={child};let version;
 for(let i=0;i<300;i++){try{version=await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();break;}catch{await sleep(200);}}
 assert(version,"The distributed portable must expose its local diagnostic endpoint");
 const browser=await chromium.connectOverCDP(version.webSocketDebuggerUrl),context=browser.contexts()[0];
 let page=context.pages()[0];if(!page)page=await context.waitForEvent("page");
 page.on("pageerror",e=>errors.push(e.message));
 await context.route(/^(https?|wss?):/,route=>route.abort());
 await page.waitForURL("rpg://client/");await page.waitForLoadState("domcontentloaded");await page.bringToFront();
 current={child,browser,page};return current;
}
async function close(){
 if(!current)return;const {page,child,browser}=current;
 if(page&&!page.isClosed())await page.evaluate(()=>window.close()).catch(()=>{});
 for(let i=0;i<50&&child.exitCode===null;i++)await sleep(100);
 if(child.exitCode===null)throw Error("Portable did not close after save flush");
 await browser?.close().catch(()=>{});current=null;
}
async function record(page,code,duration){
 await page.locator(".rpg-canvas3d").focus();
 await page.evaluate(()=>{globalThis.portableFrames=[];globalThis.portableRecording=true;function frame(t){if(!portableRecording)return;const hero=document.querySelector(".rpg-canvas3d")?.scene3D.items.find(a=>a.hero);if(Array.isArray(hero?.display))portableFrames.push([t,...hero.display,...session.tutorial.battle.players[session.me].position]);requestAnimationFrame(frame);}requestAnimationFrame(frame);});
 const started=Date.now();await page.keyboard.down(code);
 try{await page.waitForFunction(ms=>portableFrames.length>30&&portableFrames.at(-1)[0]-portableFrames[0][0]>=ms,duration,{timeout:20000});}
 catch(error){console.error(JSON.stringify(await page.evaluate(()=>({visibility:document.visibilityState,frames:portableFrames.length,first:portableFrames[0],last:portableFrames.at(-1),axis:RPGMotion.axis,pending:RPGMotion.pending,stats:document.querySelector(".rpg-canvas3d")?.scene3D.stats,errors:document.querySelector("#message")?.textContent}))),errors);throw error;}
 const running=await page.evaluate(()=>{portableRecording=false;return portableFrames;});
 await page.keyboard.up(code);await page.waitForFunction(()=>!RPGMotion.pending&&session.tutorial.battle.players[session.me].motion_axis.every(v=>v===0));
 return {running,elapsed:Date.now()-started};
}
(async()=>{
 try{
  const {page}=await launch();
  if(process.argv.includes("--zones")){
   await require("./verify_portable_zones.cjs")(page,root);assert.deepEqual(errors,[]);return;
  }
  await page.click("#solo-entry");await page.locator("#characters:not([hidden])").waitFor({timeout:90000});
  await page.fill("#new-character-name","Test correctif portable");await page.selectOption("#new-character-class","Knight");await page.click("#character-create button");await page.click("#tutorial");
  await page.waitForFunction(()=>document.querySelector(".rpg-canvas3d")?.scene3D.stats.frames>3,null,{timeout:60000});
  const lane=await page.evaluate(()=>{const a=session.tutorial,p=a.battle.players[session.me].position;for(let distance=9;distance>=2;distance--)for(const [axis,code] of [[[1,0],"ArrowRight"],[[0,1],"ArrowDown"],[[-1,0],"ArrowLeft"],[[0,-1],"ArrowUp"]]){const end=p.map((v,i)=>v+axis[i]*distance);const route=gridPath(a.battle.map,p,end);if(route?.length===distance&&route.every(v=>v[axis[0]?1:0]===p[axis[0]?1:0]))return {axis,code,distance};}});
  assert(lane,"Test requires at least two clear cells in one direction");
  const resets=await page.evaluate(()=>RPGMotion.diagnostics.hardResets);
  await page.evaluate(()=>{const original=RPGMotion.sample;globalThis.speedSamples=[];RPGMotion.sample=(a,me,now)=>{const p=original(a,me,now);if(p)speedSamples.push([now,...p]);return p;};});
  // Delay both pushed state and movement acknowledgements; the Python engine stays real-time.
  await page.evaluate(()=>{const transport=globalThis.rpgRealtime,original=transport.onState,request=transport.request.bind(transport),delays=[40,160,65,240,110,190];let count=0;globalThis.delayedStates=0;transport.onState=result=>{const delay=delays[count++%delays.length];setTimeout(()=>{delayedStates++;original(result);},delay);};transport.request=async(path,options)=>{const result=await request(path,options);if(path==="/api/commands"&&JSON.parse(options.body||"{}").action==="move_axis")await new Promise(r=>setTimeout(r,120));return result;};});
  const {running}=await record(page,lane.code,3000);
  let backstep=0,maxStep=0;
  for(let i=1;i<running.length;i++){const delta=running[i].slice(1,3).map((v,k)=>v-running[i-1][k+1]);backstep=Math.max(backstep,-delta.reduce((s,v,k)=>s+v*lane.axis[k],0));maxStep=Math.max(maxStep,Math.hypot(...delta));}
  const progress=running.at(-1).slice(1,3).reduce((s,v,k)=>s+(v-running[0][k+1])*lane.axis[k],0);
  const metrics=await page.evaluate(()=>({diagnostics:RPGMotion.diagnostics,states:delayedStates,position:session.tutorial.battle.players[session.me].position,stats:document.querySelector(".rpg-canvas3d").scene3D.stats}));
  assert(progress>1);assert(backstep<.012,`Rollback while holding direction: ${backstep}`);assert.equal(metrics.diagnostics.hardResets,resets);assert(metrics.states>=5);assert(metrics.stats.vertices>1000);
  const samples=await page.evaluate(()=>speedSamples),maximum=await page.evaluate(()=>session.tutorial.battle.motion_rules.speed*session.tutorial.battle.motion_rules.ratio);let peakSpeed=0;
  for(let i=1;i<samples.length;i++){const dt=(samples[i][0]-samples[i-1][0])/1000;if(dt>0)peakSpeed=Math.max(peakSpeed,Math.hypot(samples[i][1]-samples[i-1][1],samples[i][2]-samples[i-1][2])/dt);}
  assert(peakSpeed<=maximum+1e-6,`Local speed ${peakSpeed} exceeds ${maximum}`);
  assert.equal(metrics.diagnostics.maxCorrectionStep,0,"Ordinary snapshots must never adjust a legal local movement");
  const displayed=await page.evaluate(()=>speedSamples.at(-1).slice(1));
  assert(Math.hypot(...displayed.map((v,i)=>v-metrics.position[i]))<1e-6,"The engine accepts the exact local stopping position");
  const held=metrics.position;await sleep(650);assert.deepEqual(await page.evaluate(()=>session.tutorial.battle.players[session.me].position),held,"Release stops authoritative movement");
  await page.screenshot({path:path.join(root,".data/portable-motion-correctif.png")});
  const id=await page.evaluate(()=>session.id);
  console.log(JSON.stringify({check:"Exact distributed portable: real Python engine, delayed states 40–240 ms, 120 ms motion acknowledgements, stop on release",result:"passed",frames:running.length,progress,backstep,maxStep,peakSpeed,maximum,...metrics}));
  await page.evaluate(()=>soloTransport.flush());
  await close();const reopened=await launch();
  await reopened.page.waitForFunction(()=>Boolean(session?.tutorial),null,{timeout:90000});
  console.log(JSON.stringify({check:"Reopened portable identity",expected:id,actual:await reopened.page.evaluate(()=>({id:session.id,name:session.tutorial.players.find(p=>p.id===session.me)?.name,position:session.tutorial.battle.players[session.me].position}))}));
  assert.equal(await reopened.page.evaluate(()=>session.id),id);
  assert.deepEqual(await reopened.page.evaluate(()=>session.tutorial.battle.players[session.me].position),held);
  assert.deepEqual(errors,[]);console.log("Portable: save flushed on close and exact position restored on reopen; no JavaScript errors.");
 }finally{await close();}
})().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
