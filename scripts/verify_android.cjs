"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {_android} = require("../.ui-test/node_modules/playwright");
const {execFileSync} = require("node:child_process");
const root = path.resolve(__dirname, "..");
const linuxRoot = process.platform === "win32" ? "/mnt/" + root[0].toLowerCase() + root.slice(2).replaceAll("\\", "/") : root;
function adb(...args) {
  const command = process.platform === "win32" ? "wsl" : "bash";
  const prefix = process.platform === "win32" ? ["-d", "Ubuntu", "-u", "root", "--", "bash"] : [];
  return execFileSync(command, [...prefix, linuxRoot + "/scripts/android-adb.sh", ...args], {encoding:"utf8",timeout:60000});
}
async function connect() {
  const [device]=await _android.devices({omitDriverInstall:true});
  assert(device,"Émulateur Android connecté");
  const view=await device.webView({pkg:"fr.jeuxrpg.mobile.debug",timeout:60000});
  const page=await view.page();
  const browser={close:()=>device.close()};
  return {browser,page};
}
(async()=>{
  const errors=[];
  adb("install","-r",linuxRoot+"/android/app/build/outputs/apk/debug/app-debug.apk");
  adb("shell","pm","clear","fr.jeuxrpg.mobile.debug");
  adb("shell","svc","wifi","disable");
  adb("shell","svc","data","disable");
  adb("shell","am","start","-n","fr.jeuxrpg.mobile.debug/fr.jeuxrpg.mobile.MainActivity");
  let current=await connect();
  try {
    const page=current.page;
    page.on("pageerror",error=>errors.push(error.message));
    await page.locator("#solo-entry").waitFor({timeout:60000});
    assert(await page.evaluate(()=>isSecureContext&&Boolean(navigator.locks)));
    await page.click("#solo-entry");
    await page.locator("#characters:not([hidden])").waitFor({timeout:120000});
    await page.fill("#new-character-name","Android hors ligne");
    await page.selectOption("#new-character-class","Knight");
    await page.click("#character-create button");
    await page.click("#tutorial");
    await page.waitForFunction(()=>Boolean(session?.tutorial),null,{timeout:60000});
    const id=await page.evaluate(()=>session.id);
    assert.equal(await page.evaluate(()=>session.tutorial.world.zone_entries.zone_rosee),"rosee");
    await page.screenshot({path:path.join(root,".data/android-offline.png")});
    adb("shell","am","force-stop","fr.jeuxrpg.mobile.debug");
    await current.browser.close();
    adb("shell","am","start","-n","fr.jeuxrpg.mobile.debug/fr.jeuxrpg.mobile.MainActivity");
    current=await connect();
    await current.page.waitForFunction(expected=>session?.id===expected,id,{timeout:120000});
    assert.equal(await current.page.evaluate(()=>gameMode),"solo");
    await current.page.evaluate(()=>document.getElementById("show-quest").click());
    assert(await current.page.evaluate(()=>document.body.classList.contains("hud-menu-open")));
    adb("shell","input","keyevent","4");
    await current.page.waitForFunction(()=>!document.body.classList.contains("hud-menu-open"));
    adb("shell","input","keyevent","4");
    await new Promise(resolve=>setTimeout(resolve,800));
    const resumed=adb("shell","dumpsys","activity","activities").split("\n").find(line=>line.includes("mResumedActivity"))||"";
    assert(!resumed.includes("fr.jeuxrpg.mobile.debug"),"Retour Android quitte après sauvegarde");
    assert.deepEqual(errors,[]);
    console.log("Android : APK installé, réseau coupé, personnage créé, solo lancé, sauvegarde automatique après arrêt forcé, reprise et bouton Retour natif vérifiés.");
  } finally {await current.browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
