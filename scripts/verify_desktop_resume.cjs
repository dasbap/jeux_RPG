"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),{_electron,chromium}=require("../.ui-test/node_modules/playwright");
const root=path.resolve(__dirname,".."),source=process.argv.includes("--profile-source")?path.resolve(process.argv[process.argv.indexOf("--profile-source")+1]):null;
if(!source)throw new Error("Pass --profile-source <profile>; the source is copied and never opened for writing.");
const profile=fs.mkdtempSync(path.join(root,".data/resume-verification-")),target=path.join(profile,"Partitions","jeux-rpg");
fs.mkdirSync(target,{recursive:true});
for(const name of ["IndexedDB","Local Storage"]){const from=path.join(source,"Partitions","jeux-rpg",name);if(fs.existsSync(from))fs.cpSync(from,path.join(target,name),{recursive:true,filter:p=>path.basename(p)!=="LOCK"});}
const executablePath=process.env.RPG_DESKTOP_EXECUTABLE||(process.argv.includes("--portable")?path.join(root,"dist/windows/Jeux-RPG.exe"):process.argv.includes("--packaged")?path.join(root,"dist/client/win-unpacked/Jeux-RPG.exe"):require("../desktop/node_modules/electron"));
const env={...process.env,RPG_DESKTOP_TEST:"1",RPG_DESKTOP_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
async function launch(){
 let app,page;
 if(process.argv.includes("--portable")){
  const net=require("node:net"),{spawn,execFile}=require("node:child_process"),listener=net.createServer();
  await new Promise(resolve=>listener.listen(0,"127.0.0.1",resolve));const port=listener.address().port;await new Promise(resolve=>listener.close(resolve));
  const child=spawn(executablePath,[`--remote-debugging-port=${port}`],{env,windowsHide:true,stdio:"ignore"});
  let browser;
  for(let attempt=0;attempt<100;attempt++){try{browser=await chromium.connectOverCDP(`http://127.0.0.1:${port}`,{timeout:1000});break;}catch{await new Promise(resolve=>setTimeout(resolve,200));}}
  if(!browser)throw new Error("Portable client did not expose its test debugging port.");
  const context=browser.contexts()[0];page=context.pages()[0]||await context.waitForEvent("page");
  await context.route(/^(https?|wss?):/,route=>route.abort());
  const cdp=await context.newCDPSession(page);await cdp.send("Emulation.setFocusEmulationEnabled",{enabled:true});
  app={close:async()=>{
    const exited=new Promise(resolve=>child.once("exit",resolve));
    await page.evaluate(async()=>{if(soloTransport)await soloTransport.flush();window.close();}).catch(()=>{});
    await Promise.race([exited,new Promise(resolve=>setTimeout(resolve,10000))]);
    if(child.exitCode===null)await new Promise(resolve=>execFile("taskkill",["/PID",String(child.pid),"/T","/F"],{windowsHide:true},()=>resolve()));
  }};
 }else{
  app=await _electron.launch({executablePath,args:process.argv.includes("--packaged")?[]:[path.join(root,"desktop")],env,timeout:60000});
  await app.evaluate(({BrowserWindow,session})=>{BrowserWindow.getAllWindows()[0].webContents.setBackgroundThrottling(false);session.fromPartition("persist:jeux-rpg").webRequest.onBeforeRequest({urls:["https://*/*","http://*/*","wss://*/*","ws://*/*"]},(_,done)=>done({cancel:true}));});
  page=await app.firstWindow();
 }
 await page.waitForFunction(()=>typeof gameMode!=="undefined"&&gameMode==="solo"&&!busy&&(session?.tutorial||!document.getElementById("characters").hidden),null,{timeout:60000});
 if(await page.evaluate(()=>!session?.tutorial)){
  assert(await page.locator("[data-character]").count()>1,"Single-character resume must not fail back to the roster");
  await page.locator('[data-character][aria-pressed="true"]').click();
 }
 await page.waitForFunction(()=>!!session?.tutorial,null,{timeout:60000});
 await page.locator("#loading-screen").waitFor({state:"hidden"});
 assert(await page.locator("#battle").isVisible());
 if(await page.evaluate(()=>!!session.tutorial.battle))await page.waitForFunction(()=>document.querySelector(".rpg-canvas3d")?.scene3D.stats.frames>2);
 const state=await page.evaluate(async()=>{const player=session.tutorial.players.find(p=>p.id===session.me),account=await api("/api/account/me");return {session:session.id,player:session.me,count:account.characters.length,inventory:player.inventory,gold:player.gold,level:player.level};});
 return {app,page,state};
}
(async()=>{let current;try{
 current=await launch();const first=current.state;
 await current.app.close();current=null;
 current=await launch();assert.equal(current.state.session,first.session);assert.equal(current.state.player,first.player);assert.equal(current.state.count,first.count);assert.deepEqual(current.state.inventory,first.inventory);assert.equal(current.state.gold,first.gold);assert.equal(current.state.level,first.level);
 await current.page.screenshot({path:path.join(root,".data/desktop-resume-fixed.png")});
 console.log(JSON.stringify({passed:true,executable:executablePath,checks:["copied existing profile", "offline old-save migration", "visible adventure", "native close and restart", "characters, level, inventory and gold retained"],characters:first.count}));
 }finally{if(current)await current.app.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
