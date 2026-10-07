const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const webAppSource=require('./web_app_source.cjs');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')).combat;
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const [width,height] of [[1440,900],[390,844],[844,390]]){
   const mobile=width<751||height<500;
   const page=await browser.newPage({viewport:{width,height},isMobile:mobile,hasTouch:mobile});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const html=fs.readFileSync(path.join(root,'jeuxRPG/multiplayer/web/index.html'),'utf8').replace(/<script[^>]*>.*?<\/script>/gs,'');
   await page.route('http://hud.test/**',route=>route.fulfill({contentType:route.request().url().endsWith('.css')?'text/css':'text/html',body:route.request().url().endsWith('.css')?fs.readFileSync(path.join(root,'jeuxRPG/multiplayer/web/style.css'),'utf8'):html}));
   await page.goto('http://hud.test/');
   await page.addStyleTag({content:fs.readFileSync(path.join(root,'jeuxRPG/multiplayer/web/style.css'),'utf8')});
   await page.evaluate(()=>{window.fetch=()=>new Promise(()=>{});window.setInterval=()=>0;});
   for(const file of ['map_artwork.js','mobile_controls.js']) await page.addScriptTag({content:fs.readFileSync(path.join(root,'jeuxRPG/multiplayer/web',file),'utf8')});
   await page.addScriptTag({content:webAppSource(root)});
   await page.evaluate(adventure=>{
    window.eval(`token='fixture';session={id:'layout',me:'p0',tutorial:${JSON.stringify(adventure)},events:[]};document.getElementById('battle').hidden=false;document.getElementById('tutorial-panel').hidden=false;renderTutorial(session.tutorial);`);
   },fixture);
   const rect=async id=>page.locator('#'+id).boundingBox();
   const menu=await rect('character-menu'),vitals=await rect('combat-player-panel'),zone=await rect('zone-banner'),actions=await rect('skill-hud'),map=await rect('world-map');
   assert(menu&&vitals&&zone&&actions&&map,'HUD visible');
   assert(await page.locator('#combat-enemy-panel').isVisible(),'Raccourcis des monstres visibles sur ordinateur et mobile');
   assert(!(await page.locator('#chat-panel').isVisible()),'Chat replié par défaut');
   await page.locator('#chat-toggle').click();
   assert(await page.locator('#chat-panel').isVisible(),'Icône de chat utilisable sur tous les écrans');
   await page.locator('#chat-toggle').click();
   await page.evaluate(()=>window.eval("renderVitals('character-vitals',[{id:'energy-test',name:'Couleurs',hp:5,max_hp:10,energies:[{type:'Mana',current:5,max:10},{type:'Aura',current:5,max:10},{type:'Foie',current:5,max:10}]}]);"));
   const energyColors=await page.locator('#character-vitals .vitals-energy').evaluateAll(nodes=>nodes.map(node=>getComputedStyle(node).accentColor));
   assert.deepEqual(energyColors,['rgb(52, 120, 246)','rgb(115, 207, 245)','rgb(247, 211, 95)'],'Mana bleu, aura bleu ciel et foi jaune');

   assert(menu.x>width/2&&vitals.x<width/4,'Menus et PV aux bons coins');
   assert(actions.x+actions.width<=width+1&&actions.y+actions.height<=height+1,'Actions dans l’écran : '+JSON.stringify({width,height,actions}));
   assert(map.width>=width-20&&map.height>=height-20,'Carte plein écran');
   const overlaps=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
   assert(!overlaps(zone,menu)&&!overlaps(zone,vitals),'Zone lisible sans chevauchement');
   assert.equal(await page.locator('#field-left,#field-up,#field-down,#field-right').count(),0,'Flèches de caméra retirées');
   await page.locator('#mob-list-toggle').click();
   assert(!(await page.locator('#combat-enemy-panel').isVisible()),'Liste entièrement repliable');
   await page.evaluate(()=>window.eval('renderTutorial(session.tutorial);'));
   assert(!(await page.locator('#combat-enemy-panel').isVisible()),'Liste reste repliée après mise à jour');
   await page.locator('#mob-list-toggle').click();
   assert(await page.locator('#combat-enemy-panel').isVisible(),'Liste réouvrable hors menu');
   await page.evaluate(()=>window.eval('window.cameraRequests=0;window.savedTutorialCommand=tutorialCommand;tutorialCommand=()=>{window.cameraRequests++;};'));
   const dragX=width*.45,dragY=height*.5;
   if(mobile){
    const cdp=await page.context().newCDPSession(page);
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:dragX,y:dragY}]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:dragX-60,y:dragY+30}]});
    assert.equal(await page.evaluate(()=>window.eval('fieldCamera.follow')),false,'Caméra tactile libre pendant le glissement');
    await page.evaluate(()=>window.eval('renderTutorial(session.tutorial);'));
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await cdp.detach();
   }else{
    await page.mouse.move(dragX,dragY);await page.mouse.down();
    await page.mouse.move(dragX-60,dragY+30,{steps:4});
    assert.equal(await page.evaluate(()=>window.eval('fieldCamera.follow')),false,'Caméra libre pendant le clic maintenu');
    await page.evaluate(()=>window.eval('renderTutorial(session.tutorial);'));
    await page.mouse.up();
   }
   await page.waitForTimeout(1000);
   assert.equal(await page.evaluate(()=>window.eval('fieldCamera.follow')),false,'Attente avant retour au suivi');
   await page.dispatchEvent('#world-map','pointerdown',{pointerId:42,isPrimary:true,button:0,clientX:dragX,clientY:dragY});
   await page.dispatchEvent('#world-map','pointerup',{pointerId:42,isPrimary:true,button:0,clientX:dragX,clientY:dragY});
   await page.waitForTimeout(1150);
   assert.equal(await page.evaluate(()=>window.eval('fieldCamera.follow')),true,'Suivi repris après deux secondes');
   assert.equal(await page.evaluate(()=>window.cameraRequests),0,'Glissement sans déplacement ni requête serveur');
   await page.evaluate(()=>window.eval('tutorialCommand=window.savedTutorialCommand;'));
   const button=page.locator('#skill-main-attack button');
   await button.focus();
   assert(await button.evaluate(node=>node===document.activeElement),'Attaque accessible au clavier');
   await page.mouse.move(1,1);
   assert(await page.locator('#skill-offense').isVisible(),'Compétence rapide visible sans maintien');
   await button.hover();
   await page.waitForTimeout(200);
   const attackBefore=await button.boundingBox();
   await page.evaluate(()=>{
    document.getElementById('message').textContent='Aucune cible à portée pour l’attaque. Message sur plusieurs lignes pour vérifier la stabilité.';
    for(const id of ['corpse-actions','tactical-actions']){
     const extra=document.createElement('button');extra.dataset.layoutFixture='true';extra.textContent=id==='corpse-actions'?'Dépecer':'Se cacher';document.getElementById(id).append(extra);
    }
   });
   assert.deepEqual(await button.boundingBox(),attackBefore,'Messages et actions contextuelles ne déplacent pas l’attaque');
   const favorite=page.locator('#skill-offense button');
   if(await favorite.count()){
    await favorite.evaluate(node=>{node.hudShortAction=()=>{window.slideSkillUsed=(window.slideSkillUsed||0)+1;};});
    const target=await favorite.boundingBox();
    await page.mouse.move(attackBefore.x+attackBefore.width/2,attackBefore.y+attackBefore.height/2);
    await page.mouse.down();
    await page.waitForTimeout(450);
    await page.mouse.move(target.x+target.width/2,target.y+target.height/2);
    await page.mouse.up();
    assert.equal(await page.evaluate(()=>window.slideSkillUsed),1,'Maintenir l’attaque puis glisser active la compétence au relâchement');
    assert.equal(await page.evaluate(()=>Boolean(document.getElementById('skill-hud').hudGesture)),false,'Geste terminé');
   }
   await page.evaluate(()=>{document.getElementById('message').textContent='';document.querySelectorAll('[data-layout-fixture]').forEach(node=>node.remove());});
   await page.evaluate(()=>{
    window.eval("const arcActor=session.tutorial.players.find(p=>p.id===session.me);const arcSkill=arcActor.skills.find(s=>skillCategory(s)==='offense');if(arcSkill){arcActor.skills.push({...arcSkill,name:'Arc test 2'},{...arcSkill,name:'Arc test 3'});}renderTutorial(session.tutorial);");
   });
   await page.mouse.move(1,1);
   await page.locator('#skill-offense button').evaluate(node=>node.hudLongAction());
   const arc=await page.locator('#skill-popover button').evaluateAll(nodes=>nodes.map(node=>{const r=node.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};}));
   const anchor=await page.locator('#skill-offense button').boundingBox();
   assert(arc.length>=3,'Sous-compétences disponibles en arc');
   for(const point of arc){assert(Math.abs(Math.hypot(point.x-anchor.x-anchor.width/2,point.y-anchor.y-anchor.height/2)-(width<751?126:156))<2,'Arc centré sur la compétence correspondante');assert(point.x>=0&&point.x<=width&&point.y>=0&&point.y<=height,'Sous-compétence dans l’écran');}
   const quickNames=await page.locator('.mob-quick-actions button').evaluateAll(nodes=>nodes.map(node=>node.dataset.quickSkill));
   const favorites=await page.locator('.skill-favorite').evaluateAll(nodes=>nodes.map(node=>node.dataset.skill));
   assert(quickNames.every(name=>favorites.includes(name)),'Les monstres proposent uniquement les compétences rapides désignées');
   assert.equal(await page.locator('.battle-map').getAttribute('clip-path'),'inset(0)','Découpe sur le viewport entier sans couper une partie du terrain');
   await page.mouse.move(1,1);
   await page.evaluate(()=>window.eval("session.tutorial.battle.corpses=[{id:'layout-corpse',name:'Corps test',position:[...session.tutorial.battle.players[session.me].position],harvested:[]}];renderTutorial(session.tutorial);"));
   const harvest=page.locator('#corpse-actions button');
   assert.equal(await harvest.getAttribute('aria-label'),'Dépecer Corps test','Dépeçage accessible avec une icône compacte');
   const harvestBox=await harvest.boundingBox();
   assert(harvestBox&&harvestBox.y>height/2&&!overlaps(harvestBox,menu)&&!overlaps(harvestBox,await button.boundingBox()),'Dépeçage près du combat sans collision avec les paramètres ou l’attaque');

   if(mobile){
    const stick=await rect('touch-stick');
    assert(stick&&stick.x<width/2&&stick.y>height/2,'Joystick à gauche');
    assert(!overlaps(stick,await rect('chat-toggle')),'Joystick sans collision avec le chat');
    assert((await rect('combat-enemy-panel')).height<=Math.min(140,height*.25)+2,'Liste des monstres compacte');
    await page.locator('#chat-toggle').click();
    assert(await page.locator('#chat-panel').isVisible(),'Chat ouvrable');
    await page.locator('#chat-toggle').click();
   }
   await page.locator('#game-menu-toggle').click();
   await page.locator('#show-social').click();
   assert(await page.locator('#social-view').isVisible(),'Social consultable dans le HUD');
   await page.locator('#back-view').click();
   await page.keyboard.press('Escape');
   await page.locator('#show-inventory').click();
   assert(await page.locator('#inventory-view').isVisible(),'Inventaire consultable en combat');
   await page.locator('#back-view').click();
   assert(!(await page.locator('#inventory-view').isVisible()),'Retour au jeu');
   assert.deepEqual(errors,[]);
   fs.mkdirSync(path.join(root,'hud-captures'),{recursive:true});
   await page.screenshot({path:path.join(root,`hud-captures/${width}x${height}.png`)});
   await page.close();
  }
  console.log('HUD vérifié dans Chromium : ordinateur, mobile portrait et paysage.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
