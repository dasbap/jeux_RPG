"use strict";
const fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"..");
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,".data/browser-binaries");
const {chromium}=require("../.data/browser-tools/node_modules/playwright");
(async()=>{
  const content=JSON.parse(fs.readFileSync(path.join(root,"projects/authored/content.json"),"utf8")).content;
  const mobs=JSON.parse(fs.readFileSync(path.join(root,"projects/authored/mobs.json"),"utf8")).maps;
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1200,height:900},deviceScaleFactor:1});
    await page.route("**/*",route=>route.abort());
    await page.setContent('<style>body{background:#15212b;color:#ebecdf;font:14px system-ui;margin:20px}h1{font-size:22px}.grid{display:grid;grid-template-columns:repeat(8,1fr);gap:8px}article{background:#25353c;border:1px solid #607074;border-radius:8px;padding:8px;text-align:center;min-height:130px}svg{display:block;width:90px;height:90px;margin:auto}small{display:block;color:#b4cbbe;font-size:11px}p{margin:4px 0}</style><h1>Sprites originaux — corps partagés, armes et teintes</h1><div class="grid" id="gallery"></div>');
    await page.addScriptTag({content:fs.readFileSync(path.join(root,"jeuxRPG/multiplayer/web/sprites.js"),"utf8")});
    await page.evaluate(({catalog,mobs})=>{
      const namespace="http://www.w3.org/2000/svg";
      const element=(tag,attrs)=>{const e=document.createElementNS(namespace,tag);for(const[key,value]of Object.entries(attrs))e.setAttribute(key,value);return e;};
      const entries=Object.keys(catalog.bindings).sort((a,b)=>Number(!a.includes("gobelin")&&!a.includes("goblin"))-Number(!b.includes("gobelin")&&!b.includes("goblin"))||a.localeCompare(b));
      for(const target of entries){
        const card=document.createElement("article"),svg=element("svg",{viewBox:"0 0 40 40"});
        const picture=entitySprite({sprites:catalog},[target],element,[0,0]);svg.append(picture);card.append(svg);
        const title=document.createElement("p");title.textContent=mobs[target.slice(4)]?.name||target;card.append(title);
        const note=document.createElement("small");note.textContent=(catalog.equipment?.[target]||"Sans arme").replace("arme_","");card.append(note);
        document.getElementById("gallery").append(card);
      }
    },{catalog:content.sprites,mobs});
    await page.screenshot({path:path.join(root,".data/entity-sprites.png"),fullPage:true});
    console.log("Galerie locale : .data/entity-sprites.png");
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
