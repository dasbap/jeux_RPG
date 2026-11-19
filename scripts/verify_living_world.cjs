"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {test} = require("node:test");
const {JSDOM} = require("../.ui-test/node_modules/jsdom");

function setup() {
  const {window} = new JSDOM('<div id="region-view"></div>');
  const commands = [], context = vm.createContext({document:window.document,$:id=>window.document.getElementById(id),busy:false,tutorialCommand:(...args)=>commands.push(args)});
  vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/app_world.js","utf8"),context);
  context.tutorialCommand=(...args)=>commands.push(args);
  const life = {catching_up:false,local_town:"a",can_trade:true,towns:[{id:"a",name:"Ville A",status:"peaceful",integrity:100,guards:12,food:60,wood:40,stone:30,raid:null}],merchant:{name:"Caravane",location:"Ville A",stock:[{id:"wood",name:"Bois",unit_price:3,quantity:5}]},nearby:[],events:[]};
  return {context,document:window.document,life,commands,render:()=>context.renderLivingWorld({living_world:life})};
}

test("world actions quote the displayed price and preserve focused controls",()=>{
  const {document,life,commands,render}=setup(); render();
  const buy=document.querySelector("[data-item=wood]"); buy.focus();
  life.merchant.stock[0].unit_price=4; render();
  assert.equal(document.activeElement,buy); buy.click();
  assert.equal(JSON.stringify(commands),JSON.stringify([["world_buy",{item:"wood",quantity:1,unit_price:4}]]));
  assert(document.querySelector("[data-kind=defend]").disabled);
  life.towns[0].raid={phase:"warning"}; render();
  document.querySelector("[data-kind=defend]").click();
  assert.equal(commands[1][0],"world_help");
});

test("catch-up, distance, depleted stock and busy state disable trading",()=>{
  const {context,document,life,render}=setup();
  const disabled=()=>document.querySelector("[data-item=wood]").disabled;
  life.catching_up=true;render();assert(disabled());
  life.catching_up=false;life.can_trade=false;render();assert(disabled());
  life.can_trade=true;life.merchant.stock[0].quantity=0;render();assert(disabled());
  life.merchant.stock[0].quantity=5;context.busy=true;render();assert(disabled());
  context.busy=false;render();assert(!disabled());
});

test("news and town names render as text; stale rows and disabled worlds disappear",()=>{
  const {context,document,life,render}=setup();
  life.towns[0].name='<img src=x onerror="alert(1)">';
  life.events=[{id:"news",message:"<script>alert(1)</script>"}];render();
  assert.equal(document.querySelector("img,script"),null);
  assert.match(document.querySelector("#world-life-events").textContent,/<script>/);
  life.events=[];life.merchant.stock=[];render();
  assert.equal(document.querySelectorAll("#world-life-events li,#world-life-market button").length,0);
  context.renderLivingWorld({});assert(document.getElementById("world-life-view").hidden);
});
