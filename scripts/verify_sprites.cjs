"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const {test}=require("node:test");
const {JSDOM}=require("../.ui-test/node_modules/jsdom");
function setup(){
  const document=new JSDOM("<html></html>").window.document;
  const context=vm.createContext({});
  vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/sprites.js","utf8"),context);
  const sprite={name:"Test",width:2,height:2,palette:[null,"#123456","#abcdef"],frames:[["01","20"],["02","10"]],frame_ms:120};
  const adventure={sprites:{assets:{hero:sprite},bindings:{"class:Knight":"hero","ambient:guards":"hero"}}};
  const element=(tag,attrs)=>{const node=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,value);return node;};
  return {context,adventure,element,sprite};
}
test("sprites resolve bindings, transparency and animation without external image requests",()=>{
  const {context,adventure,element}=setup();
  const node=context.entitySprite(adventure,["npc:absent","class:Knight"],element,[3,4]);
  assert.equal(node.getAttribute("data-sprite"),"hero");
  const svg=decodeURIComponent(node.getAttribute("href").split(",")[1]);
  assert.match(svg,/shape-rendering="crispEdges"/);assert.match(svg,/#123456/);
  assert.match(svg,/repeatCount="indefinite"/);assert.match(svg,/dur="240ms"/);
  assert(!svg.includes("<script")&&!svg.includes("<image")&&!svg.includes('fill="null"'));
  assert.equal(context.entitySprite(adventure,["mob:unassigned"],element,[0,0]),null);
  assert.equal(context.entitySprite({},["class:Knight"],element,[0,0]),null);
});
test("sprite URI cache survives snapshots and changes when a pixel changes",()=>{
  const {context,sprite}=setup();
  const first=context.spriteDataUri(sprite);
  assert.equal(context.spriteDataUri(JSON.parse(JSON.stringify(sprite))),first);
  sprite.frames[0][0]="11";assert.notEqual(context.spriteDataUri(sprite),first);
});
test("weapon and tint changes reuse body pixels and generate separate cached compositions",()=>{
  const {context,adventure,element,sprite}=setup();
  // A real body palette has dedicated primary and highlight slots.
  sprite.palette.push("#336633","#669966");sprite.frames[0][0]="03";
  const original=JSON.stringify(sprite);
  adventure.sprites.assets.sword={...sprite,name:"Sword",frames:[["10","00"]],layer:"weapon"};
  adventure.sprites.equipment={"class:Knight":"sword"};
  adventure.sprites.colors={"class:Knight":"#2244aa"};
  const node=context.entitySprite(adventure,["class:Knight"],element,[0,0]);
  const rendered=decodeURIComponent(node.getAttribute("href").split(",")[1]);
  assert.match(rendered,/data-layer="body"/);assert.match(rendered,/data-layer="weapon"/);assert.match(rendered,/#2244aa/);
  assert.equal(node.getAttribute("data-weapon"),"sword");assert.equal(JSON.stringify(sprite),original);
  delete adventure.sprites.equipment["class:Knight"];
  assert.notEqual(context.entitySprite(adventure,["class:Knight"],element,[0,0]).getAttribute("href"),node.getAttribute("href"));
});
