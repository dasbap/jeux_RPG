"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {_electron}=require("../.ui-test/node_modules/playwright");
const root=path.resolve(__dirname,".."),packaged=process.argv.includes("--packaged");
const executablePath=packaged?path.join(root,"dist/client/win-unpacked/Jeux-RPG.exe"):require("../desktop/node_modules/electron");
const profile=fs.mkdtempSync(path.join(root,".data/narrative-verification-"));
const env={...process.env,RPG_DESKTOP_TEST:"1",RPG_DESKTOP_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
let app;
(async()=>{
 try {
  app=await _electron.launch({executablePath,args:packaged?[]:[path.join(root,"desktop")],env,timeout:60000});
  const page=await app.firstWindow(),errors=[];page.on("pageerror",error=>errors.push(error.message));
  page.on("console",message=>{if(message.type()==="error"&&/Content Security Policy|Traceback/.test(message.text()))errors.push(message.text());});
  await app.evaluate(async({app,session})=>{
   const require=process.getBuiltinModule("module").createRequire(app.getAppPath()+"/main.cjs");
   const fs=require("node:fs"),path=require("node:path"),base=app.getAppPath(),assets=path.join(base,"assets");
   const handler=require(path.join(base,"runtime.cjs")).createHandler({root:assets,manifest:require(path.join(assets,"manifest.json"))});
   const partition=session.fromPartition("persist:jeux-rpg");
   partition.webRequest.onBeforeRequest({urls:["https://*/*","http://*/*","wss://*/*","ws://*/*"]},(_details,callback)=>callback({cancel:true}));
   await partition.protocol.unhandle("rpg");
   await partition.protocol.handle("rpg",request=>new URL(request.url).pathname==="/solo_worker.js"?new Response(fs.readFileSync(path.join(assets,"solo_worker.js"),"utf8")+"\nglobalThis.narrativeSetup=code=>python.runPython(code);\n",{headers:{"Content-Type":"application/javascript"}}):handler(request));
  });
  await page.click("#solo-entry");await page.locator("#characters:not([hidden])").waitFor({timeout:60000});
  await page.fill("#new-character-name","Témoin de la Veille");await page.selectOption("#new-character-class","Knight");
  await page.click("#character-create button");await page.click("#tutorial");
  await page.waitForFunction(()=>Boolean(session?.tutorial?.narrative),null,{timeout:60000});
  console.log("Histoire : partie solo démarrée.");
  const worker=page.workers().find(worker=>worker.url().includes("solo_worker"));assert(worker);
  async function setup(code){await worker.evaluate(code=>globalThis.narrativeSetup(`
from jeuxRPG.multiplayer import content,fields,narrative
row=solo.db.execute("SELECT session_id,data FROM tutorials").fetchone()
party=json.loads(row["data"])
player=next(iter(party["characters"]))
${code}
solo.db.execute("UPDATE tutorials SET data=? WHERE session_id=?",(json.dumps(party),row["session_id"]))
solo.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?",(row["session_id"],))
`),code);await page.evaluate(()=>refresh(true));}
  async function at(npc){await setup(`
map_id,site=next((key,site) for key,definition in fields.MAPS.items() for site in definition["sites"] if site["id"]==${JSON.stringify(npc)})
entry=next([site["position"][0]+dx,site["position"][1]+dy] for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)] if __import__("jeuxRPG.multiplayer.tactics",fromlist=["walkable"]).walkable(fields.MAPS[map_id],[site["position"][0]+dx,site["position"][1]+dy]))
fields.enter(party,map_id,entry,solo.service._now())
`);await page.waitForFunction(npc=>Boolean(session.tutorial.field_interactions?.some(site=>site.id===npc)),npc);}
  async function talk(npc){await page.locator(`.field-site[data-site="${npc}"]`).click();await page.locator("#story-dialog").waitFor({state:"visible"});await page.waitForFunction(npc=>document.getElementById("story-dialog").dataset.npc===npc,npc);}
  async function close(){await page.click("#story-close");await page.locator("#story-dialog").waitFor({state:"hidden"});await page.waitForFunction(()=>!busy);}
  await at("mira");await talk("mira");
  console.log("Histoire : première conversation de Mira ouverte.");
  assert.equal(await page.evaluate(()=>session.tutorial.quest_journal.length),0,"Parler n’accepte aucun contrat");
  await page.locator('#story-quests [data-quest="mira_hunt_1"] button').click();
  await page.waitForFunction(()=>session.tutorial.quest_journal.length===1);
  const focus=page.locator('#story-topics button[data-story-key="routes"]');await focus.focus();
  await page.waitForTimeout(1200);
  assert(await focus.evaluate(node=>document.activeElement===node),"Le dialogue et son focus résistent aux rafraîchissements");
  await page.setViewportSize({width:390,height:844});
  const bounds=await page.locator("#story-dialog").boundingBox();
  assert(bounds.x>=0&&bounds.x+bounds.width<=391&&bounds.height<=844,"Dialogue utilisable sur mobile");
  await page.screenshot({path:path.join(root,".data/story-mira-mobile.png")});
  await page.setViewportSize({width:1424,height:920});await close();
  await at("forge");await talk("forge");
  assert(await page.locator("#story-service button").isDisabled(),"Forge clairement verrouillée avant remise");
  assert(!await page.locator("#craft-view").isVisible(),"Parler au forgeron ouvre sa conversation");await close();
  await setup(`
party.update(position="hunt",field_map="hunt",battle=None,mobs=[],mob=None)
for _ in range(4):content.quest_event(party,"kill","goblin","zone_lisiere")
`);
  await at("mira");await talk("mira");await page.locator('#story-quests [data-quest="mira_hunt_1"] button').click();
  await page.waitForFunction(()=>session.tutorial.forge_unlocked);await close();
  await at("borne_veille");await talk("borne_veille");
  await page.locator('#story-topics button[data-story-key="lire"]').click();
  await page.waitForFunction(()=>session.tutorial.narrative.notes.some(note=>note.id==="borne_lue"));await close();
  await at("clearing:0");await talk("clearing:0");
  await page.locator('#story-quests [data-quest="derniere_borne"] button').click();
  await page.waitForFunction(()=>session.tutorial.quest_journal.some(q=>q.id==="derniere_borne"&&q.status==="ready"));
  await page.locator('#story-quests [data-quest="derniere_borne"] button').click();
  await page.waitForFunction(()=>session.tutorial.quest_journal.some(q=>q.id==="derniere_borne"&&q.status==="completed"));await close();
  await at("forge");await talk("forge");
  await page.locator('#story-quests [data-quest="craft_bottes_lucioles"] button').click();
  assert((await page.locator("#npc-dialogue").textContent()).includes("Mira m’a parlé"),"L’accueil de Garrik reflète le déblocage de la forge");
  await page.waitForFunction(()=>session.tutorial.quest_journal.some(q=>q.id==="craft_bottes_lucioles"));
  await page.click("#story-service button");await page.locator("#craft-view").waitFor({state:"visible"});
  await setup('party["inventory"][player]={key:1000 for key in content.gameplay()["materials"]}');
  await page.locator('#forge-catalogue [data-recipe="bottes_lucioles"] button[data-action="craft"]').click();
  await page.waitForFunction(()=>session.tutorial.players[0].gear.some(piece=>piece.recipe==="bottes_lucioles"));
  await page.click("#forge-close");await talk("forge");
  await page.locator('#story-quests [data-quest="craft_bottes_lucioles"] button').click();
  await page.waitForFunction(()=>session.tutorial.quest_journal.some(q=>q.id==="craft_bottes_lucioles"&&q.status==="completed"));
  await page.locator('#story-quests [data-quest="upgrade_bottes_lucioles"] button').click();
  await page.waitForFunction(()=>session.tutorial.quest_journal.some(q=>q.id==="upgrade_bottes_lucioles"));
  await page.screenshot({path:path.join(root,".data/story-garrik-desktop.png")});await close();
  await page.evaluate(()=>showView("quest",{toggle:false}));
  assert(await page.locator("#story-notes").isVisible());
  const id=await page.evaluate(()=>session.id);
  assert.deepEqual(errors,[]);
  await app.close();app=null;
  app=await _electron.launch({executablePath,args:packaged?[]:[path.join(root,"desktop")],env,timeout:60000});
  const resumed=await app.firstWindow();
  await resumed.waitForFunction(id=>session?.id===id&&Boolean(session.tutorial?.narrative),id,{timeout:60000});
  assert(await resumed.evaluate(()=>session.tutorial.forge_unlocked));
  assert(await resumed.evaluate(()=>session.tutorial.narrative.notes.some(note=>note.id==="borne_lue")));
  assert(await resumed.evaluate(()=>session.tutorial.quest_journal.some(q=>q.id==="upgrade_bottes_lucioles")));
  console.log(`Histoire ${packaged?"compilée":"source"} : acceptation explicite, dialogue mobile stable, indice, remise, déblocage et fabrication à la forge, prérequis et reprise de sauvegarde vérifiés hors ligne.`);
 }catch(error){
  if(app){const page=await app.firstWindow();await page.screenshot({path:path.join(root,".data/story-ui-failure.png")}).catch(()=>{});console.error(await page.evaluate(()=>({message:document.getElementById("message")?.textContent,connection:document.getElementById("connection")?.textContent,view:session?.tutorial?.field_map,story:session?.tutorial?.narrative,dialog:document.getElementById("story-dialog")?.open})).catch(()=>({})));}
  throw error;
 }finally{if(app)await app.close().catch(()=>{});}
})().catch(error=>{console.error(error);process.exitCode=1;});
