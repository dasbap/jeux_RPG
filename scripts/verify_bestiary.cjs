"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {test} = require("node:test");
const {JSDOM} = require("../.ui-test/node_modules/jsdom");

function setup() {
  const {window} = new JSDOM(fs.readFileSync("jeuxRPG/multiplayer/web/index.html","utf8"));
  const document = window.document, signatures = new Map();
  const maps = [{id:"a",name:"Auberge"},{id:"z",name:"Zéphyr"}];
  const monster = (id,name,spawn,loot) => ({id,name,rank:"D",description:"Découvert",hp:{first_encounter:20,hunt:30},stats:{force:5,endurance:3,intelligence:1,sagesse:1},weaknesses:[],resistances:[],loot:[{item:loot,quantity:1,max_quantity:1,chance:1,attempts:1}],xp:{hunt:10},spawn_maps:spawn,rare_loot:[{item:"Rubis",chance:.1,attempts:1,min:1,max:1}],materials_usage:"Forge"});
  const adventure = {world:{bestiary:[monster("wolf","Loup",maps,"Fourrure"),monster("boar","Sanglier",[maps[0]],"Cuir")]}};
  const context = vm.createContext({document,$:id=>document.getElementById(id),session:{id:"test",tutorial:adventure},renderGame:()=>{throw Error("Un filtre ne doit pas redessiner le jeu");},sectionChanged:(key,value)=>{const next=JSON.stringify(value);if(signatures.get(key)===next)return false;signatures.set(key,next);return true;}});
  const core=fs.readFileSync("jeuxRPG/multiplayer/web/app_core.js","utf8");
  vm.runInContext(core.slice(core.indexOf("function syncSelectOptions("),core.indexOf("let pendingBattleMove")),context);
  vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/app_world.js","utf8"),context);
  vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/app_bootstrap.js","utf8"),context);
  context.renderBestiary(adventure);
  const change=(id,value)=>{document.getElementById(id).value=value;document.getElementById(id).dispatchEvent(new window.Event(id==="bestiary-search"?"input":"change"));};
  return {context,document,adventure,change,cards:()=>[...document.querySelectorAll("#bestiary-details article")]};
}

test("map, text, rare materials and sort filters update immediately without a game redraw",()=>{
  const {document,change,cards}=setup();
  assert.equal(cards().length,2);
  change("bestiary-map","z");assert.equal(cards().length,1);assert.match(cards()[0].textContent,/Loup/);
  change("bestiary-map","");change("bestiary-search","CUIR");assert.equal(cards().length,1);assert.match(cards()[0].textContent,/Sanglier/);
  change("bestiary-search","Rubis");assert.equal(cards().length,2);
  change("bestiary-sort","desc");assert.match(cards()[0].textContent,/Zéphyr, Auberge/);
  change("bestiary-search","absent");assert.equal(cards().length,0);assert.match(document.getElementById("bestiary-details").textContent,/Aucun mob/);
});

test("unchanged bestiary keeps its DOM and scroll while other world data changes",()=>{
  const {context,document,adventure,cards}=setup();
  const card=cards()[0],root=document.getElementById("bestiary-details");root.scrollTop=180;
  adventure.world.current="elsewhere";
  context.renderBestiary(adventure);
  assert.equal(cards()[0],card);assert.equal(root.scrollTop,180);
  adventure.world.bestiary[0].name="Nouveau loup";
  context.renderBestiary(adventure);assert.match(cards()[0].textContent,/Nouveau loup/);
});

test("a disappeared map resets its filter and an empty bestiary clears previous cards",()=>{
  const {context,document,adventure,change,cards}=setup();
  change("bestiary-map","z");
  adventure.world.bestiary=adventure.world.bestiary.slice(1);
  context.renderBestiary(adventure);
  assert.equal(document.getElementById("bestiary-map").value,"");assert.equal(cards().length,1);
  adventure.world.bestiary=[];context.renderBestiary(adventure);
  assert.equal(cards().length,0);assert.match(document.getElementById("bestiary-details").textContent,/Aucun monstre/);
});
