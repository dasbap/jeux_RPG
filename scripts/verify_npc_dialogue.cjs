"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {chromium}=require("../.ui-test/node_modules/playwright");
const root=path.resolve(__dirname,".."),web=path.join(root,"jeuxRPG/multiplayer/web");
const fixture=JSON.parse(fs.readFileSync(path.join(root,".data/ux-audit/fixtures.json"),"utf8")).combat;
const files=["map_artwork.js","mobile_controls.js",...require("./client_source.cjs").files];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RPG_BROWSER_EXECUTABLE});
 try{
  for(const [width,height] of [[1440,900],[1280,720],[390,844],[844,390]]){
   const page=await browser.newPage({viewport:{width,height}}),errors=[];
   page.on("pageerror",error=>errors.push(error.message));
   await page.route("http://npc.test/**",route=>{
    const name=new URL(route.request().url()).pathname.slice(1),allowed=files.includes(name)||name==="style.css";
    return route.fulfill({contentType:allowed?(name.endsWith(".css")?"text/css":"text/javascript"):"text/html",body:allowed?fs.readFileSync(path.join(web,name),"utf8"):fs.readFileSync(path.join(web,"index.html"),"utf8").replace(/<script[^>]*>.*?<\/script>/gs,"")});
   });
   await page.goto("http://npc.test/");
   await page.evaluate(()=>{fetch=()=>new Promise(()=>{});setInterval=()=>0;});
   for(const file of files)await page.addScriptTag({url:"http://npc.test/"+file});
   await page.evaluate(adventure=>{
    const name="Mira · responsable des patrouilles";
    window.greeting="Les voyageurs arrivent sans leurs outils, les gardes rentrent sans sommeil, et chacun me demande quand cela va finir. Tu cherches du travail ou simplement une route ?";
    adventure.field_interactions=[{id:"mira",name,dialogue:window.greeting}];
    adventure.narrative={notes:[],greetings:{mira:window.greeting},conversation:null};
    token="npc";gameMode="solo";session={id:"npc",state:"running",me:adventure.players[0].id,players:adventure.players,tutorial:adventure,events:[]};
    for(const id of ["registration","characters","lobby"])document.getElementById(id).hidden=true;
    for(const id of ["battle","tutorial-panel"])document.getElementById(id).hidden=false;
    refresh=async()=>{};scheduleRefresh=()=>{};
    tutorialCommand=(action,params)=>{
     if(action==="talk"){
      window.talkedTo=params.npc;
      adventure.narrative.conversation={npc:"mira",name,text:window.greeting.repeat(12),topics:[],choices:[],quests:[],service:null};
      renderGame(adventure);
     }
    };
    renderGame(adventure);
   },structuredClone(fixture));
   const panel=page.locator("#npc-view"),button=page.locator("#npc-actions button");
   assert(await panel.isVisible());
   const frame=await panel.boundingBox(),action=await button.boundingBox();
   assert(frame.x>=0&&frame.y>=0&&frame.x+frame.width<=width+1&&frame.y+frame.height<=height+1,"Le dialogue reste dans l’écran");
   assert(action.y>=frame.y&&action.y+action.height<=frame.y+frame.height,"Parler reste dans l’encadré");
   const overlap=await page.evaluate(()=>{
    const npc=document.getElementById("npc-view").getBoundingClientRect();
    return [...document.querySelectorAll("#skill-hud button,#touch-controls button")].some(button=>{
     const box=button.getBoundingClientRect();
     return box.width&&box.height&&box.left<npc.right&&box.right>npc.left&&box.top<npc.bottom&&box.bottom>npc.top;
    });
   });
   assert(!overlap,"Aucune commande de combat ne recouvre le dialogue");
   await page.evaluate(()=>{session.tutorial.narrative.greetings.mira=window.greeting.repeat(20);renderGame(session.tutorial);});
   const text=page.locator("#npc-dialogue");
   assert(await text.evaluate(node=>node.scrollHeight>node.clientHeight&&node.clientHeight>20),"Le long texte possède une zone de lecture défilable");
   await text.focus();await page.keyboard.press("End");
   await text.evaluate(node=>node.scrollTop=node.scrollHeight);
   const top=await text.evaluate(node=>node.scrollTop);
   await page.evaluate(()=>renderGame(session.tutorial));
   assert.equal(await text.evaluate(node=>node.scrollTop),top,"La lecture ne revient pas au début à chaque rafraîchissement");
   assert(await button.isVisible());
   await page.screenshot({path:path.join(root,`.data/npc-dialogue-${width}x${height}.png`)});
   await button.click();assert.equal(await page.evaluate(()=>window.talkedTo),"mira");
   assert(await page.locator("#story-dialog").evaluate(node=>node.open),"Parler ouvre le dialogue complet");
   const dialog=await page.locator("#story-dialog").boundingBox();
   assert(dialog.x>=0&&dialog.y>=0&&dialog.x+dialog.width<=width+1&&dialog.y+dialog.height<=height+1);
   assert.deepEqual(errors,[]);
   console.log(`Dialogue PNJ ${width}x${height} : texte défilable, commandes dégagées et conversation complète accessibles.`);
   await page.close();
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
