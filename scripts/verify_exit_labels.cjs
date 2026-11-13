"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {chromium}=require("../.ui-test/node_modules/playwright");
const root=path.resolve(__dirname,".."),web=path.join(root,"jeuxRPG/multiplayer/web");
const fixture=JSON.parse(fs.readFileSync(path.join(root,".data/ux-audit/fixtures.json"),"utf8")).combat;
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RPG_BROWSER_EXECUTABLE});
 try {
  for(const [width,height] of [[1440,900],[390,844],[844,390]]) {
   const page=await browser.newPage({viewport:{width,height},reducedMotion:"reduce"});
   const html=fs.readFileSync(path.join(web,"index.html"),"utf8").replace(/<script[^>]*>.*?<\/script>/gs,"");
   const policyErrors=[];page.on("console",message=>{if(message.type()==="error"&&message.text().includes("Content Security Policy"))policyErrors.push(message.text());});
   await page.route("http://hud.test/**",route=>route.fulfill({headers:{"Content-Security-Policy":"style-src 'self'"},contentType:route.request().url().endsWith(".css")?"text/css":"text/html",body:route.request().url().endsWith(".css")?fs.readFileSync(path.join(web,"style.css"),"utf8"):html}));
   await page.goto("http://hud.test/");
   await page.evaluate(()=>{window.fetch=()=>new Promise(()=>{});window.setInterval=()=>0;});
   for(const file of ["map_artwork.js","mobile_controls.js",...require("./client_source.cjs").files])await page.addScriptTag({content:fs.readFileSync(path.join(web,file),"utf8")});
   await page.evaluate(adventure=>{
    token="labels";gameMode="solo";session={id:"labels",state:"running",revision:1,me:"p0",tutorial:adventure,events:[]};
    for(const id of ["registration","characters","lobby"])document.getElementById(id).hidden=true;
    for(const id of ["battle","tutorial-panel"])document.getElementById(id).hidden=false;
    const map=adventure.battle.map;
    const rock=[Math.floor(map.width/2),Math.floor(map.height/2)];
    map.decorations=[...(map.decorations || []),{kind:"rock",position:rock}];
    adventure.battle.explored.push(rock);
    map.exits=[{position:[0,Math.floor(map.height/2)],name:"Retour vers le village de Rosée"},{position:[map.width-1,Math.floor(map.height/2)],name:"Prairies des Lucioles"},{position:[Math.floor(map.width/2),0],name:"Chemin vers la forêt des Éveillés"},{position:[Math.floor(map.width/2),map.height-1],name:"Entrée de la grotte des Oubliés"}];
    renderGame(adventure);
   },fixture);
   for(const span of [12,24,48]) {
    await page.evaluate(span=>{fieldCamera={map:session.tutorial.battle.map.id,span,x:session.tutorial.battle.map.width/2,y:session.tutorial.battle.map.height/2,follow:false};renderGame(session.tutorial);},span);
    const geometry=await page.locator(".exit-caption").evaluateAll(groups=>groups.map(group=>{
     const box=group.querySelector("rect").getBoundingClientRect(),svg=group.ownerSVGElement.getBoundingClientRect();
     return {x:box.x,y:box.y,right:box.right,bottom:box.bottom,view:{x:svg.x,y:svg.y,right:svg.right,bottom:svg.bottom},font:parseFloat(getComputedStyle(group.querySelector("text")).fontSize)*group.getScreenCTM().a,texts:[...group.querySelectorAll("tspan")].map(text=>{const r=text.getBoundingClientRect();return {text:text.textContent,left:r.left,right:r.right};})};
    }));
    assert.equal(geometry.length,4);
    for(const label of geometry) {
     assert(label.x>=label.view.x&&label.y>=label.view.y&&label.right<=label.view.right+1&&label.bottom<=label.view.bottom+1,"Libellé intégralement dans la caméra : "+JSON.stringify(label));
     assert(Math.abs(label.font-12)<.2,"Taille de texte lisible quel que soit le zoom");
     for(const line of label.texts)assert(line.left>=label.x&&line.right<=label.right+1,"Texte contenu dans son cartouche");
    }
    const occlusions=await page.evaluate(()=>{
     const panels=["zone-banner","combat-player-panel","combat-enemy-panel","hud-navigation","field-camera","game-menu-toggle","mob-list-toggle","touch-stick","skill-hud"].map(id=>document.getElementById(id)?.getBoundingClientRect()).filter(box=>box?.width>0&&box.height>0);
     return [...document.querySelectorAll(".exit-caption rect")].filter(node=>{const label=node.getBoundingClientRect();return panels.some(box=>label.left<box.right&&label.right>box.left&&label.top<box.bottom&&label.bottom>box.top);}).length;
    });
    assert.equal(occlusions,0,"Aucun nom masqué par l’interface");
   }
   assert.equal(await page.locator(".exit-caption:visible").count(),0,"Aucun nom affiché sans survol");
   const marker=page.locator(".exit-marker").nth(1);
   await marker.locator(":scope > circle").hover({force:true});
   await marker.locator(".exit-caption").waitFor({state:"visible",timeout:3000});
   await page.evaluate(()=>new Promise(requestAnimationFrame));
   assert(await marker.locator(".exit-caption").isVisible(),"Le nom apparaît au survol de l’icône : "+JSON.stringify(await marker.evaluate(node=>{const c=node.querySelector("circle").getBoundingClientRect();return {hover:node.matches(":hover"),caption:getComputedStyle(node.querySelector(".exit-caption")).visibility,hit:document.elementsFromPoint(c.x+c.width/2,c.y+c.height/2).map(e=>e.id||e.tagName)};})));
   assert.equal(await page.locator(".exit-caption:visible").count(),1,"Seul le nom survolé apparaît");
   const retainedMarker=await marker.elementHandle();
   for(let tick=0;tick<5;tick++) {
    await page.evaluate(()=>renderGame(session.tutorial,true));
    const layers=await page.locator("#world-map .battle-map").evaluate(svg=>{
     const children=[...svg.children];
     const scenery=children.filter(node=>node.matches(".terrain-decoration"));
     const markers=children.filter(node=>node.matches(".exit-marker"));
     return {decorations:scenery.length,above:markers.every(marker=>scenery.every(decor=>children.indexOf(decor)<children.indexOf(marker)))};
    });
    assert(layers.decorations>0,"Le test inclut un rocher visible");
    assert(layers.above,"Les passages et leurs noms restent au-dessus du décor après chaque rafraîchissement");
   }
   assert(await marker.evaluate((node,retained)=>node===retained,retainedMarker),"Le survol conserve le même repère");
   assert(await marker.locator(".exit-caption").isVisible(),"Le nom reste visible pendant les rafraîchissements");
   await page.mouse.move(width/2,height/2);
   await marker.locator(".exit-caption").waitFor({state:"hidden",timeout:3000});
   await page.evaluate(()=>new Promise(requestAnimationFrame));
   assert.equal(await page.locator(".exit-caption:visible").count(),0,"Le nom disparaît en quittant l’icône");
   await page.keyboard.press("Tab");await marker.focus();
   await marker.locator(".exit-caption").waitFor({state:"visible",timeout:3000});
   await page.evaluate(()=>new Promise(requestAnimationFrame));
   assert(await marker.locator(".exit-caption").isVisible(),"Le nom reste accessible au clavier : "+JSON.stringify(await marker.evaluate(node=>({focus:node.matches(":focus"),visible:node.matches(":focus-visible"),active:document.activeElement?.outerHTML.slice(0,150)}))));
   await page.screenshot({path:path.join(root,`.data/exit-labels-${width}x${height}.png`)});
   assert.deepEqual(policyErrors,[],"Rendu compatible avec la politique de styles du client Windows");
   console.log(`Passages lisibles aux quatre bords et à trois zooms : ${width} × ${height}.`);
   await page.close();
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
