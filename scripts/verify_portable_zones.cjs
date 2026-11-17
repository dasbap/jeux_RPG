"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
module.exports=async function verifyZones(page,root){
 const bytes=Array.from(fs.readFileSync(path.join(root,".data/zone-desktop-fixture.sqlite3")));
 await page.evaluate(async data=>{
  const db=await new Promise((resolve,reject)=>{const request=indexedDB.open("jeux-rpg-solo",1);request.onupgradeneeded=()=>request.result.createObjectStore("saves");request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
  await new Promise((resolve,reject)=>{const tx=db.transaction("saves","readwrite");tx.objectStore("saves").put(new Uint8Array(data),"game");tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});db.close();
  await switchGameMode("solo",{resume:true});
 },bytes);
 await page.waitForFunction(()=>session?.tutorial?.field_map==="rosee"&&document.querySelector(".rpg-canvas3d")?.scene3D.stats.frames>3,null,{timeout:90000});
 try{await page.waitForFunction(()=>document.querySelector(".rpg-canvas3d").scene3D.items.some(a=>a.track),null,{timeout:15000});}
 catch(error){console.log(JSON.stringify(await page.evaluate(()=>({map:session.tutorial.battle.map.id,nearby:session.tutorial.living_world?.nearby,track:typeof RPGScene3D.GuardTrack,items:document.querySelector(".rpg-canvas3d").scene3D.items.map(a=>({id:a.id,kind:a.unit?.kind}))}))));throw error;}
 const patrol=await page.evaluate(()=>new Promise(resolve=>{
  const started=performance.now(),previous=new Map();let frames=0,moving=0,pauses=0,lastFrame=0;
  function inspect(now){
   const scene=document.querySelector(".rpg-canvas3d").scene3D;
   if(scene.last!==lastFrame){lastFrame=scene.last;frames++;
    for(const a of scene.items.filter(a=>a.track&&Array.isArray(a.display))){
     const prev=previous.get(a.id);
     if(prev&&scene.last-prev.at<100){
      const expected=a.track.sample(scene.last),before=a.track.sample(prev.at);
      if(Math.hypot(...expected.map((v,i)=>v-before[i]))>.0001){
       moving++;if(Math.hypot(...a.display.map((v,i)=>v-prev.position[i]))<.000001)pauses++;
      }
     }
     previous.set(a.id,{at:scene.last,position:[...a.display]});
    }
   }
   if(now-started>=6000)resolve({frames,moving,pauses});else requestAnimationFrame(inspect);
  }requestAnimationFrame(inspect);
 }));
 assert(patrol.frames>60);assert(patrol.moving>20,"Live patrols must actually walk");assert.equal(patrol.pauses,0,"No pause between buffered guard steps");
 console.log(JSON.stringify({check:"Live Windows guard animation follows buffered steps without pauses",result:"passed",...patrol}));
 await page.evaluate(()=>{const transport=rpgRealtime,original=transport.onState,request=transport.request.bind(transport);let sequence=0;globalThis.zoneCommands=[];
  transport.onState=result=>{setTimeout(()=>original(result),[40,160,65,240,110,190][sequence++%6]);};
  transport.request=async(path,options)=>{const result=await request(path,options);if(path==="/api/commands"){
   const payload=JSON.parse(options.body),body=await result.clone().json();zoneCommands.push({action:payload.action,encounter:payload.params.encounter,position:payload.params.position,status:result.status,error:body.error});
   await new Promise(resolve=>setTimeout(resolve,120));
  }return result;};
 });
 await page.locator(".rpg-canvas3d").focus();const crossings=[],baseline=await page.evaluate(()=>RPGMotion.diagnostics.hardResets);
 for(const [code,destination,entry,axis] of [["ArrowUp","rosee_caserne",30,-1],["ArrowDown","rosee",1,1],["ArrowUp","rosee_caserne",30,-1]]){
  const before=await page.evaluate(()=>session.tutorial.encounter_number);await page.keyboard.down(code);
  await page.waitForFunction(({destination,before})=>session.tutorial.field_map===destination&&session.tutorial.encounter_number>before,{destination,before},{timeout:25000});
  await page.waitForFunction(({destination,entry,axis})=>session.tutorial.field_map===destination&&(session.tutorial.battle.players[session.me].position[1]-entry)*axis>1,{destination,entry,axis},{timeout:15000});
  crossings.push(await page.evaluate(()=>({map:session.tutorial.field_map,encounter:session.tutorial.encounter_number,position:session.tutorial.battle.players[session.me].position})));
  await page.waitForFunction(axis=>{const hero=document.querySelector(".rpg-canvas3d").scene3D.items.find(a=>a.hero);return Math.cos(hero.yaw-(axis<0?Math.PI:0))>.9;},axis);
  assert(await page.evaluate(()=>!document.querySelector(".rpg-canvas3d").scene3D.items.some(a=>["monsters","raiders"].includes(a.unit?.kind))),"No abstract group is rendered as a character");
  await page.keyboard.up(code);await page.waitForFunction(()=>!RPGMotion.pending&&session.tutorial.battle.players[session.me].motion_axis?.every(v=>v===0),null,{timeout:15000});
 }
 const held=await page.evaluate(()=>session.tutorial.battle.players[session.me].position);await page.waitForTimeout(650);
 assert.deepEqual(await page.evaluate(()=>session.tutorial.battle.players[session.me].position),held);
 const diagnostics=await page.evaluate(()=>RPGMotion.diagnostics),commands=await page.evaluate(()=>zoneCommands);
 assert.equal(diagnostics.hardResets,baseline);assert.equal(diagnostics.maxCorrectionStep,0);
 assert(commands.filter(c=>c.action==="move_axis").every(c=>Array.isArray(c.position)));
 assert.deepEqual(commands.filter(c=>c.status!==200&&!["stale_encounter","movement_speed"].includes(c.error)),[]);
 await page.screenshot({path:path.join(root,".data/portable-zone-transitions.png")});await page.evaluate(()=>soloTransport.flush());
 console.log(JSON.stringify({check:"Windows portable, real offline Python engine: three held-key zone crossings, no extra clicks, delayed replies and no rollback",result:"passed",crossings,diagnostics}));
};
