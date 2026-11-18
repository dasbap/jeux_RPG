"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const {JSDOM}=require("../.ui-test/node_modules/jsdom");
function setup(saved){
 const dom=new JSDOM(fs.readFileSync("jeuxRPG/multiplayer/web/index.html","utf8"),{runScripts:"outside-only",pretendToBeVisual:true,url:"http://controls.test"}),w=dom.window,d=w.document,calls=[];
 if(saved)w.localStorage.setItem("rpg-keybindings-v1",saved);
 w.$=id=>d.getElementById(id);w.session={id:"test",me:"hero",tutorial:{encounter_number:1,field_map:"cave_1",battle:{movement_model:"continuous-v1",players:{hero:{position:[2,2]}}},players:[{id:"hero",hp:20}],mobs:[
  {combat_id:"far",position:[8,2],stats:{hp:{current:20}}},
  {combat_id:"near",position:[3,2],stats:{hp:{current:20}}},
  {combat_id:"dead",position:[2,2],stats:{hp:{current:0}}},
  {combat_id:"friend",position:[2,3],hostile:false,stats:{hp:{current:20}}}],world:{places:[]}}};
 w.busy=false;w.gameMode="online";w.focusedMob="";w.combatTarget="";w.fieldCamera={follow:true};w.RPGMotion={set:v=>calls.push(["motion",...v]),position:()=>[2,2]};
 w.RPGScene3D={attack:()=>calls.push(["attack"])};w.tutorialCommand=(...args)=>calls.push(args);w.message=text=>calls.push(["message",text]);
 vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/free_controls.js","utf8"),dom.getInternalVMContext());
 vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/app_world.js","utf8"),dom.getInternalVMContext());
 vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/app_bootstrap.js","utf8"),dom.getInternalVMContext());
 w.showView=(view,options)=>{calls.push(["view",view]);d.body.classList.toggle("hud-menu-open",!(d.body.classList.contains("hud-menu-open")&&w.currentView===view&&options?.toggle!==false));w.currentView=view;d.getElementById("options-view").hidden=view!=="options";};
 w.selectEntity=id=>{w.focusedMob=w.focusedMob===id?"":id;w.combatTarget=w.focusedMob;calls.push(["target",w.focusedMob]);};
 w.tutorialCommand=(...args)=>calls.push(args);
 const key=(key,code="",extra={},target=d.body)=>{const event=new w.KeyboardEvent("keydown",{key,code,bubbles:true,cancelable:true,...extra});target.dispatchEvent(event);return event;};
 return {w,d,calls,key,close:()=>{w.RPGKeybindings.destroy();w.close();}};
}

test("target cycling starts near, wraps, reverses and ignores dead or friendly entities",()=>{
 const s=setup();try{
  s.w.combatTarget="near";s.key("Tab","Tab");assert.equal(s.w.focusedMob,"near");
  s.key("Tab","Tab");assert.equal(s.w.focusedMob,"far");
  s.key("Tab","Tab");assert.equal(s.w.focusedMob,"near");
  s.key("Tab","Tab",{shiftKey:true});assert.equal(s.w.focusedMob,"far");
  s.w.session.tutorial.mobs=s.w.session.tutorial.mobs.filter(m=>m.combat_id==="far");
  s.key("Tab","Tab");assert.equal(s.w.focusedMob,"far");
 }finally{s.close();}
});

test("attack runs once, respects rebinding, rejects conflicts and persists changes",()=>{
 const s=setup();let saved;try{
  s.key(" ","Space");s.key(" ","Space",{repeat:true});assert.equal(s.calls.filter(c=>c[0]==="attack").length,1);
  assert.equal(s.w.RPGKeybindings.bind("attack","i"),false);
  assert.equal(s.w.RPGKeybindings.bind("attack","w"),false);
  assert.equal(s.w.RPGKeybindings.bind("attack","v"),true);
  s.key(" ","Space");s.key("v","KeyV");assert.equal(s.calls.filter(c=>c[0]==="attack").length,2);
  saved=s.w.localStorage.getItem("rpg-keybindings-v1");
 }finally{s.close();}
 const restored=setup(saved);try{assert.equal(restored.w.RPGKeybindings.label("attack"),"V");restored.key("v","KeyV");assert.equal(restored.calls.filter(c=>c[0]==="attack").length,1);}finally{restored.close();}
});

test("chat, forms, editable text, dialogs, modifiers and composition never trigger shortcuts",()=>{
 const s=setup();try{
  for(const tag of ["input","textarea","select","div"]){
   const target=s.d.createElement(tag);if(tag==="div")target.contentEditable="true",target.setAttribute("contenteditable","");s.d.body.append(target);
   for(const [key,code]of [[" ","Space"],["i","KeyI"],["Tab","Tab"]])assert.equal(s.key(key,code,{},target).defaultPrevented,false);
  }
  for(const modifier of ["ctrlKey","metaKey","altKey","isComposing"])s.key("i","KeyI",{[modifier]:true});
  const dialog=s.d.createElement("dialog");dialog.open=true;s.d.body.append(dialog);s.key(" ","Space");s.key("i","KeyI");
  assert.equal(s.calls.length,0);
 }finally{s.close();}
});

test("menus toggle with their key, stop movement and suppress combat shortcuts",()=>{
 const s=setup();try{
  s.key("i","KeyI");assert(s.d.body.classList.contains("hud-menu-open"));assert.deepEqual(s.calls[0],["motion",0,0]);
  s.key(" ","Space");s.key("Tab","Tab");assert(!s.calls.some(c=>["attack","target"].includes(c[0])));
  s.key("i","KeyI");assert(!s.d.body.classList.contains("hud-menu-open"));
  for(const [key,view]of [["e","equipment"],["j","quest"],["m","map"],["b","bestiary"],["c","stats"],["o","options"]]){s.key(key,`Key${key.toUpperCase()}`);assert(s.calls.some(c=>c[0]==="view"&&c[1]===view));}
 }finally{s.close();}
});

test("talk uses server-provided proximity and skills support AZERTY digit keys",()=>{
 const s=setup();try{
  s.key("f","KeyF");assert(!s.calls.some(c=>c[0]==="talk"));
  s.w.session.tutorial.field_interactions=[{id:"mira",dialogue:"Bonjour"}];
  s.key("f","KeyF");assert.equal(s.calls.at(-1)[0],"talk");assert.equal(s.calls.at(-1)[1].npc,"mira");
  const button=s.d.createElement("button");button.onclick=()=>s.calls.push(["skill"]);s.d.getElementById("skill-offense").append(button);
  s.key("&","Digit1");assert.equal(s.calls.at(-1)[0],"skill");
  s.w.busy=true;s.key("f","KeyF");assert.equal(s.calls.at(-1)[0],"skill");
 }finally{s.close();}
});

test("binding capture cancels with Escape and reset restores defaults",()=>{
 const s=setup();try{
  s.d.querySelector('[data-binding="attack"]').click();
  s.key("i","KeyI");assert(s.d.getElementById("keybinding-status").textContent.includes("déjà"));
  s.key("Escape","Escape");assert.equal(s.w.RPGKeybindings.label("attack"),"Espace");
  s.d.querySelector('[data-binding="attack"]').click();s.key("v","KeyV");assert.equal(s.w.RPGKeybindings.label("attack"),"V");
  s.d.querySelector("#keybindings > button").click();assert.equal(s.w.RPGKeybindings.label("attack"),"Espace");
  assert(!s.calls.some(c=>c[0]==="attack"));
 }finally{s.close();}
});


test("corpse targeting skips harvested or empty bodies, cycles backwards and harvests nearby",()=>{
 const s=setup();try{
  const a=s.w.session.tutorial;
  a.battle.corpses=[{id:"empty",name:"Vide",position:[2,2],loot:{},harvested:[]},{id:"used",name:"Pris",position:[2,2],loot:{peau:1},harvested:["other"]},{id:"body-near",name:"Proche",position:[3,2],loot:{peau:1},harvested:[]},{id:"body-far",name:"Loin",position:[7,2],loot:{peau:1},harvested:[]}];
  s.key("x","KeyX");assert.equal(s.w.focusedMob,"body-near");
  s.key("g","KeyG");assert.equal(s.calls.at(-1)[0],"harvest");assert.equal(s.calls.at(-1)[1].target,"body-near");
  s.key("x","KeyX");assert.equal(s.w.focusedMob,"body-far");
  s.key("x","KeyX",{shiftKey:true});assert.equal(s.w.focusedMob,"body-near");
  a.battle.corpses[2].harvested=["hero"];
  s.key("x","KeyX");assert.equal(s.w.focusedMob,"body-far");
  s.w.busy=true;const count=s.calls.length;s.key("g","KeyG");assert.equal(s.calls.length,count);
 }finally{s.close();}
});

test("new corpse shortcuts preserve existing custom keys without collisions",()=>{
 const s=setup(JSON.stringify({attack:"g",inventory:"x"}));try{
  assert.equal(s.w.RPGKeybindings.label("attack"),"G");assert.equal(s.w.RPGKeybindings.label("inventory"),"X");
  const keys=[...s.d.querySelectorAll('[data-binding]')].map(b=>b.textContent);assert.equal(new Set(keys).size,keys.length);
 }finally{s.close();}
});
