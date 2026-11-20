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
  const cdp=await page.context().newCDPSession(page);await cdp.send("Emulation.setFocusEmulationEnabled",{enabled:true});
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && /Content Security Policy|Traceback/.test(message.text())) errors.push(message.text()); });
  await page.waitForLoadState("domcontentloaded");
  return {app, page};
}
(async()=>{
 let current;
 try {
  current=await launch();let page=current.page;
  await page.click("#solo-entry");await page.locator("#characters:not([hidden])").waitFor({timeout:60000});
  await page.fill("#new-character-name","Depeceur hors ligne");await page.selectOption("#new-character-class","Knight");await page.click("#character-create button");await page.click("#tutorial");
  await page.waitForFunction(()=>Boolean(session?.tutorial?.field_map),null,{timeout:30000});
  await page.evaluate(()=>soloTransport.flush());
  const readSave=()=>page.evaluate(async()=>{
    const db=await new Promise((resolve,reject)=>{const r=indexedDB.open("jeux-rpg-solo",1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    try{return await new Promise((resolve,reject)=>{const tx=db.transaction("saves","readonly"),r=tx.objectStore("saves").get("game");tx.oncomplete=()=>resolve(btoa(Array.from(new Uint8Array(r.result),b=>String.fromCharCode(b)).join("")));tx.onerror=()=>reject(tx.error);});}finally{db.close();}
  });
  const saved=await readSave();
  const code=[
    "import os, json, sqlite3, sys",
    "os.environ['RPG_MAPS_FILE']=str(__import__('pathlib').Path('jeuxRPG/maps').resolve())",
    "from jeuxRPG.multiplayer import fields, spawn_cycles",
    "from jeuxRPG.multiplayer.field_spawners import origin",
    "db=sqlite3.connect(':memory:');db.deserialize(sys.stdin.buffer.read())",
    "row=db.execute('SELECT session_id,data FROM tutorials').fetchone();p=json.loads(row[1])",
    "player=next(iter(p['characters']));position=p['battle']['players'][player]['position']",
    "p['battle']['corpses']=[{'id':'offline-body','name':'Corps hors ligne','position':position[:],'loot':{'peau':5},'harvested':[]}]",
    "key,group=next(iter(spawn_cycles.groups(p['field_map'],fields.MAPS[p['field_map']]).items()))",
    "p['mobs']=[m for m in p['mobs'] if origin(m)!=group['origins'][0]]",
    "p['spawn_timers']={p['field_map']:{key:{'next_at':-group['interval'],'interval':group['interval']}}}",
    "db.execute('UPDATE tutorials SET data=? WHERE session_id=?',(json.dumps(p),row[0]));db.commit();sys.stdout.buffer.write(db.serialize())"
  ].join("\n");
  const bytes=require('node:child_process').execFileSync(process.env.PYTHON||'python',['-c',code],{input:Buffer.from(saved,'base64')});
  await page.evaluate(()=>soloTransport.close());
  await page.evaluate(async bytes=>{
    const db=await new Promise((resolve,reject)=>{const r=indexedDB.open("jeux-rpg-solo",1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    try{await new Promise((resolve,reject)=>{const tx=db.transaction('saves','readwrite');tx.objectStore('saves').put(Uint8Array.from(atob(bytes),c=>c.charCodeAt(0)),'game');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});}finally{db.close();}
  },bytes.toString('base64'));
  await page.reload();await page.waitForFunction(()=>session?.tutorial?.battle?.corpses?.some(c=>c.id==='offline-body'),null,{timeout:60000});
  await page.evaluate(()=>soloTransport.flush());
  const respawnSave=await readSave();
  require('node:child_process').execFileSync(process.env.PYTHON||'python',['-c',"import json,sqlite3,sys;db=sqlite3.connect(':memory:');db.deserialize(sys.stdin.buffer.read());p=json.loads(db.execute('SELECT data FROM tutorials').fetchone()[0]);assert any(':repop:' in m['combat_id'] for m in p['mobs'])"],{input:Buffer.from(respawnSave,'base64')});
  await page.evaluate(()=>document.body.classList.remove('hud-menu-open'));
  await page.locator('#loading-screen').waitFor({state:'hidden'});
  await page.locator('.rpg-canvas3d').focus();await page.keyboard.press('x');await page.waitForFunction(()=>focusedMob==='offline-body',{},{timeout:5000}).catch(async error=>{console.error(await page.evaluate(()=>({hidden:document.hidden,body:document.body.className,focused:focusedMob,binding:RPGKeybindings.label('harvest_target'),me:session.tutorial.players.find(p=>p.id===session.me),corpses:session.tutorial.battle.corpses,message:document.querySelector('#message').textContent})));throw error;});
  await page.keyboard.press('g');await page.waitForFunction(()=>session.tutorial.players.find(p=>p.id===session.me).inventory.peau===5);
  await page.evaluate(()=>soloTransport.flush());await current.app.close();current=null;
  current=await launch();page=current.page;
  await page.waitForFunction(()=>session?.tutorial?.players?.find(p=>p.id===session.me)?.inventory?.peau===5,null,{timeout:60000});
  assert(await page.evaluate(()=>session.tutorial.battle.corpses.find(c=>c.id==='offline-body').harvested.length===1));
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,checks:['offline Pyodide respawn scheduler','persisted overdue spawn replenishes','X corpse targeting','G harvest','inventory after native restart','no double loot']}));
 }finally{if(current)await current.app.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
