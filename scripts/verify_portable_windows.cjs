"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");
const {spawn, execFile} = require("node:child_process");
const {chromium} = require("../.ui-test/node_modules/playwright");
const root = path.resolve(__dirname, "..");
const executable = process.env.RPG_DESKTOP_EXECUTABLE || path.join(root, "dist/windows/Jeux-RPG.exe");
fs.mkdirSync(path.join(root, ".data"), {recursive:true});
const profile = fs.mkdtempSync(path.join(root, ".data/portable-verification-"));
const errors = [];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function launch() {
  const listener = net.createServer();
  await new Promise(resolve => listener.listen(0, "127.0.0.1", resolve));
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const env = {...process.env, RPG_DESKTOP_TEST:"1", RPG_DESKTOP_DATA_DIR:profile};
  delete env.ELECTRON_RUN_AS_NODE;
  const args=[`--remote-debugging-port=${port}`];
  if(process.platform==="linux")args.push("--no-sandbox","--ozone-platform=headless","--use-angle=swiftshader","--enable-unsafe-swiftshader");
  const child = spawn(executable, args, {env, windowsHide:true, stdio:"ignore"});
  let browser;
  async function close(page) {
    const exited = child.exitCode === null ? new Promise(resolve => child.once("exit", resolve)) : Promise.resolve();
    if (page) await page.evaluate(async () => {await soloTransport?.flush(); window.close();}).catch(() => {});
    await Promise.race([exited, delay(10000)]);
    if (child.exitCode === null) {
      if(process.platform==="win32")await new Promise(resolve => execFile("taskkill", ["/PID", String(child.pid), "/T", "/F"], {windowsHide:true}, resolve));
      else child.kill("SIGKILL");
    }
    await browser?.close();
  }
  try {
    for (let attempt=0; attempt<150; attempt++) {
      try {browser=await chromium.connectOverCDP(`http://127.0.0.1:${port}`, {timeout:1000}); break;}
      catch {if(child.exitCode !== null)throw Error("Portable exited before exposing its test port"); await delay(200);}
    }
    if (!browser) throw Error("Portable did not expose its test port");
    const context=browser.contexts()[0];
    await context.route(/^(https?|wss?):/, route => route.abort());
    const page=context.pages()[0] || await context.waitForEvent("page");
    page.on("pageerror", error => errors.push(error.message));
    const cdp=await context.newCDPSession(page);
    await cdp.send("Emulation.setFocusEmulationEnabled", {enabled:true});
    await page.waitForLoadState("domcontentloaded");
    return {page, close:()=>close(page)};
  } catch (error) {await close(); throw error;}
}
async function ready(page) {
  await page.waitForFunction(()=>Boolean(session?.tutorial), null, {timeout:90000});
  await page.locator("#loading-screen").waitFor({state:"hidden", timeout:90000});
  await page.waitForFunction(()=>document.querySelector(".rpg-canvas3d")?.scene3D.stats.frames>2).catch(async error=>{
    console.error(await page.evaluate(()=>({hidden:document.hidden,renderer:document.getElementById("world-map").dataset.renderer,stats:document.querySelector(".rpg-canvas3d")?.scene3D.stats})));
    throw error;
  });
}
async function state(page) {
  return page.evaluate(()=>{const p=session.tutorial.players.find(p=>p.id===session.me);return {session:session.id,player:session.me,level:p.level,gold:p.gold,inventory:p.inventory};});
}
(async()=>{
  let current;
  try {
    current=await launch();
    await current.page.click("#solo-entry");
    await current.page.locator("#characters:not([hidden])").waitFor({timeout:90000});
    await current.page.fill("#new-character-name", "Docker hors ligne");
    await current.page.selectOption("#new-character-class", "Knight");
    await current.page.click("#character-create button");
    await current.page.click("#tutorial");
    await ready(current.page);
    assert.equal(await current.page.locator("#field-camera").isVisible(), false);
    const offsets=await current.page.evaluate(()=>{
      const panel=document.getElementById("npc-view"),hidden=panel.hidden;
      panel.hidden=false;
      const animations=panel.getAnimations();
      if(!animations.some(a=>a.animationName==="npc-dialogue-arrive"))throw Error("Missing centered dialogue animation");
      const values=[];
      for(const time of [0,16,140,279,300]) {
        for(const animation of animations){animation.pause();animation.currentTime=time;}
        const rect=panel.getBoundingClientRect();values.push(rect.x+rect.width/2-innerWidth/2);
      }
      for(const animation of animations)animation.cancel();
      panel.hidden=hidden;
      return values;
    });
    assert(offsets.every(offset=>Math.abs(offset)<1), JSON.stringify(offsets));
    const first=await state(current.page);
    await current.close();current=null;
    current=await launch();await ready(current.page);
    assert.deepEqual(await state(current.page), first);
    await current.page.screenshot({path:path.join(root,".data/portable-docker-offline.png")});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed:true, executable, checks:["offline solo creation", "WebGL scene", "toolbar hidden", "dialogue centered from first frame", "normal close and restart", "character retained"]}));
  } finally {if(current)await current.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
