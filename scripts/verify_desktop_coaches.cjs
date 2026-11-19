"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {_electron} = require("../.ui-test/node_modules/playwright");
const root = path.resolve(__dirname, "..");
const packaged = process.argv.includes("--packaged");
const executablePath = process.env.RPG_DESKTOP_EXECUTABLE || (packaged ? path.join(root, "dist/client/win-unpacked/Jeux-RPG.exe") : require("../desktop/node_modules/electron"));
fs.mkdirSync(path.join(root, ".data"), {recursive: true});
const profile = fs.mkdtempSync(path.join(root, ".data/desktop-verification-"));
const env = {...process.env, RPG_DESKTOP_TEST: "1", RPG_DESKTOP_DATA_DIR: profile};
delete env.ELECTRON_RUN_AS_NODE;
const errors = [];
async function launch() {
  const args = packaged ? [] : [path.join(root, "desktop")];
  if (process.platform === "linux") args.push("--no-sandbox", "--ozone-platform=headless");
  const app = await _electron.launch({executablePath, args, env, timeout: 60000});
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].webContents.setBackgroundThrottling(false));
  await app.evaluate(({session}) => {
    // Block native requests too, including the main process API bridge.
    session.fromPartition("persist:jeux-rpg").webRequest.onBeforeRequest({urls: ["https://*/*", "http://*/*", "wss://*/*", "ws://*/*"]}, (_details, callback) => callback({cancel: true}));
  });
  const page = await app.firstWindow();
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && /Content Security Policy|Traceback/.test(message.text())) errors.push(message.text()); });
  await page.waitForLoadState("domcontentloaded");
  return {app, page};
}
(async()=>{
 let current;
 try {
  current=await launch();const page=current.page;
  const cdp=await page.context().newCDPSession(page);await cdp.send("Emulation.setFocusEmulationEnabled",{enabled:true});
  await page.click("#solo-entry");await page.locator("#characters:not([hidden])").waitFor({timeout:60000});
  await page.fill("#new-character-name","Cocher hors ligne");await page.selectOption("#new-character-class","Knight");await page.click("#character-create button");await page.click("#tutorial");
  await page.waitForFunction(()=>Boolean(session?.tutorial?.field_map),null,{timeout:30000});
  await page.evaluate(()=>{const a=session.tutorial,me=a.players.find(p=>p.id===session.me),stop=a.battle.map.sites.find(s=>s.id==="coach_foret");toggleGameMenu(false);moveControlled(a,me,stop.position);});
  await page.locator('[data-coach-route="foret_rosee"]').waitFor({timeout:30000});
  await page.locator('[data-coach-route="foret_rosee"]').click();
  await page.locator('#journey-view.coach-journey').waitFor();
  assert(await page.locator('#journey-coach').isVisible());assert(!(await page.locator('#world-map').isVisible()));
  await page.waitForFunction(()=>session?.tutorial?.field_map==="rosee"&&!session.tutorial.moving,null,{timeout:20000});
  await page.evaluate(()=>soloTransport.flush());await current.app.close();current=null;
  current=await launch();await current.page.waitForFunction(()=>session?.tutorial?.field_map==="rosee",null,{timeout:60000});
  assert(await current.page.locator('[data-coach-route="rosee_brume"]').count()>0);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,checks:["offline Pyodide engine","walk to physical relay","board coach","animated carriage","direct playable arrival","native restart at arrival relay"]}));
 } finally {if(current)await current.app.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
