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
    await page.locator("#show-"+view).click();
    const content=page.locator(view==="map"?"#region-view":"#"+view+"-view");
    assert(await content.isVisible(),`Menu ${view} accessible`);
    const back=await box("back-view");
    assert(back&&back.x>=0&&back.y>=0&&back.x+back.width<=width,"Retour accessible");
    assert(!overlaps(back,await box("mob-list-toggle")),"Le bouton Retour ne couvre pas le cheval");
    assert(await page.locator("#back-view").evaluate(el=>el.scrollWidth<=el.clientWidth+1),"Le texte de retour tient dans le bouton");
    const frame=await page.locator(".adventure-grid").boundingBox();
    assert(Math.abs(width-frame.x-frame.width)<=12,"Le panneau du menu est ancré à droite");
    if(width>=1100)assert(frame.x>width/2,"Les informations du menu laissent le centre de l’écran libre");
    assert(!overlaps(frame,await box("combat-player-panel")),"Les menus ne couvrent pas le joueur");
    assert(!overlaps(frame,await box("combat-enemy-panel")),"Les menus ne couvrent pas les ennemis");
    if(view==="quest") {
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
