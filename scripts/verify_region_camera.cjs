"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {chromium}=require("../.ui-test/node_modules/playwright");
const root=path.resolve(__dirname,".."),web=path.join(root,"jeuxRPG/multiplayer/web");
const fixture=JSON.parse(fs.readFileSync(path.join(root,".data/ux-audit/fixtures.json"),"utf8")).combat;
const files=["map_artwork.js","mobile_controls.js",...require("./client_source.cjs").files];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RPG_BROWSER_EXECUTABLE});
 try{
  for(const [width,height] of [[1440,900],[390,844]]){
   const context=await browser.newContext({viewport:{width,height},hasTouch:true});
   const page=await context.newPage(),errors=[];
   page.on("pageerror",error=>errors.push(error.message));
   await page.route("http://camera.test/**",route=>{
    const name=new URL(route.request().url()).pathname.slice(1),allowed=files.includes(name)||name==="style.css";
    return route.fulfill({contentType:allowed?(name.endsWith(".css")?"text/css":"text/javascript"):"text/html",body:allowed?fs.readFileSync(path.join(web,name),"utf8"):fs.readFileSync(path.join(web,"index.html"),"utf8").replace(/<script[^>]*>.*?<\/script>/gs,"")});
   });
   await page.goto("http://camera.test/");
   await page.evaluate(()=>{fetch=()=>new Promise(()=>{});setInterval=()=>0;});
   for(const file of files)await page.addScriptTag({url:"http://camera.test/"+file});
   await page.evaluate(adventure=>{
    adventure.battle=null;adventure.field_map=null;adventure.mobs=[];adventure.mob=null;
    const place=adventure.world.places.find(place=>place.points.length>2);
    place.points[0].x=-180;place.points[0].y=-120;
    adventure.world.current=place.id;adventure.position=place.id;mapPlace=place.id;
    token="audit";gameMode="solo";session={id:"camera",state:"running",me:adventure.players[0].id,players:adventure.players,tutorial:adventure,events:[]};
    for(const id of ["registration","characters","lobby"])document.getElementById(id).hidden=true;
    for(const id of ["battle","tutorial-panel"])document.getElementById(id).hidden=false;
    refresh=async()=>{};scheduleRefresh=()=>{};window.sentTravel=0;tutorialCommand=()=>{window.sentTravel++;};
    renderGame(adventure);showView("map",{toggle:false});
   },structuredClone(fixture));
   const map=page.locator('#region-map > svg[data-map^="detail:"]');
   const box=()=>map.getAttribute("viewBox");
   const initial=await box();
   const fits=await map.evaluate(svg=>{
    const bounds=svg.viewBox.baseVal;
    return [...svg.querySelectorAll("circle")].every(circle=>{
     const x=+circle.getAttribute("cx"),y=+circle.getAttribute("cy");
     return x>=bounds.x&&y>=bounds.y&&x<=bounds.x+bounds.width&&y<=bounds.y+bounds.height;
    });
   });
   assert(fits,"Le cadrage initial inclut même les coordonnées négatives du Builder");
   const rect=await map.boundingBox(),x=rect.x+rect.width*.55,y=rect.y+rect.height*.55;
   await page.mouse.move(x,y);await page.mouse.down();
   await page.mouse.move(x-35,y-20,{steps:4});
   const during=await box();assert.notEqual(during,initial,"La carte se déplace sans zoom préalable");
   await page.evaluate(()=>{session.tutorial.world.cameraAuditTick=1;renderGame(session.tutorial);});
   assert.equal(await box(),during,"Le cadrage reste en place après rafraîchissement");
   await page.mouse.move(x-65,y-35,{steps:4});await page.mouse.up();
   assert.notEqual(await box(),during,"Le glisser continue malgré un rafraîchissement");
   assert.equal(await page.evaluate(()=>window.sentTravel),0,"Glisser n’ordonne aucun déplacement au personnage");
   await page.locator("#region-center").click();assert.equal(await box(),initial);
   await page.locator("#region-in").click();const zoomed=await box();assert.notEqual(zoomed,initial);
   await page.locator("#region-out").click();
   await page.locator("#region-center").click();assert.equal(await box(),initial);
   await map.focus();await page.keyboard.press("ArrowRight");assert.notEqual(await box(),initial);
   await page.keyboard.press("Home");assert.equal(await box(),initial);
   await page.mouse.move(x,y);await page.mouse.wheel(0,-100);assert.notEqual(await box(),initial);
   await page.locator("#region-center").click();
   // Actual touch events, rather than synthesized mouse events.
   const cdp=await context.newCDPSession(page);
   await cdp.send("Input.dispatchTouchEvent",{type:"touchStart",touchPoints:[{x,y}]});
   await cdp.send("Input.dispatchTouchEvent",{type:"touchMove",touchPoints:[{x:x-40,y:y-25}]});
   await cdp.send("Input.dispatchTouchEvent",{type:"touchEnd",touchPoints:[]});
   assert.notEqual(await box(),initial,"Le glisser fonctionne au doigt");
   await page.locator("#region-center").click();
   const point=map.locator("[data-point]").first(),pointRect=await point.locator("circle").boundingBox();
   await page.waitForTimeout(510);
   await page.mouse.move(pointRect.x+pointRect.width/2,pointRect.y+pointRect.height/2);
   await page.mouse.down();await page.mouse.move(pointRect.x+pointRect.width/2+45,pointRect.y+pointRect.height/2+20,{steps:5});await page.mouse.up();
   assert.equal(await point.getAttribute("aria-pressed"),null,"Glisser depuis un point ne le sélectionne pas");
   assert.equal(await page.evaluate(()=>window.sentTravel),0);
   await page.locator("#region-center").click();
   await page.waitForTimeout(510);await point.click();
   assert(await page.locator('#map-points button[aria-pressed="true"]').count(),"Un clic simple sélectionne toujours un point");
   await page.screenshot({path:path.join(root,`.data/region-camera-${width}.png`)});
   assert.deepEqual(errors,[]);
   console.log(`Carte du menu ${width}x${height} : glisser souris/doigt, zoom, clavier, recentrage et clics vérifiés.`);
   await context.close();
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
