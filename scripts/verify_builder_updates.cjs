"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {_electron}=require("../.ui-test/node_modules/playwright");
const root=path.resolve(__dirname,".."),profile=fs.mkdtempSync(path.join(root,".data/builder-update-"));
const env={...process.env,RPG_DESKTOP_TEST:"1",RPG_DESKTOP_DATA_DIR:profile};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const app=await _electron.launch({executablePath:path.join(root,"dist/client/win-unpacked/Jeux-RPG.exe"),env,timeout:60000});
 try{
  await app.evaluate(async({app,session})=>{
   const require=process.getBuiltinModule("module").createRequire(app.getAppPath()+"/main.cjs");
   const fs=require("node:fs"),path=require("node:path"),base=app.getAppPath(),assets=path.join(base,"assets");
   const handler=require(path.join(base,"runtime.cjs")).createHandler({root:assets,manifest:require(path.join(assets,"manifest.json"))});
   const protocol=session.fromPartition("persist:jeux-rpg").protocol;
   await protocol.unhandle("rpg");
   await protocol.handle("rpg",request=>new URL(request.url).pathname==="/solo_worker.js"?new Response(fs.readFileSync(path.join(assets,"solo_worker.js"),"utf8")+"\nglobalThis.builderSetup=code=>python.runPython(code);\n",{headers:{"Content-Type":"application/javascript"}}):handler(request));
  });
  const page=await app.firstWindow(),errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.click("#solo-entry");
  await page.locator("#characters:not([hidden])").waitFor({timeout:60000});
  await page.fill("#new-character-name","Builder existant");
  await page.selectOption("#new-character-class","Knight");
  await page.click("#character-create button");
  await page.click("#tutorial");
  await page.waitForFunction(()=>Boolean(session?.tutorial),null,{timeout:30000});
  const worker=page.workers().find(worker=>worker.url().includes("solo_worker"));
  await worker.evaluate(()=>globalThis.builderSetup(`
from jeuxRPG.multiplayer import fields
row = solo.db.execute("SELECT session_id,data FROM tutorials").fetchone()
party = json.loads(row["data"])
fields.enter(party, "lisiere", [1, 10], solo.service.clock.now())
party["mobs"] = []
party["mob"] = None
party["battle"].pop("spawn_manifest", None)
party["battle"]["initial_mobs"] = 0
party["inventory"]["peau"] = 17
solo.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
solo.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (row["session_id"],))
`));
  await page.evaluate(()=>refresh(true));
  await page.waitForFunction(()=>session.tutorial.field_map==="lisiere"&&session.tutorial.battle.spawn_manifest);
  const actual=await worker.evaluate(()=>JSON.parse(globalThis.builderSetup(`
party = json.loads(solo.db.execute("SELECT data FROM tutorials").fetchone()["data"])
json.dumps({"mobs": [{"id": m["mob_id"], "home": m["home"]} for m in party["mobs"]], "inventory": party["inventory"]["peau"]})
`)));
  const definition=JSON.parse(fs.readFileSync(path.join(root,"projects/authored/world.json"),"utf8")).lisiere;
  const expected=definition.spawns.flatMap(position=>{
   const config=definition.spawners.find(config=>JSON.stringify(config.position)===JSON.stringify(position))||{};
   return Array.from({length:config.count||1},()=>config.mob_id||"goblin");
  }).sort();
  assert.deepEqual(actual.mobs.map(mob=>mob.id).sort(),expected,"La sauvegarde vide reçoit exactement les espèces et nombres du Builder");
  assert.equal(actual.inventory,17,"L’inventaire personnel est conservé");
  const rendered=await page.evaluate(()=>session.tutorial.battle.map.spawners);
  assert.deepEqual(rendered,definition.spawners,"Le client affiche le catalogue actuel");
  assert.deepEqual(errors,[]);
  console.log(`Windows solo: ancienne lisière vide actualisée avec ${actual.mobs.length} mobs du Builder, inventaire conservé.`);
 }finally{await app.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
