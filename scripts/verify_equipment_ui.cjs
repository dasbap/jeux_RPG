"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),{test}=require("node:test");
const {JSDOM}=require("../.ui-test/node_modules/jsdom");
function setup(){
 const {window}=new JSDOM(fs.readFileSync("jeuxRPG/multiplayer/web/index.html","utf8")),document=window.document,signatures=new Map(),calls=[];
 const piece={recipe:"veste",name:"Veste de la lisière",slot:"torso",level:3,hp:8,force:2,set_id:"lisiere"};
 const me={id:"p",gear:[piece],stored_gear:[{...piece,recipe:"manteau_veille",name:"Manteau de la Veille",level:2,hp:12}],equipment_sets:[{id:"lisiere",name:"Panoplie de la Lisière",pieces:1,tiers:[{pieces:2,active:false,bonuses:{hp:4}},{pieces:4,active:false,bonuses:{force:2}}]}],inventory:{bois:3},equipment_locked_reason:""};
 const adventure={players:[me]};
 const context=vm.createContext({document,$:id=>document.getElementById(id),session:{id:"test",me:"p",tutorial:adventure},busy:false,command:(...args)=>calls.push(args),sectionChanged:(key,value)=>{const next=JSON.stringify(value);if(signatures.get(key)===next)return false;signatures.set(key,next);return true;}});
 vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/app_world.js","utf8"),context);
 vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/app_bootstrap.js","utf8"),context);
 const render=()=>context.renderEquipment(adventure,me);render();return {window,document,context,me,adventure,calls,render};
}
test("equipment cards send real equip and unequip commands for owned pieces",()=>{
 const {document,calls}=setup();
 assert.equal(document.querySelectorAll(".equipment-slot").length,6);
 document.querySelector('[data-equipment-action="unequip"]').click();
 document.querySelector('[data-equipment-action="equip"]').click();
 assert.equal(calls[0][0],"unequip");assert.equal(calls[0][1].recipe,"veste");
 assert.equal(calls[1][0],"equip");assert.equal(calls[1][1].recipe,"manteau_veille");
 assert(document.querySelectorAll(".item-icon svg").length===2);
});

test("NPC dialogue removes completed quest cards and hides its empty quest heading",()=>{
 const {context,document,window,adventure}=setup();
 window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 window.HTMLDialogElement.prototype.close=function(){this.open=false;};
 const quest={id:"done",name:"Mission",description:"Objectif",reward_xp:10,missing_requirements:[],status:"active",progress:1,count:2};
 adventure.narrative={conversation:{npc:"mira",name:"Mira",text:"Bonjour",topics:[],choices:[],quests:[quest]},notes:[]};
 context.renderNarrative(adventure);assert.equal(document.querySelectorAll(".story-quest").length,1);
 quest.status="completed";context.renderNarrative(adventure);
 assert.equal(document.querySelectorAll(".story-quest").length,0);assert(document.getElementById("story-quest-heading").hidden);
 quest.status="locked";quest.missing_requirements=["Niveau 5 requis"];context.renderNarrative(adventure);
 assert.equal(document.querySelectorAll(".story-quest").length,0);assert(document.getElementById("story-quest-heading").hidden);
 quest.status="available";context.renderNarrative(adventure);assert.equal(document.querySelectorAll(".story-quest").length,0);
 quest.missing_requirements=[];context.renderNarrative(adventure);assert.equal(document.querySelectorAll(".story-quest").length,1);
});

test("inventory and equipment share exact set bonuses, current thresholds and projected activations",()=>{
 const {context,document,me,adventure,render}=setup();
 context.renderInventory(adventure,me);
 const gear=document.querySelector('#equipment-view [data-recipe="veste"] .item-set-bonuses');
 const inventory=document.querySelector('#inventory-view [data-recipe="veste"] .item-set-bonuses');
 assert.equal(gear.textContent,inventory.textContent);assert.match(inventory.textContent,/2 pièces.*Inactif/);assert.match(inventory.textContent,/\+4 PV/);
 const preview=context.itemSetBonuses({recipe:"casque",slot:"head",set_id:"lisiere"},me);assert.match(preview.textContent,/S’activera avec cette pièce/);
 me.equipment_sets[0].tiers[0].active=true;me.equipment_sets[0].pieces=2;render();context.renderInventory(adventure,me);
 assert.equal(document.querySelectorAll('#inventory-view .item-set-tier.active').length,2);
 document.getElementById("inventory-kind").value="materials";context.renderInventory(adventure,me);
 assert.equal(document.querySelectorAll('#inventory-gear .gear-card').length,0);assert.match(document.getElementById("inventory-details").textContent,/bois/);
});
test("search and slot selection filter immediately, comparisons and focus survive unchanged updates",()=>{
 const {document,window,render}=setup(),search=document.getElementById("equipment-search");
 const card=document.querySelector(".gear-card");card.querySelector("details").open=true;
 search.focus();render();assert.equal(document.querySelector(".gear-card"),card);assert(card.querySelector("details").open);assert.equal(document.activeElement,search);
 search.value="veille";search.dispatchEvent(new window.Event("input"));assert.equal(document.querySelectorAll(".gear-card").length,1);
 assert.match(document.querySelector(".gear-card").textContent,/\+4/);
 document.getElementById("equipment-slot").value="head";document.getElementById("equipment-slot").dispatchEvent(new window.Event("change"));assert.equal(document.querySelectorAll(".gear-card").length,0);assert(document.querySelector(".atlas-empty"));
});
test("server equipment restrictions disable actions and update after a piece is removed",()=>{
 const {document,me,render}=setup();me.equipment_locked_reason="Hors combat uniquement";render();
 assert([...document.querySelectorAll(".gear-action")].every(button=>button.disabled));
 assert.match(document.getElementById("equipment-status").textContent,/Hors combat/);
 me.equipment_locked_reason="";me.stored_gear.push(me.gear.pop());render();
 assert.equal(document.querySelectorAll('[data-equipment-action="unequip"]').length,0);
 assert.equal(document.querySelectorAll('[data-equipment-action="equip"]').length,2);
});

test("weapon slots and shared class requirements are shown, incompatible equipment stays disabled",()=>{
 const {context,document,me,adventure,render}=setup();
 me.class_name="Knight";
 const staff={recipe:"baton_lucioles",name:"Bâton des Lucioles",slot:"weapon",weapon_type:"staff",level:0,classes:["Mage","Priest","Necromancien"],class_names:["Mage","Prêtre","Nécromancien"],intelligence:3,sagesse:3};
 me.stored_gear.push(staff);me.forge=[staff];render();
 assert.equal(document.querySelectorAll(".equipment-slot").length,7);
 const button=()=>document.querySelector('[data-recipe="baton_lucioles"] [data-equipment-action="equip"]');
 assert(button().disabled);assert(document.querySelector('[data-recipe="baton_lucioles"] .item-classes').textContent.includes("Prêtre"));
 context.renderInventory(adventure,me);
 assert(document.querySelector('#inventory-gear [data-recipe="baton_lucioles"] button').disabled);
 me.class_name="Priest";render();assert(!button().disabled);
 me.class_name="Mage";render();assert(!button().disabled);
 me.class_name="Necromancien";render();assert(!button().disabled);
});
