"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const {JSDOM}=require("../.ui-test/node_modules/jsdom");
const root="jeuxRPG/multiplayer/web/";
function setup(){
 const dom=new JSDOM(fs.readFileSync(root+"index.html","utf8"),{url:"http://loading.test",runScripts:"outside-only"}),w=dom.window;
 w.setTimeout=()=>1;w.setInterval=()=>1;
 w.fetch=async()=>({ok:true,json:async()=>[]});
 const characters=[{id:"a",name:"Premier",class_name:"Knight"},{id:"b",name:"Deuxieme",class_name:"Mage"}];let selected="a",failed=false,flushes=0;
 const account=()=>({account:{username:"Solo"},characters,selected,token:`token-${selected}`});
 const transport={connected:true,subscribe:async()=>{},flush:async()=>{flushes++;},close:async()=>{},request:async(path,options)=>{
  if(failed)throw new Error("Lecture impossible");
  if(path==="/api/account/character")selected=JSON.parse(options.body).player_id;
  const body=path==="/api/classes"?[{id:"Knight",name:"Chevalier"},{id:"Mage",name:"Mage"},{id:"Archer",name:"Archer"}]:path==="/api/state"?{player:characters.find(c=>c.id===selected),session:null}:account();
  return {ok:true,status:200,json:async()=>body};
 }};
 w.createRpgSoloTransport=async({onProgress}={})=>{onProgress?.({title:"Moteur local",detail:"Chargement"});return transport;};
 w.eval(require("./client_source.cjs")()+';window.testApp={switchGameMode,selectCharacter,openCharacterRoster,refresh,state:()=>({lastPlayer,accountState,busy}),mode:()=>gameMode};');
 return {w,dom,transport,fail:()=>{failed=true;},flushes:()=>flushes,close:()=>w.close()};
}

test("overlapping loading jobs preserve progress, focus and input blocking",()=>{
 const dom=new JSDOM('<main><button id="start">Jouer</button></main>',{url:"http://loading.test",runScripts:"outside-only"}),w=dom.window;
 vm.runInContext(fs.readFileSync(root+"app_core.js","utf8"),dom.getInternalVMContext());
 try{
  const start=w.document.getElementById("start");start.focus();
  const first=w.RPGLoading.begin("Monde","Lecture"),second=w.RPGLoading.begin("Personnage","Reprise");
  assert(w.document.querySelector("main").inert);assert(w.document.body.classList.contains("rpg-loading"));
  first.update("Ancien travail","Toujours actif");assert.equal(w.document.getElementById("loading-title").textContent,"Personnage");
  second.finish();assert.equal(w.document.getElementById("loading-title").textContent,"Ancien travail");
  assert.equal(w.document.getElementById("loading-screen").hidden,false);
  first.finish();assert.equal(w.document.getElementById("loading-screen").hidden,true);assert.equal(w.document.activeElement,start);assert.equal(w.document.querySelector("main").inert,false);
 }finally{w.close();}
});

test("solo roster switches players without retaining old state or accepting late snapshots",async()=>{
 const s=setup();try{
  await s.w.testApp.switchGameMode("solo");assert.equal(s.w.document.querySelectorAll("[data-character]").length,2);
  assert.equal(s.w.document.querySelector('[data-character="a"]').getAttribute("aria-pressed"),"true");
  await s.w.testApp.selectCharacter({action:"select",player_id:"b"});
  assert.equal(s.w.testApp.state().lastPlayer.id,"b");assert.equal(s.w.document.getElementById("loading-screen").hidden,true);
  s.transport.onState({status:200,body:{player:{id:"a",name:"Old",class_name:"Knight"},session:null}});
  assert.equal(s.w.testApp.state().lastPlayer.id,"b");
  s.w.document.getElementById("game-menu-items").hidden=false;
  await s.w.testApp.openCharacterRoster();assert.equal(s.w.document.getElementById("game-menu-items").hidden,true);assert.equal(s.w.document.getElementById("characters").hidden,false);assert(s.flushes()>=2);
  assert.equal(s.w.document.querySelector('[data-character="b"]').getAttribute("aria-pressed"),"true");
  await s.w.testApp.selectCharacter({action:"select",player_id:"a"});assert.equal(s.w.testApp.state().lastPlayer.id,"a");
 }finally{s.close();}
});

test("failed character loading releases the screen and keeps the roster available",async()=>{
 const s=setup();try{
  await s.w.testApp.switchGameMode("solo");s.fail();
  await s.w.testApp.selectCharacter({action:"select",player_id:"b"});
  assert.equal(s.w.document.getElementById("loading-screen").hidden,true);
  assert.equal(s.w.document.getElementById("characters").hidden,false);
  assert.equal(s.w.testApp.state().busy,false);assert(s.w.document.getElementById("message").textContent.includes("Lecture impossible"));
 }finally{s.close();}
});

test("a failed solo engine startup never leaves the page inert",async()=>{
 const s=setup();try{
  s.w.createRpgSoloTransport=async()=>{throw new Error("Moteur indisponible");};
  await s.w.testApp.switchGameMode("solo");
  assert.equal(s.w.document.getElementById("loading-screen").hidden,true);
  assert.equal(s.w.document.querySelector("main").inert,false);
  assert.equal(s.w.testApp.state().busy,false);assert.equal(s.w.testApp.mode(),"online");
  assert.equal(s.w.document.getElementById("registration").hidden,false);
 }finally{s.close();}
});

test("a solo resume error returns to saved characters instead of a server retry screen",async()=>{
 const s=setup();try{
  await s.w.testApp.switchGameMode("solo");await s.w.testApp.selectCharacter({action:"select",player_id:"b"});s.fail();
  await s.w.testApp.refresh(true);
  assert.equal(s.w.document.getElementById("characters").hidden,false);
  assert.equal(s.w.document.getElementById("loading-screen").hidden,true);
  assert.equal(s.w.document.querySelectorAll("[data-character]").length,2);
  assert(s.w.document.getElementById("connection").textContent.includes("Solo"));
  assert(!s.w.document.getElementById("connection").textContent.includes("serveur"));
 }finally{s.close();}
});
