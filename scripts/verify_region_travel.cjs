"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {_electron} = require("../.ui-test/node_modules/playwright");
const root = path.resolve(__dirname, "..");
const profile = fs.mkdtempSync(path.join(root, ".data/region-travel-"));
const env = {...process.env, RPG_DESKTOP_TEST:"1", RPG_DESKTOP_DATA_DIR:profile};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
  const app = await _electron.launch({executablePath:path.join(root,"dist/client/win-unpacked/Jeux-RPG.exe"),env,timeout:60000});
  try {
    const page = await app.firstWindow();
    const errors=[];page.on("pageerror",error=>errors.push(error.message));
    await app.evaluate(async ({app,session})=>{
      const require=process.getBuiltinModule("module").createRequire(app.getAppPath()+"/main.cjs");
      const fs=require("node:fs"),path=require("node:path");
      const base=app.getAppPath(),assets=path.join(base,"assets");
      const handler=require(path.join(base,"runtime.cjs")).createHandler({root:assets,manifest:require(path.join(assets,"manifest.json"))});
      const protocol=session.fromPartition("persist:jeux-rpg").protocol;
      await protocol.unhandle("rpg");
      await protocol.handle("rpg",request=>{
        if(new URL(request.url).pathname === "/solo_worker.js")return new Response(
          fs.readFileSync(path.join(assets,"solo_worker.js"),"utf8")+"\nglobalThis.regionTravelSetup = code => { python.runPython(code); };\n",
          {headers:{"Content-Type":"application/javascript"}}
        );
        return handler(request);
      });
    });
    await page.click("#solo-entry");
    await page.locator("#characters:not([hidden])").waitFor({timeout:60000});
    await page.fill("#new-character-name","Durée région");
    await page.selectOption("#new-character-class","Knight");
    await page.click("#character-create button");
    await page.click("#tutorial");
    await page.waitForFunction(()=>Boolean(session?.tutorial),null,{timeout:30000});
    const worker = page.workers().find(worker=>worker.url().includes("solo_worker"));
    assert(worker,"Moteur solo Pyodide disponible");
    for(const source of ["rosee","forest","clearing"]) {
      await worker.evaluate(source=>globalThis.regionTravelSetup(`
from jeuxRPG.multiplayer import fields, tactics
row = solo.db.execute("SELECT session_id,data FROM tutorials").fetchone()
party = json.loads(row["data"])
source = ${JSON.stringify(source)}
gate = fields.MAPS[source]["exits"][0]
x,y = gate["position"]
entry = [1 if x == 0 else fields.MAPS[source]["width"]-2 if x == fields.MAPS[source]["width"]-1 else x, 1 if y == 0 else fields.MAPS[source]["height"]-2 if y == fields.MAPS[source]["height"]-1 else y]
party.update(journey=[], transit=None)
fields.enter(party,source,entry,0)
solo.service.random = lambda: 1
solo.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
solo.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (row["session_id"],))
`),source);
      await page.evaluate(()=>refresh(true));
      await page.waitForFunction(source=>session.tutorial.field_map===source,source);
      await page.evaluate(()=>{document.body.classList.remove("hud-menu-open");});
      await page.evaluate(()=>{const [x,y]=session.tutorial.battle.map.exits[0].position;return tutorialCommand("battle_move",{x,y,path:[[x,y]]});});
      await page.waitForFunction(()=>!session.tutorial.field_map&&!session.tutorial.moving,null,{timeout:15000});
      await page.waitForFunction(()=>!document.getElementById("region-view").hidden);
      assert(await page.locator("#region-view").isVisible(),`${source} : carte globale ouverte`);
      await page.waitForTimeout(1000);
      assert.equal(await page.evaluate(()=>Boolean(session.tutorial.moving)),false,`${source} : aucun trajet forcé`);
      assert.equal(await page.evaluate(()=>session.tutorial.position),source);
    }
    console.log("Solo compilé : les sorties du village et des deux forêts ouvrent la carte globale, sans marche automatique.");
    // Prepare a traveller at Rosée in this disposable profile only.
    await worker.evaluate(()=>{
      globalThis.regionTravelSetup(`
row = solo.db.execute("SELECT session_id,data FROM tutorials").fetchone()
party = json.loads(row["data"])
solo.service.random = lambda: 1
party.update(position="rosee", step="village", battle=None, mobs=[], mob=None, journey=[], transit=None)
party.pop("field_map", None)
party["visited"] = ["clearing", "rosee"]
solo.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
solo.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (row["session_id"],))
`);
    });
    await page.evaluate(()=>refresh(true));
    await page.waitForFunction(()=>session.tutorial.position === "rosee" && !session.tutorial.battle);
    await page.evaluate(()=>showView("map",{toggle:false}));
    assert(await page.locator("#region-view").isVisible());
    assert((await page.locator("#world-map .route-name").count())>0);
    assert.equal(await page.locator('#region-map > svg[data-map="general"]').count(),0,"Pas de carte globale en double dans le panneau");
    assert.equal(await page.locator("#world-map .route-badge").count(),0);
    assert((await page.locator("#world-map .route-name text").first().textContent()).length>1);
    await page.screenshot({path:path.join(root,".data/region-routes-readable.png")});
    const started = Date.now();
    await page.evaluate(()=>tutorialCommand("move",{destination:"foret_eveilles"}));
    await page.waitForFunction(()=>Boolean(session.tutorial.transit));
    assert(await page.locator("#journey-view").isVisible());
    const first = await page.locator("#journey-progress").evaluate(element=>element.value);
    await page.waitForTimeout(1000);
    const next = await page.locator("#journey-progress").evaluate(element=>element.value);
    assert(next>first,"Le personnage progresse pendant le trajet");
    await page.screenshot({path:path.join(root,".data/region-travel-moving.png")});
    assert.equal(await page.evaluate(()=>session.tutorial.field_map || null),null,"Le trajet ne finit pas en moins d'une seconde");
    await page.waitForFunction(()=>session.tutorial.field_map === "clearing",null,{timeout:25000});
    const elapsed = Date.now()-started;
    assert(elapsed>=9000,`Durée trop courte : ${elapsed} ms`);
    assert.equal(await page.locator("#region-view").isVisible(),false,"La carte de région se ferme à l'arrivée");
    assert.equal(await page.locator("#journey-view").isVisible(),false);
    assert.equal(await page.evaluate(()=>document.body.classList.contains("hud-menu-open")),false);
    assert.deepEqual(errors,[]);
    await page.screenshot({path:path.join(root,".data/region-travel-arrival.png")});
    console.log(`Solo compilé : village → Forêt des Éveillés en ${(elapsed/1000).toFixed(2)} s réelles ; carte de région fermée à l'arrivée.`);
    await worker.evaluate(()=>globalThis.regionTravelSetup(`
row = solo.db.execute("SELECT session_id,data FROM tutorials").fetchone()
party = json.loads(row["data"])
party.update(position="lisiere", battle=None, mobs=[], mob=None, journey=[], transit=None)
party.pop("field_map", None)
solo.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
solo.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (row["session_id"],))
`));
    await page.evaluate(()=>refresh(true));
    await page.waitForFunction(()=>session.tutorial.position === "lisiere");
    await page.evaluate(()=>tutorialCommand("move",{destination:"rosee"}));
    assert.equal(await page.evaluate(()=>session.tutorial.transit.destination),"rosee_lisiere");
    console.log("Lisière → village : Chemin de la lisière sélectionné, sans passage par la grotte.");
    await worker.evaluate(()=>globalThis.regionTravelSetup(`
from jeuxRPG.multiplayer import forge, content
from jeuxRPG.multiplayer.service import GameError
row = solo.db.execute("SELECT session_id,data FROM tutorials").fetchone()
party = json.loads(row["data"])
party.update(position="forge", quest="completed", battle=None, mobs=[], mob=None, journey=[], transit=None)
party.pop("field_map", None)
player = next(iter(party["characters"]))
party["inventory"][player] = {item:1000 for item in content.gameplay()["materials"]}
for recipe in ("casque","veste","gants","jambieres","bottes"):
    forge.execute(party,player,"craft",recipe,GameError)
solo.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
solo.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (row["session_id"],))
`));
    await page.evaluate(()=>refresh(true));
    await page.evaluate(()=>showView("equipment",{toggle:false}));
    const set=page.locator('[data-set="lisiere"]');
    assert.equal(await set.locator(".set-tier.active").count(),3);
    const hp=await page.evaluate(()=>session.tutorial.players[0].max_hp);
    await page.evaluate(()=>refresh(true));
    assert.equal(await page.evaluate(()=>session.tutorial.players[0].max_hp),hp,"Le rafraîchissement ne multiplie pas les bonus");
    await page.evaluate(()=>tutorialCommand("craft",{recipe:"bottes_lucioles"}));
    await page.waitForFunction(()=>session.tutorial.players[0].equipment_sets[0].pieces===4);
    assert.equal(await set.locator(".set-tier.active").count(),2);
    assert.equal(await page.evaluate(()=>session.tutorial.players[0].max_hp),hp-7,"Les PV retirent le palier 5 et prennent les nouvelles bottes en compte");
    await page.screenshot({path:path.join(root,".data/equipment-set-mixed.png")});
    console.log("Panoplie solo : paliers 2/4/5 actifs à cinq pièces, puis perte du palier 5 et ajustement réel des PV après remplacement.");
  } finally {await app.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
