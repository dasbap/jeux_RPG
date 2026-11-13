"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {chromium}=require("../.ui-test/node_modules/playwright");
const web=path.join(__dirname,"../jeuxRPG/multiplayer/web");
const fixture=JSON.parse(fs.readFileSync(process.argv[2],"utf8")).combat;
const files=["map_artwork.js","mobile_controls.js",...require("./client_source.cjs").files];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RPG_BROWSER_EXECUTABLE});
 try {
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("console",message=>{if(message.type()==="error"&&message.text().includes("Content Security Policy"))errors.push(message.text());});
  await page.route("http://ui.test/**",route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   const allowed=files.includes(name)||name==="style.css";
   const body=allowed?fs.readFileSync(path.join(web,name),"utf8"):fs.readFileSync(path.join(web,"index.html"),"utf8").replace(/<script[^>]*>.*?<\/script>/gs,"");
   return route.fulfill({contentType:allowed?(name.endsWith(".css")?"text/css":"text/javascript"):"text/html",headers:{"Content-Security-Policy":"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'"},body});
  });
  await page.goto("http://ui.test/");
  await page.evaluate(()=>{fetch=()=>new Promise(()=>{});setInterval=()=>0;});
  for(const file of files)await page.addScriptTag({url:"http://ui.test/"+file});
  await page.evaluate(adventure=>{
   token="audit";session={id:"interface",state:"running",me:adventure.players[0].id,players:adventure.players,tutorial:adventure,events:[]};
   for(const id of ["registration","characters","lobby"])document.getElementById(id).hidden=true;
   for(const id of ["battle","tutorial-panel"])document.getElementById(id).hidden=false;
   refresh=async()=>{};scheduleRefresh=()=>{};renderGame(adventure);showView("options",{toggle:false});
  },fixture);
  const custom={menus:{width_percent:60,height_percent:55,position:"right"},quests:{card_min_width_px:450,padding_px:20,gap_px:18,compact:false},minimap:{width_px:300,height_px:190},theme:{accent_color:"#55cc88",panel_color:"#102a30",text_color:"#eeeeee",font_size_px:18},hud:{zone_banner_seconds:1}};
  await page.evaluate(value=>{session.tutorial.interface=value;renderGame(session.tutorial);},custom);
  const frame=await page.locator(".adventure-grid").boundingBox();
  assert(Math.abs(frame.width-1280*.6)<2&&Math.abs(frame.height-900*.55)<2);
  assert(Math.abs(1280-frame.x-frame.width-12)<2,"Position à droite issue du Builder");
  assert.equal(await page.locator(".adventure-grid").evaluate(el=>getComputedStyle(el).backgroundColor),"rgb(16, 42, 48)");
  assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).fontSize),"18px");
  assert(await page.evaluate(()=>document.body.classList.contains("ui-relaxed-quests")));
  await page.evaluate(()=>showView("quest",{toggle:false}));
  assert.equal(await page.locator("#quest-list").evaluate(el=>getComputedStyle(el).gap),"18px");
  assert.equal(await page.locator(".quest-card").first().evaluate(el=>getComputedStyle(el).paddingTop),"26px");
  assert.equal(await page.locator("#quest-list [data-track-quest]").first().evaluate(el=>getComputedStyle(el).backgroundColor),"rgb(85, 204, 136)");
  await page.evaluate(()=>{const observer=new MutationObserver(()=>{});observer.observe(document.documentElement,{attributes:true,attributeFilter:["style"]});for(let tick=0;tick<10;tick++)renderGame(session.tutorial);window.interfaceMutations=observer.takeRecords().length;observer.disconnect();});
  assert.equal(await page.evaluate(()=>window.interfaceMutations),0,"Les réglages inchangés ne modifient pas le style à chaque rafraîchissement");
  await page.evaluate(()=>{document.getElementById("zone-banner").dataset.zone="";renderGame(session.tutorial);});
  await page.waitForTimeout(1150);
  assert(!await page.locator("#zone-banner").isVisible(),"La durée du nom de zone suit le Builder");
  await page.screenshot({path:path.join(__dirname,"../.data/interface-custom.png")});
  await page.locator("#back-view").click();
  assert(Math.abs((await page.locator("#hud-navigation").boundingBox()).width-300)<2,"La largeur de la mini-carte suit le Builder");
  assert.equal(await page.locator("#hud-minimap").evaluate(el=>getComputedStyle(el).height),"190px");
  await page.evaluate(()=>showView("quest",{toggle:false}));
  await page.evaluate(()=>{delete session.tutorial.interface;renderGame(session.tutorial);});
  assert(Math.abs((await page.locator(".adventure-grid").boundingBox()).width-1280*.75)<2,"Les anciens projets retrouvent les valeurs par défaut");
  assert.deepEqual(errors,[]);
  console.log("Interface Builder : dimensions, position, couleurs, texte, quêtes, durée de zone et rafraîchissements vérifiés sous CSP stricte.");
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
