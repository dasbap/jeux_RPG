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
(async () => {
  let current;
  try {
    current = await launch();
    const page = current.page;
    assert.equal(page.url(), "rpg://client/");
    assert.equal(await page.evaluate(() => typeof require), "undefined");
    assert.equal(await page.evaluate(() => isSecureContext && Boolean(navigator.locks)), true);
    await page.click("#solo-entry");
    await page.locator("#characters:not([hidden])").waitFor({timeout: 60000});
    await page.fill("#new-character-name", "Bureau hors ligne");
    await page.selectOption("#new-character-class", "Knight");
    await page.click("#character-create button");
    await page.click("#tutorial");
    await page.waitForFunction(() => Boolean(session?.tutorial), null, {timeout: 30000});
    const world = await page.evaluate(() => session.tutorial.world);
    const livingWorld = await page.evaluate(() => session.tutorial.living_world);
    const sprite = page.locator('image[data-sprite="chevalier_original"]').first();
    await sprite.waitFor();
    assert.equal(await sprite.getAttribute("data-weapon"),"arme_sword_shield");
    assert(await page.evaluate(()=>{
      const data=session.tutorial.sprites;
      return data.bindings["mob:gobelin_archer"]===data.bindings["mob:garde_gobelin"]&&data.equipment["mob:gobelin_archer"]==="arme_bow"&&data.equipment["mob:garde_gobelin"]==="arme_sword_shield";
    }),"Les variantes de gobelins réutilisent le corps et changent seulement l'arme");
    assert(await page.evaluate(async () => {
      const source=document.querySelector('image[data-sprite="chevalier_original"]').getAttribute("href");
      const image=new Image();image.src=source;
      try {await image.decode();return image.naturalWidth===session.tutorial.sprites.assets.chevalier_original.width;}catch{return false;}
    }),"Le sprite embarqué se décode hors ligne avec la politique CSP du client");
    await sprite.click();
    await page.waitForFunction(()=>focusedMob===session.me);
    assert(await page.locator(`[data-unit] .objective-ring`).count()>0,"Un personnage avec sprite reste sélectionnable");
    await sprite.click();
    assert(livingWorld?.towns.length > 0,"Le monde vivant est actif dans le moteur solo embarqué");
    assert(livingWorld.merchant.stock.length > 0,"La caravane dispose de son stock partagé local");
    assert.equal(world.zone_entries.zone_rosee, "rosee");
    const interfaceSettings=await page.evaluate(()=>session.tutorial.interface);
    const authoredInterface=JSON.parse(fs.readFileSync(path.join(root,"projects/authored/content.json"),"utf8")).content.interface || {};
    assert.equal(interfaceSettings.menus.width_percent,authoredInterface.menus?.width_percent ?? 75);
    assert.equal(interfaceSettings.menus.position,authoredInterface.menus?.position ?? "center");
    await page.locator("#game-menu-toggle").click();
    assert((await page.locator("#game-menu-items").boundingBox()).width<=280);
    assert(await page.locator("#combat-player-panel").isVisible());
    await page.locator("#show-quest").click();
    await page.locator("#quest-type").selectOption("main");
    assert.equal(await page.locator("#quest-type").inputValue(),"main");
    assert.equal(await page.locator("#quest-category").count(),1);
    const menuFrame=await page.locator(".adventure-grid").boundingBox();
    const viewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    assert(Math.abs(menuFrame.width-viewport.width*interfaceSettings.menus.width_percent/100)<2&&Math.abs(menuFrame.height-viewport.height*interfaceSettings.menus.height_percent/100)<2);
    const expectedLeft=interfaceSettings.menus.position==="left"?12:interfaceSettings.menus.position==="right"?viewport.width-menuFrame.width-12:(viewport.width-menuFrame.width)/2;
    assert(Math.abs(menuFrame.x-expectedLeft)<2&&Math.abs(menuFrame.y+menuFrame.height/2-viewport.height/2)<2);
    for(const id of ["combat-player-panel","combat-enemy-panel","combat-action-panel","hud-navigation","game-menu-toggle","mob-list-toggle"])assert(!await page.locator("#"+id).isVisible(),`HUD masqué : ${id}`);
    await page.evaluate(()=>document.getElementById("back-view").click());
    assert(world.graph.clearing.includes("forest"));
    assert(world.graph.forest.includes("rosee"));
    assert(!world.graph.zone_lisiere.includes("forest"));
    const enemyToggle = await page.locator("#mob-list-toggle").boundingBox();
    assert(await page.locator("#game-menu-toggle").isVisible(),"Le HUD revient à la fermeture du panneau");
    assert(enemyToggle.x > (await page.evaluate(()=>innerWidth))/2,"Le bouton cheval est à droite dans le client compilé");
    await page.evaluate(()=>showView("map",{toggle:false}));
    assert(await page.locator("#world-life-view").isVisible(),"La vie du monde est accessible depuis la carte");
    assert.equal(await page.locator("#world-life-towns article").count(),livingWorld.towns.length);
    const detail=page.locator('#region-map > svg[data-map^="detail:"]').last();
    await detail.scrollIntoViewIfNeeded();
    const beforePan=await detail.getAttribute("viewBox"),detailBox=await detail.boundingBox();
    const dragX=detailBox.x+detailBox.width/2,dragY=detailBox.y+detailBox.height/2;
    await page.mouse.move(dragX,dragY);await page.mouse.down();
    await page.mouse.move(dragX-60,dragY-30,{steps:5});await page.mouse.up();
    assert.notEqual(await detail.getAttribute("viewBox"),beforePan,"La carte du menu se déplace dans le client Windows");
    await page.locator("#region-center").click();
    assert.equal(await detail.getAttribute("viewBox"),beforePan,"Le recentrage restaure toute la carte");
    await page.locator("#back-view").click();
    await page.evaluate(()=>showView("bestiary",{toggle:false}));
    const filtering = await page.evaluate(() => {
      const originalBestiary=session.tutorial.world.bestiary, originalRender=renderGame;
      const base={rank:"D",description:"Fiche de recette locale",hp:{first_encounter:20,hunt:30},stats:{force:5,endurance:3,intelligence:1,sagesse:1},weaknesses:[],resistances:[],loot:[{item:"Cuir",quantity:1,max_quantity:1,chance:1,attempts:1}],xp:{hunt:10},rare_loot:[],materials_usage:"Forge"};
      const maps=[{id:"local-a",name:"Auberge"},{id:"local-z",name:"Zéphyr"}];
      let redraws=0;
      try {
        session.tutorial.world.bestiary=Array.from({length:80},(_,index)=>({...base,id:`local-${index}`,name:`Créature ${String(index).padStart(2,"0")}`,spawn_maps:index%2?[maps[0]]:maps}));
        renderBestiary(session.tutorial);
        const first=$("bestiary-details").firstElementChild;
        renderBestiary(session.tutorial);
        const retained=first===$("bestiary-details").firstElementChild;
        renderGame=(...args)=>{redraws++;return originalRender(...args);};
        const times=[];
        for(let index=0;index<20;index++) {
          const start=performance.now();
          $("bestiary-map").value=index%2?"":"local-z";
          $("bestiary-map").dispatchEvent(new Event("change"));
          const expected=index%2?80:40;
          if($("bestiary-details").querySelectorAll("article").length!==expected)throw Error("Le filtre carte n'est pas immédiatement appliqué");
          times.push(performance.now()-start);
        }
        $("bestiary-search").value="Créature 07";
        $("bestiary-search").dispatchEvent(new Event("input"));
        const searched=$("bestiary-details").querySelectorAll("article").length;
        $("bestiary-search").value="";$("bestiary-search").dispatchEvent(new Event("input"));
        $("bestiary-sort").value="desc";$("bestiary-sort").dispatchEvent(new Event("change"));
        return {redraws,retained,searched,sorted:$("bestiary-details").firstElementChild.textContent.includes("Zéphyr, Auberge"),maxMs:Math.max(...times),averageMs:times.reduce((a,b)=>a+b,0)/times.length};
      } finally {
        renderGame=originalRender;
        session.tutorial.world.bestiary=originalBestiary;
        $("bestiary-search").value="";$("bestiary-map").value="";$("bestiary-sort").value="asc";
        renderBestiary(session.tutorial);
      }
    });
    assert.equal(filtering.redraws,0,"Les filtres du bestiaire ne redessinent pas le jeu");
    assert(filtering.retained&&filtering.sorted&&filtering.searched===1);
    console.log(`Bestiaire compilé, 80 fiches fictives : ${filtering.averageMs.toFixed(1)} ms en moyenne, ${filtering.maxMs.toFixed(1)} ms au maximum sur 20 changements ; aucun rendu global.`);
    await page.locator("#back-view").click();
    const id = await page.evaluate(() => session.id);
    // Close immediately after starting: the native close hook must flush IndexedDB.
    const closed = current.app.waitForEvent("close");
    await current.app.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows()[0].close());
    await closed;
    current = await launch();
    await current.page.waitForFunction(expected => session?.id === expected, id, {timeout: 60000});
    assert.equal(await current.page.evaluate(() => gameMode), "solo");
    assert.deepEqual(await current.page.evaluate(() => session.tutorial.living_world.towns),livingWorld.towns,"Le monde vivant est conservé après fermeture et reprise du client");
    const result = await current.page.evaluate(async () => (await fetch("/api/classes")).json());
    assert(result.some(item => item.id === "Knight"));
    await current.page.screenshot({path: path.join(root, ".data/desktop-offline.png")});
    assert.deepEqual(errors, []);
    console.log(`Client ${packaged ? "compilé" : "source"} : réseau bloqué, tutoriel solo, sauvegarde à la fermeture, reprise après redémarrage et isolation Node vérifiés.`);
  } finally { if (current) await current.app.close().catch(() => {}); }
})().catch(error => {console.error(error); process.exitCode = 1;});
