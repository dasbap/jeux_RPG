"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("../.ui-test/node_modules/playwright");
const web = path.join(__dirname, "../jeuxRPG/multiplayer/web");
const fixtures = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.RPG_BROWSER_EXECUTABLE});
  try {
    const page = await browser.newPage({viewport:{width:1280, height:900}});
    const errors = [];page.on("pageerror", error => errors.push(error.message));
    const html = fs.readFileSync(path.join(web, "index.html"), "utf8").replace(/<script[^>]*>.*?<\/script>/gs, "");
    await page.route("http://hud.test/**", route => route.fulfill({contentType:route.request().url().endsWith(".css") ? "text/css" : "text/html", body:route.request().url().endsWith(".css") ? fs.readFileSync(path.join(web, "style.css"), "utf8") : html}));
    await page.goto("http://hud.test/");
    await page.evaluate(() => {window.fetch=()=>new Promise(()=>{});window.setInterval=()=>0;});
    for (const file of ["map_artwork.js", "mobile_controls.js", ...require("./client_source.cjs").files]) await page.addScriptTag({content:fs.readFileSync(path.join(web, file), "utf8")});
    await page.evaluate(adventure => {
      token="audit";gameMode="online";session={id:"controls",state:"running",revision:1,me:adventure.players[0].id,players:adventure.players,tutorial:adventure,events:[]};
      refresh=async()=>{};scheduleRefresh=()=>{};
      for (const id of ["registration", "characters", "lobby"]) document.getElementById(id).hidden=true;
      for (const id of ["battle", "tutorial-panel"]) document.getElementById(id).hidden=false;
      renderGame(adventure);
      window.tickControls=()=>{adventure.world.auditTick=(adventure.world.auditTick || 0)+1;renderGame(adventure);};
      window.fixtureAdventure=adventure;
    }, fixtures.combat);
    await page.emulateMedia({reducedMotion:"reduce"});
    assert(await page.locator("#zone-banner").isVisible(),"Le nom est visible à l’entrée");
    for(let tick=0;tick<13;tick++) {await page.waitForTimeout(250);await page.evaluate(()=>window.tickControls());}
    assert(!await page.locator("#zone-banner").isVisible(),"Le nom disparaît après trois secondes malgré les rafraîchissements et les animations réduites");
    await page.evaluate(()=>{fixtureAdventure.encounter_number++;window.tickControls();});
    assert(!await page.locator("#zone-banner").isVisible(),"Une rencontre dans la même zone ne relance pas le bandeau");
    await page.evaluate(()=>{session.id="controls-new-entry";window.tickControls();});
    assert(await page.locator("#zone-banner").isVisible(),"Une nouvelle entrée affiche le nom");
    async function stablePopup(id) {
      const select=page.locator("#"+id);
      await select.click();
      await page.waitForFunction(id=>document.getElementById(id).matches(":open"),id);
      await page.evaluate(()=>{for(let tick=0;tick<10;tick++)window.tickControls();});
      await page.waitForTimeout(100);
      assert(await select.evaluate(node=>node.matches(":open")),`${id} reste ouvert après dix mises à jour`);
      await page.keyboard.press("Escape");
    }
    await page.evaluate(()=>showView("map",{toggle:false}));
    assert(await page.locator("#region-map .route-name text").count()>0,"Les chemins portent leurs noms");
    assert.equal(await page.locator("#region-map .route-badge").count(),0,"Aucun repère numéroté");
    assert.equal(await page.locator("#region-map .world-route-legend").count(),0,"Aucune légende numérotée");
    const routeBoxes=await page.locator("#region-map .route-name").evaluateAll(nodes=>nodes.map(node=>{
      const rect=node.querySelector("rect").getBBox(),text=node.querySelector("text").getBBox();
      return {fits:text.x>=rect.x-1&&text.y>=rect.y-1&&text.x+text.width<=rect.x+rect.width+1&&text.y+text.height<=rect.y+rect.height+1};
    }));
    assert(routeBoxes.every(box=>box.fits),"Les noms tiennent dans leurs étiquettes");
    await page.locator('#region-map > svg[data-map="general"]').screenshot({path:path.join(__dirname,"../.data/world-route-names.png")});
    await stablePopup("map-place");
    await page.evaluate(()=>{document.getElementById("map-details").open=false;window.tickControls();});
    assert(!await page.locator("#map-details").evaluate(node=>node.open),"Les détails fermés par le joueur restent fermés");
    await page.evaluate(()=>{
      window.savedField={battle:session.tutorial.battle,field_map:session.tutorial.field_map};
      session.tutorial.battle=null;session.tutorial.field_map=null;window.tickControls();
    });
    assert.equal(await page.locator('#world-map > svg[data-map="general"]').count(),1,"Carte globale principale disponible");
    assert.equal(await page.locator('#region-map > svg[data-map="general"]').count(),0,"La carte globale n’est pas répétée dans le panneau");
    await page.evaluate(()=>{document.getElementById("map-details").open=true;});
    assert(await page.locator("#map-place").isVisible(),"Le choix de destination reste disponible");
    await page.evaluate(()=>{Object.assign(session.tutorial,window.savedField);window.tickControls();showView("map",{toggle:false});});
    assert.equal(await page.locator('#region-map > svg[data-map="general"]').count(),1,"La carte régionale reste disponible pendant l’exploration à pied");
    await page.evaluate(()=>showView("bestiary",{toggle:false}));
    await stablePopup("bestiary-map");
    await stablePopup("bestiary-sort");
    await page.locator("#bestiary-search").fill("gobelin");
    await page.locator("#bestiary-search").evaluate(node=>node.setSelectionRange(2,5));
    await page.evaluate(()=>{for(let tick=0;tick<10;tick++)window.tickControls();});
    assert.deepEqual(await page.locator("#bestiary-search").evaluate(node=>[node.value,node.selectionStart,node.selectionEnd,document.activeElement===node]),["gobelin",2,5,true]);
    await page.evaluate(()=>{
      session.tutorial.battle=null;
      socialState={friends:[],requests:[],invitations:[],rallies:[],team:{members:[]}};
      presenceState={realm:1,realms:2,online:1,capacity:20,nearby:[]};
      showView("social",{toggle:false});
      window.tickControls=()=>{busy=!busy;renderSocial();renderChat({online:[],global:[],group:[]});};
    });
    await page.locator("#rally-destination").selectOption({index:1});
    const rallyDestination=await page.locator("#rally-destination").inputValue();
    await stablePopup("rally-destination");
    assert.equal(await page.locator("#rally-destination").inputValue(),rallyDestination);
    for(const id of ["social-name","guild-name"]) {
      await page.locator("#"+id).evaluate(node=>{node.value="Texte en cours";node.focus();node.setSelectionRange(3,7);});
      await page.evaluate(()=>{for(let tick=0;tick<10;tick++)window.tickControls();renderChat({online:[],global:[],group:[]});});
      assert.deepEqual(await page.locator("#"+id).evaluate(node=>[node.value,node.selectionStart,node.selectionEnd,document.activeElement===node]),["Texte en cours",3,7,true],id);
    }
    await page.locator("#back-view").click();
    await page.evaluate(()=>{document.getElementById("chat-panel").hidden=false;document.body.classList.add("chat-open");});
    await page.locator("#chat-message").evaluate(node=>{node.value="Texte en cours";node.focus();node.setSelectionRange(3,7);});
    await page.evaluate(()=>{for(let tick=0;tick<10;tick++)window.tickControls();});
    assert.deepEqual(await page.locator("#chat-message").evaluate(node=>[node.value,node.selectionStart,node.selectionEnd,document.activeElement===node]),["Texte en cours",3,7,true]);
    await stablePopup("chat-channel");
    await page.evaluate(()=>{
      document.body.classList.remove("combat-active","hud-menu-open");
      session={id:"duel",state:"running",revision:1,me:"a",players:[{id:"a",name:"Vous",class_name:"Knight",hp:25,max_hp:25,cooldown_real_seconds:0},{id:"b",name:"Adversaire B",class_name:"Knight",hp:25,max_hp:25},{id:"c",name:"Adversaire C",class_name:"Knight",hp:25,max_hp:25}],events:[]};
      presenceState={pvp:true};
      const state={player:session.players[0]};
      render(state);
      window.tickControls=()=>{session.revision++;session.players[0].cooldown_real_seconds=session.revision%2 ? 0.5 : 0;render(state);};
    });
    await page.locator("#duel-target").selectOption("c");
    await stablePopup("duel-target");
    assert.equal(await page.locator("#duel-target").inputValue(),"c");
    await page.evaluate(()=>{session.players.pop();window.tickControls();});
    assert.equal(await page.locator("#duel-target").inputValue(),"b","Une cible disparue est remplacée par une cible valide");
    const fallback=await page.evaluate(()=>{
      const select=document.createElement("select");
      syncSelectOptions(select,[["a","Premier"],["b","Second"]]);select.value="b";
      syncSelectOptions(select,[["a","Premier renommé"],["b","Second"]]);
      const preserved=select.value;syncSelectOptions(select,[["a","Premier renommé"]]);
      return [preserved,select.value,select.options[0].textContent];
    });
    assert.deepEqual(fallback,["b","a","Premier renommé"]);
    if(process.argv[3]) {
      const forgeFixture=JSON.parse(fs.readFileSync(process.argv[3],"utf8")).unlocked;
      await page.evaluate(adventure=>{
        busy=false;session={id:"forge-audit",me:adventure.players[0].id,tutorial:adventure,events:[]};
        document.getElementById("chat-panel").hidden=true;document.body.classList.remove("chat-open");
        window.tickControls=()=>renderGame(session.tutorial);
        document.getElementById("tutorial-panel").hidden=false;
        renderGame(adventure);document.getElementById("craft-view").showModal();
        window.forgeAuditButton=document.querySelector("#forge-catalogue [data-action]");
        window.forgeAuditButton.focus();
        for(let tick=0;tick<10;tick++)renderGame(adventure);
      },forgeFixture);
      assert(await page.evaluate(()=>window.forgeAuditButton===document.querySelector("#forge-catalogue [data-action]")&&document.activeElement===window.forgeAuditButton),"La forge conserve ses boutons et le focus pendant les actualisations");
      await page.evaluate(()=>{
        document.getElementById("craft-view").close();
        showView("quest",{toggle:false});
      });
      await stablePopup("quest-category");
      await stablePopup("quest-type");
      await page.screenshot({path:path.join(__dirname,"../.data/quest-type-journal-desktop.png")});
      await page.setViewportSize({width:390,height:844});
      assert(await page.locator("#quest-type").isVisible(),"Le second filtre est visible sur petit écran");
      const categoryBox=await page.locator("#quest-category").boundingBox(),typeBox=await page.locator("#quest-type").boundingBox();
      assert(categoryBox.x+categoryBox.width<=typeBox.x,"La catégorie est à gauche du type, sans chevauchement");
      assert(Math.abs(categoryBox.y-typeBox.y)<2,"Les deux filtres restent sur la même ligne sur petit écran");
      await page.screenshot({path:path.join(__dirname,"../.data/quest-type-journal-mobile.png")});
      await page.setViewportSize({width:1280,height:900});
      await page.locator("#quest-actions button").focus();
      await page.evaluate(()=>{
        const button=document.querySelector("#quest-actions button");button.focus();
        const initiallyFocused=document.activeElement===button;
        for(let tick=0;tick<10;tick++)renderGame(session.tutorial);
        window.questActionStable={same:button===document.querySelector("#quest-actions button"),focused:document.activeElement===button,initiallyFocused};
      });
      assert.deepEqual(await page.evaluate(()=>window.questActionStable),{same:true,focused:true,initiallyFocused:true},"Le bouton de localisation reste stable");
    }
    assert.deepEqual(errors,[]);
    console.log("Navigateur : six listes stables, choix conservés, disparition des cibles, saisies et fermeture des détails vérifiés.");
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
