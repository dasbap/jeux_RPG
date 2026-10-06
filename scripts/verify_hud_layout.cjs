const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')).combat;
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const [width,height] of [[1440,900],[390,844],[844,390]]){
   const page=await browser.newPage({viewport:{width,height}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const html=fs.readFileSync(path.join(root,'multiplayer/web/index.html'),'utf8').replace(/<script[^>]*>.*?<\/script>/gs,'');
   await page.route('http://hud.test/**',route=>route.fulfill({contentType:route.request().url().endsWith('.css')?'text/css':'text/html',body:route.request().url().endsWith('.css')?fs.readFileSync(path.join(root,'multiplayer/web/style.css'),'utf8'):html}));
   await page.goto('http://hud.test/');
   await page.addStyleTag({content:fs.readFileSync(path.join(root,'multiplayer/web/style.css'),'utf8')});
   await page.evaluate(()=>{window.fetch=()=>new Promise(()=>{});window.setInterval=()=>0;});
   for(const file of ['map_artwork.js','mobile_controls.js','app.js']) await page.addScriptTag({content:fs.readFileSync(path.join(root,'multiplayer/web',file),'utf8')});
   await page.evaluate(adventure=>{
    window.eval(`token='fixture';session={id:'layout',me:'p0',tutorial:${JSON.stringify(adventure)},events:[]};document.getElementById('battle').hidden=false;document.getElementById('tutorial-panel').hidden=false;renderTutorial(session.tutorial);`);
   },fixture);
   const rect=async id=>page.locator('#'+id).boundingBox();
   const menu=await rect('character-menu'),vitals=await rect('combat-player-panel'),zone=await rect('zone-banner'),actions=await rect('skill-hud'),map=await rect('world-map');
   assert(menu&&vitals&&zone&&actions&&map,'HUD visible');
   assert(menu.x>width/2&&vitals.x<width/4,'Menus et PV aux bons coins');
   assert(actions.x+actions.width<=width+1&&actions.y+actions.height<=height+1,'Actions dans l’écran : '+JSON.stringify({width,height,actions}));
   assert(map.width>=width-20&&map.height>=height-20,'Carte plein écran');
   const overlaps=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
   assert(!overlaps(zone,menu)&&!overlaps(zone,vitals),'Zone lisible sans chevauchement');
   const button=page.locator('#skill-main-attack button');
   await button.focus();
   assert(await button.evaluate(node=>node===document.activeElement),'Attaque accessible au clavier');
   await button.hover();
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
   if(width<751){
    const stick=await rect('touch-stick');
    assert(stick&&stick.x<width/2&&stick.y>height/2,'Joystick à gauche');
    await page.locator('#chat-toggle').click();
    assert(await page.locator('#chat-panel').isVisible(),'Chat ouvrable');
   }
   await page.locator('#show-social').click();
   assert(await page.locator('#social-view').isVisible(),'Social consultable dans le HUD');
   await page.locator('#back-view').click();
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
