"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {JSDOM} = require("../.ui-test/node_modules/jsdom");
const {test} = require("node:test");
const root = path.join(__dirname, "..");
function setup() {
  const dom = new JSDOM(fs.readFileSync(path.join(root,"jeuxRPG/multiplayer/web/index.html"),"utf8"));
  const document = dom.window.document;
  const signatures = new Map();
  const adventure = {
    field_map:"hunt",position:"hunt",location:"Campement",objective:"Explorer",
    quest_journal:[
      {id:"first",name:"Les éclaireurs",status:"active",progress:0,count:3,zone:"woods",npc:"mira",description:"Chercher les éclaireurs",reward_xp:100},
      {id:"second",name:"Le chef",status:"active",progress:0,count:1,map:"hunt",zone:"woods",npc:"mira",description:"Battre le chef",reward_xp:200},
    ],
    world:{current:"woods",places:[{id:"woods",points:[{id:"hunt"}]},{id:"village",points:[{id:"mira"}]}]},
    mobs:[],
    battle:{map:{id:"field_hunt",name:"Campement",width:8,height:6,cover:[[3,1]],blocked:[],water:[[6,4]],bridges:[],paths:[[1,1],[2,1]],sites:[{id:"hidden-npc",name:"PNJ caché",position:[6,4]}],exits:[{name:"Village",position:[0,1],destination:"village"}]},players:{p:{position:[1,1]}},explored:[[1,1],[2,1],[3,1]]},
  };
  let renders=0;
  const context=vm.createContext({
    document, $:id=>document.getElementById(id), session:{id:"test",me:"p",tutorial:adventure},
    trackedQuestId:"",fieldCamera:{map:"field_hunt",x:1,y:1,follow:true},cameraReturnTimer:null,
    currentView:"map",regionTravelState:null,
    renderGame:()=>{renders++;},clearTimeout(){},setTimeout:()=>1,returnCameraToPlayer(){},
    sectionChanged:(key,value)=>{const next=JSON.stringify(value);if(signatures.get(key)===next)return false;signatures.set(key,next);return true;},
  });
  vm.runInContext(fs.readFileSync(path.join(root,"jeuxRPG/multiplayer/web/app_world.js"),"utf8"),context);
  return {context,document,adventure,renders:()=>renders};
}
test("regional map closes on field arrival, including instant passages",()=>{
  const {context,document,adventure}=setup();
  context.syncRegionTravel(adventure);
  document.body.classList.add("hud-menu-open");
  context.syncRegionTravel(adventure);
  assert(document.body.classList.contains("hud-menu-open"));
  adventure.field_map="forest";context.syncRegionTravel(adventure);
  assert(!document.body.classList.contains("hud-menu-open"));
  adventure.field_map=null;context.syncRegionTravel(adventure);
  document.body.classList.add("hud-menu-open");
  context.syncRegionTravel(adventure);
  assert(document.body.classList.contains("hud-menu-open"));
  adventure.field_map="rosee";context.syncRegionTravel(adventure);
  assert(!document.body.classList.contains("hud-menu-open"));
});
test("physical exits open the global map without launching travel",()=>{
  const {context,document,adventure}=setup();context.syncRegionTravel(adventure);
  context.currentView="quest";
  adventure.field_map=null;adventure.battle=null;adventure.moving=false;
  context.syncRegionTravel(adventure);
  assert.equal(context.currentView,"map");
  assert(document.body.classList.contains("hud-menu-open"));
  assert.equal(adventure.moving,false);
});
test("field arrival preserves another menu and does not close a new session's map",()=>{
  const {context,document,adventure}=setup();context.syncRegionTravel(adventure);
  document.body.classList.add("hud-menu-open");context.currentView="quest";
  adventure.field_map="forest";context.syncRegionTravel(adventure);
  assert(document.body.classList.contains("hud-menu-open"));
  context.currentView="map";context.session.id="new-session";
  adventure.field_map="rosee";context.syncRegionTravel(adventure);
  assert(document.body.classList.contains("hud-menu-open"));
});
test("departure shows a moving character and countdown, then removes them on arrival",()=>{
  const {context,document,adventure}=setup();
  context.syncRegionTravel(adventure);
  document.body.classList.add("hud-menu-open");
  adventure.field_map=null;adventure.battle=null;adventure.moving=true;
  adventure.travel_progress=.2;adventure.travel_remaining_real_seconds=8;
  adventure.travel_source_name="Village de Rosée";adventure.travel_goal_name="Forêt des Éveillés";
  context.syncRegionTravel(adventure);context.renderJourney(adventure);
  assert(!document.body.classList.contains("hud-menu-open"));
  assert.equal(document.getElementById("journey-view").hidden,false);
  assert.equal(document.getElementById("journey-player").style.left,"20%");
  assert.equal(document.getElementById("journey-progress").value,.2);
  assert(document.getElementById("journey-route").textContent.includes("Village de Rosée → Forêt des Éveillés"));
  adventure.travel_progress=.7;adventure.travel_remaining_real_seconds=3;
  context.renderJourney(adventure);
  assert.equal(document.getElementById("journey-player").style.left,"70%");
  assert(document.getElementById("journey-remaining").textContent.includes("3 s"));
  adventure.moving=false;context.renderJourney(adventure);
  assert.equal(document.getElementById("journey-view").hidden,true);
});
test("global zone selection follows the Builder graph and resolves its entrance",()=>{
  const {context,adventure}=setup();
  adventure.position="clearing";
  adventure.world.graph={clearing:["forest"],forest:["rosee"],rosee:[],lisiere:[]};
  adventure.world.zone_entries={zone_rosee:"rosee"};
  assert.deepEqual(JSON.parse(JSON.stringify(context.worldPaths(adventure,"zone_rosee"))),{clearing:["forest","rosee"]});
  assert.equal(context.worldPaths(adventure,"lisiere").clearing,null);
  adventure.world.graph.forest=[];
  assert.equal(context.worldPaths(adventure,"zone_rosee").clearing,null);
});
test("reverse passages share one named route instead of overlapping",()=>{
  const {context}=setup();
  const groups=context.worldRouteGroups([
    {from:"forest",to:"village",name:"Chemin"},
    {from:"village",to:"forest",name:"Retour à Chemin"},
    {from:"village",to:"forest",name:"Retour · Chemin"},
    {from:"village",to:"lisiere",name:"Lisière"},
  ]);
  assert.equal(groups.length,2);
  assert.equal(groups[0].routes.length,3);
  assert.equal(groups[0].name,"Chemin");assert.equal(groups[1].name,"Lisière");
  assert.equal(groups[0].number,undefined);
});
test("route names wrap and avoid one another and place markers",()=>{
  const {context}=setup();
  const places=[{id:"a",name:"Forêt",x:80,y:60},{id:"b",name:"Village",x:380,y:60},{id:"c",name:"Grotte",x:80,y:240},{id:"d",name:"Lisière",x:380,y:240}];
  const groups=context.worldRouteGroups([
    {from:"a",to:"b",name:"Le long chemin des voyageurs de Rosée"},
    {from:"a",to:"c",name:"Chemin des bois"},
    {from:"c",to:"d",name:"Sentier oublié"},
    {from:"b",to:"d",name:"Route de la lisière"},
  ]);
  const labels=context.worldRouteLabels(groups,places,610,320);
  const overlap=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
  assert(labels[0].lines.length>1);
  for(const [index,label] of labels.entries()) {
    assert(label.x>=0&&label.y>=0&&label.x+label.width<=610&&label.y+label.height<=320);
    assert(!labels.slice(index+1).some(other=>overlap(label,other)));
    assert(!places.some(place=>overlap(label,{x:place.x-18,y:place.y-18,width:36,height:36})));
  }
});
test("local minimap draws discovered terrain without revealing hidden terrain or NPCs",()=>{
  const {context,document,adventure}=setup();context.renderHudNavigation(adventure);
  assert(document.querySelector(".mini-road"));
  assert(document.querySelector(".mini-wall"));
  assert.equal(document.querySelector(".mini-water"),null);
  assert.equal(document.querySelector('[data-mini-point="hidden-npc"]'),null);
  assert(document.querySelector('[data-mini-point="player"]'));
  assert(document.querySelector('[data-mini-point="exit-0"]'));
  assert.equal(document.querySelectorAll(".hud-mini-route").length,0);
  assert.equal(document.querySelector("#minimap-location").textContent,"Campement");
});
test("player movement updates the marker while retaining unchanged terrain",()=>{
  const {context,document,adventure}=setup();context.renderHudNavigation(adventure);
  const terrain=document.querySelector(".mini-road");
  const marker=document.querySelector(".mini-player").getAttribute("d");
  adventure.battle.players.p.position=[2,1];context.renderHudNavigation(adventure);
  assert.equal(document.querySelector(".mini-road"),terrain);
  assert.notEqual(document.querySelector(".mini-player").getAttribute("d"),marker);
  adventure.battle.explored.push([6,4]);context.renderHudNavigation(adventure);
  assert(document.querySelector(".mini-water"));
  assert(document.querySelector('[data-mini-point="hidden-npc"]'));
});
test("exit buttons inspect the camera without moving the player",()=>{
  const {context,document,adventure,renders}=setup();context.renderHudNavigation(adventure);
  document.querySelector("#minimap-exits button").click();
  assert.equal(context.fieldCamera.follow,false);
  assert.equal(context.fieldCamera.x,0);
  assert.equal(context.fieldCamera.y,1);
  assert.deepEqual(adventure.battle.players.p.position,[1,1]);
  assert.equal(renders(),1);
});
test("each quest can be tracked and returning a completed objective points to its NPC",()=>{
  const {context,document,adventure}=setup();context.renderQuestJournal(adventure);
  assert.equal(document.querySelectorAll(".quest-card").length,2);
  assert(document.querySelector('[data-quest="second"]').textContent.includes("Battre le chef"));
  document.querySelector('[data-track-quest="second"]').click();
  context.renderQuestJournal(adventure);context.renderHudNavigation(adventure);
  assert.equal(context.activeHudQuest(adventure).id,"second");
  assert(document.getElementById("hud-objective").textContent.includes("Le chef"));
  assert.equal(context.hudQuestTarget(adventure).point,"hunt");
  adventure.quest_journal[1].progress=1;
  assert.equal(context.hudQuestTarget(adventure).point,"mira");
  assert.equal(context.hudQuestTarget(adventure).zone,"village");
});
test("world travel hides the old local terrain instead of showing an unrelated diagram",()=>{
  const {context,document,adventure}=setup();context.renderHudNavigation(adventure);
  adventure.battle=null;context.renderHudNavigation(adventure);
  assert(document.getElementById("hud-minimap").hasAttribute("hidden"));
  assert.equal(document.getElementById("minimap-world").hidden,false);
});
test("only visible targets of the tracked quest are highlighted",()=>{
  const {context,document,adventure}=setup();
  context.trackedQuestId="second";
  adventure.quest_journal[1].kind="kill";adventure.quest_journal[1].target="boss";
  adventure.mobs=[
    {combat_id:"boss-1",mob_id:"boss",name:"Chef",position:[2,1],stats:{hp:{current:10}}},
    {combat_id:"guard-1",mob_id:"guard",name:"Garde",position:[1,1],stats:{hp:{current:10}}},
  ];
  context.renderHudNavigation(adventure);
  assert(document.querySelector('[data-mini-point="boss-1"][data-mini-objective]'));
  assert.equal(document.querySelector('[data-mini-point="guard-1"][data-mini-objective]'),null);
});
