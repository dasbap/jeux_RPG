"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs");
const {JSDOM}=require("../.ui-test/node_modules/jsdom");
function setup(){
 const dom=new JSDOM("<body></body>",{runScripts:"outside-only",pretendToBeVisual:true}),w=dom.window,timers=new Map(),calls=[];let sequence=0;
 w.session={id:"test",me:"hero",tutorial:{encounter_number:1,field_map:"first",battle:{movement_model:"continuous-v1"},players:[{id:"hero",hp:20}]}};
 w.fieldCamera={follow:false};w.RPGMotion={set:v=>calls.push(Array.from(v))};
 w.setInterval=fn=>{timers.set(++sequence,fn);return sequence;};w.clearInterval=id=>timers.delete(id);
 w.eval(fs.readFileSync("jeuxRPG/multiplayer/web/free_controls.js","utf8"));
 return {w,calls,timers,key:(type,code)=>w.dispatchEvent(new w.KeyboardEvent(type,{code,cancelable:true})),tick:()=>[...timers.values()].forEach(fn=>fn()),close:()=>dom.window.close()};
}
test("a held keyboard direction continues through multiple zones without clicks or repeated keydown",()=>{
 const s=setup();try{
  s.key("keydown","ArrowUp");assert.deepEqual(s.calls.at(-1),[0,-1]);
  for(let encounter=2;encounter<=4;encounter++){
   s.w.session.tutorial.encounter_number=encounter;s.w.session.tutorial.field_map=`zone-${encounter}`;
   const before=s.calls.length;s.tick();assert(s.calls.length>before);assert.deepEqual(s.calls.at(-1),[0,-1]);assert.equal(s.timers.size,1);
  }
  s.key("keyup","ArrowUp");assert.deepEqual(s.calls.at(-1),[0,0]);assert.equal(s.timers.size,0);
  s.key("keydown","ArrowRight");assert.deepEqual(s.calls.at(-1),[1,0]);
 }finally{s.close();}
});
test("a loading gap preserves held input, while blur still releases it",()=>{
 const s=setup();try{
  s.key("keydown","ArrowDown");s.w.session.tutorial.battle=null;s.tick();assert.equal(s.timers.size,1);
  s.w.session.tutorial.encounter_number++;s.w.session.tutorial.field_map="arrived";s.w.session.tutorial.battle={movement_model:"continuous-v1"};
  s.tick();assert.deepEqual(s.calls.at(-1),[0,1]);
  s.w.dispatchEvent(new s.w.Event("blur"));assert.deepEqual(s.calls.at(-1),[0,0]);assert.equal(s.timers.size,0);
 }finally{s.close();}
});

test("held movement survives a brief scene loading screen and release still stops it",()=>{
 const s=setup();try{
  s.key("keydown","ArrowUp");s.w.document.body.classList.add("rpg-loading");s.w.document.body.dataset.loadingScene="true";
  s.tick();assert.deepEqual(s.calls.at(-1),[0,0]);assert.equal(s.timers.size,1);
  s.w.session.tutorial.encounter_number++;s.w.session.tutorial.field_map="new-map";s.w.document.body.classList.remove("rpg-loading");
  s.tick();assert.deepEqual(s.calls.at(-1),[0,-1]);
  s.key("keyup","ArrowUp");assert.deepEqual(s.calls.at(-1),[0,0]);assert.equal(s.timers.size,0);
 }finally{s.close();}
});
