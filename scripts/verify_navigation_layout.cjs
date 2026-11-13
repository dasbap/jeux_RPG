"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("../.ui-test/node_modules/playwright");
const root = path.join(__dirname,"..");
const web = path.join(root,"jeuxRPG/multiplayer/web");
const fixtures = JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const output = path.join(root,"hud-captures/navigation");
const overlaps = (a,b) => a&&b&&a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RPG_BROWSER_EXECUTABLE});
 fs.mkdirSync(output,{recursive:true});
 try {
  for(const [width,height] of [[1440,900],[1280,720],[390,844],[844,390]]) {
   const page=await browser.newPage({viewport:{width,height},reducedMotion:"reduce"});
   const errors=[];page.on("pageerror",error=>errors.push(error.message));
   const html=fs.readFileSync(path.join(web,"index.html"),"utf8").replace(/<script[^>]*>.*?<\/script>/gs,"");
   await page.route("http://hud.test/**",route=>route.fulfill({contentType:route.request().url().endsWith(".css")?"text/css":"text/html",body:route.request().url().endsWith(".css")?fs.readFileSync(path.join(web,"style.css"),"utf8"):html}));
   await page.goto("http://hud.test/");
   await page.evaluate(()=>{window.fetch=()=>new Promise(()=>{});window.setInterval=()=>0;});
   for(const file of ["map_artwork.js","mobile_controls.js",...require("./client_source.cjs").files])await page.addScriptTag({content:fs.readFileSync(path.join(web,file),"utf8")});
   await page.evaluate(adventure=>{
    token="fixture";gameMode="solo";session={id:"layout",state:"running",revision:1,me:"p0",tutorial:adventure,events:[]};
    for(const id of ["registration","characters","lobby"])document.getElementById(id).hidden=true;
    for(const id of ["battle","tutorial-panel"])document.getElementById(id).hidden=false;
    renderGame(adventure);
   },fixtures.combat);
   const box=id=>page.locator("#"+id).boundingBox();
   const mini=await box("hud-navigation"),player=await box("combat-player-panel"),enemy=await box("combat-enemy-panel"),camera=await box("field-camera"),stick=await box("touch-stick");
   assert(!overlaps(mini,player),"La minicarte ne couvre pas les PV");
   assert(!overlaps(mini,enemy),"La minicarte ne couvre pas les ennemis");
   assert(!overlaps(mini,camera),"La minicarte ne couvre pas les commandes de caméra");
   assert(!overlaps(mini,stick),"La minicarte ne couvre pas le joystick");
   assert(mini.x>=0&&mini.y>=0&&mini.x+mini.width<=width&&mini.y+mini.height<=height,"Minicarte dans l’écran");
   assert(await page.locator("#hud-minimap .mini-terrain").count()>0,"Terrain présent");
   assert.equal(await page.locator("#hud-minimap .hud-mini-route").count(),0,"Les points reliés sont supprimés");
   assert(await page.locator("#combat-player-panel .vitals-meta").innerText(),"Niveau et classe du joueur présents");
   assert(await page.locator("#mob-cards .vitals-meta").first().innerText(),"Niveau et rang ennemis présents");
   const colors=await page.locator("#mob-cards .vitals-row progress").evaluateAll(nodes=>nodes.slice(0,2).map(n=>getComputedStyle(n).accentColor));
   if(colors.length===2)assert.notEqual(colors[0],colors[1],"PV et énergie ennemis ont des couleurs distinctes");
   await page.screenshot({path:path.join(output,`combat-${width}x${height}.png`)});
   await page.locator("#minimap-toggle").click();
   await page.waitForFunction(before=>document.getElementById("hud-navigation").getBoundingClientRect().width>before+30,mini.width);
   const expanded=await box("hud-navigation");
   assert(expanded.width>mini.width+30,"La minicarte peut être agrandie : "+JSON.stringify(await page.locator("#hud-navigation").evaluate(el=>({classes:el.className,width:getComputedStyle(el).width,button:document.getElementById("minimap-toggle").outerHTML})))+JSON.stringify({mini,expanded}));
   assert.equal(await page.locator("#minimap-toggle").getAttribute("aria-expanded"),"true");
   await page.screenshot({path:path.join(output,`overview-${width}x${height}.png`)});
   await page.locator("#minimap-toggle").click();
   await page.waitForFunction(before=>Math.abs(document.getElementById("hud-navigation").getBoundingClientRect().width-before)<2,mini.width);
   const position=await page.evaluate(()=>[...session.tutorial.battle.players[session.me].position]);
   const settings=await box("game-menu-toggle");
   assert(Math.abs(width-settings.x-settings.width)<=12,"Les paramètres sont alignés à droite");
   const enemiesToggle=await box("mob-list-toggle");
   assert(enemiesToggle.x>width/2,"Le bouton cheval est à droite");
   assert(!overlaps(enemiesToggle,settings),"Les boutons cheval et paramètres sont distincts");
   assert(!overlaps(enemiesToggle,await box("combat-enemy-panel")),"Le cheval ne couvre pas les PV ennemis");
   await page.locator("#mob-list-toggle").click();
   assert.equal(await page.locator("#combat-enemy-panel").isVisible(),false,"Le cheval masque la liste des ennemis");
   await page.locator("#mob-list-toggle").click();
   assert(await page.locator("#combat-enemy-panel").isVisible(),"Le cheval réaffiche les PV ennemis");
   const exits=page.locator("#minimap-exits button");
   if(await exits.count()&&await exits.first().isVisible()) {
    await exits.first().click();
    assert.equal(await page.evaluate(()=>fieldCamera.follow),false,"Une sortie recentre la caméra");
    assert.deepEqual(await page.evaluate(()=>session.tutorial.battle.players[session.me].position),position,"Inspecter ne déplace pas le personnage");
    await page.locator("#hud-minimap").focus();await page.keyboard.press("Enter");
    assert.equal(await page.evaluate(()=>fieldCamera.follow),true,"Entrée reprend le suivi du joueur");
   }
   for(const view of ["stats","equipment","inventory","quest","map","bestiary","achievements","social","options"]) {
    if(await page.locator("#game-menu-items").evaluate(el=>el.hidden))await page.locator("#game-menu-toggle").click();
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    const launcher=await box("game-menu-items");
    assert(launcher.width<=280&&launcher.height<=height*.65+2,"La liste de l’engrenage reste compacte et défilante");
    assert(Math.abs(width-launcher.x-launcher.width-12)<2&&launcher.y>=60,"La liste reste près de l’engrenage");
    assert(await page.locator("#combat-player-panel").isVisible(),"Le HUD reste visible pendant le choix d’une option");
    const enemyPanel=await box("combat-enemy-panel");
    assert(!overlaps(launcher,enemyPanel),`La liste de l’engrenage ne recouvre pas les PV ennemis : ${JSON.stringify({launcher,enemyPanel})}`);
    if(view==="stats")await page.screenshot({path:path.join(output,`launcher-${width}x${height}.png`)});
    await page.locator("#show-"+view).click();
    const content=page.locator(view==="map"?"#region-view":"#"+view+"-view");
    assert(await content.isVisible(),`Menu ${view} accessible`);
    for(const id of ["combat-player-panel","combat-enemy-panel","combat-action-panel","hud-navigation","zone-banner","game-menu-toggle","mob-list-toggle","chat-toggle","touch-controls"])assert(!await page.locator("#"+id).isVisible(),`HUD ${id} masqué dans ${view}`);
    const back=await box("back-view");
    assert(back&&back.x>=0&&back.y>=0&&back.x+back.width<=width,"Retour accessible");
    assert(await page.locator("#back-view").evaluate(el=>el.scrollWidth<=el.clientWidth+1),"Le texte de retour tient dans le bouton");
    const frame=await page.locator(".adventure-grid").boundingBox();
    assert(Math.abs(frame.width-width*.75)<2&&Math.abs(frame.height-height*.75)<2,`Menu ${view} à 75 % de l’écran`);
    assert(Math.abs(frame.x+frame.width/2-width/2)<2&&Math.abs(frame.y+frame.height/2-height/2)<2,`Menu ${view} centré horizontalement et verticalement`);
    assert(!overlaps(frame,back),"Le bouton Retour reste en dehors du contenu du menu");
    assert(await page.locator(".adventure-grid").evaluate(el=>el.scrollWidth<=el.clientWidth+1),`Menu ${view} sans débordement horizontal`);
    if(view==="quest") {
     const cards=await page.locator("#quest-list .quest-card").evaluateAll(nodes=>nodes.map(node=>{const box=node.getBoundingClientRect();return {x:box.x,y:box.y,height:box.height};}));
     if(width>=1280&&cards.length>1) {
      assert(Math.abs(cards[0].y-cards[1].y)<2&&cards[1].x>cards[0].x,"Les fiches se répartissent côte à côte sur grand écran");
      assert(cards[0].height<180,"Une fiche simple reste compacte");
      assert(cards[0].y-frame.y<230,"Le journal commence en haut du panneau, sans espace artificiel");
     }
     const follow=page.locator("#quest-list [data-track-quest]");
     if(await follow.count()>1) {
      const id=await follow.nth(1).getAttribute("data-track-quest");
      await follow.nth(1).click();
      assert.equal(await page.evaluate(()=>activeHudQuest(session.tutorial).id),id,"La seconde quête peut être suivie");
      assert.equal(await page.locator(`[data-track-quest="${id}"]`).getAttribute("aria-pressed"),"true");
     }
    }
    if(["stats","quest","options"].includes(view))await page.screenshot({path:path.join(output,`${view}-${width}x${height}.png`)});
    await page.locator("#back-view").click();
    assert(await page.locator("#combat-player-panel").isVisible(),"Le HUD réapparaît à la fermeture du panneau");
    assert(await page.locator("#game-menu-toggle").isVisible(),"L’engrenage réapparaît à la fermeture du panneau");
   }
   await page.evaluate(()=>{session.tutorial.battle=null;session.tutorial.field_map=null;renderGame(session.tutorial);});
   for(const view of ["options","quest","map"]) {
    if(await page.locator("#back-view").isVisible())await page.locator("#back-view").click();
    await page.locator("#game-menu-toggle").click();await page.locator("#show-"+view).click();
    const frame=await page.locator(".adventure-grid").boundingBox();
    assert(Math.abs(frame.width-width*.75)<2&&Math.abs(frame.height-height*.75)<2,`Menu ${view} à 75 % sur la carte globale`);
    assert(Math.abs(frame.x+frame.width/2-width/2)<2&&Math.abs(frame.y+frame.height/2-height/2)<2,`Menu ${view} centré sur la carte globale : ${JSON.stringify(frame)}`);
    await page.locator("#back-view").click();
   }
   await page.addScriptTag({content:require("../.ui-test/node_modules/axe-core").source});
   const violations=await page.evaluate(async()=>{const report=await axe.run(document,{runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21aa"]}});return report.violations.map(v=>({id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)}));});
   assert.deepEqual(violations,[],"Pas de violation d’accessibilité automatisée : "+JSON.stringify(violations));
   assert.deepEqual(errors,[]);
   console.log(`Navigation, HUD et neuf menus vérifiés : ${width} × ${height}.`);
   await page.close();
  }
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
