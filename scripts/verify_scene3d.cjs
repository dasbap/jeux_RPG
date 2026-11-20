"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const {test}=require("node:test");
function setup(){const context=vm.createContext({});vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/sprites.js","utf8")+"\n"+fs.readFileSync("jeuxRPG/multiplayer/web/scene_3d.js","utf8"),context);return context.RPGScene3D;}

test("cave terrain has its own dark palette, rock walls and discovered light sources",()=>{
 const api=setup(),map={biome:"cave",width:4,height:4,cover:[[0,0]],decorations:[{position:[0,0],kind:"rock"},{position:[1,1],kind:"camp"},{position:[3,2],kind:"crystal"}]};
 assert(api.environment(map).cave);assert(!api.environment({biome:"forest"}).cave);
 assert.notEqual(api.environment(map).ground,api.environment({biome:"forest"}).ground);
 const mesh=new api.Mesh();api.scenery(mesh,map,null,{x:2,z:2,span:8});assert(mesh.data.every(Number.isFinite));assert(mesh.data.some((value,i)=>i%6===1&&value>1));
 assert.equal(api.caveLights(map,new Set(),[1,1]).length,0);
 assert.deepEqual(Array.from(api.caveLights(map,new Set(["1,1"]),[1,1])),[1,1,0]);
 assert.deepEqual(Array.from(api.caveLights(map,null,[3,2])).slice(0,3),[3,2,1]);
});

test("terrain relief recesses water, keeps bridges walkable and hides unseen details",()=>{
 const api=setup(),map={width:4,height:4,cover:[],water:[[1,1],[2,1]],bridges:[[2,1]],decorations:[{position:[3,2],kind:"rock"}]},camera={x:2,z:2,span:8};
 const mesh=new api.Mesh();api.scenery(mesh,map,null,camera);
 assert(mesh.data.every(Number.isFinite));
 const heights=mesh.data.filter((_,i)=>i%6===1);
 assert(heights.some(y=>y===-.22));assert(heights.some(y=>y>.5));
 const hidden=new api.Mesh();api.scenery(hidden,map,new Set(),camera);
 assert(!hidden.data.filter((_,i)=>i%6===1).some(y=>y>0||y===-.22));
});
test("fixed 3D projection and geometry stay finite with no camera rotation API",()=>{
  const api=setup(),camera={x:5,z:6,halfW:10,halfH:7};
  assert.deepEqual(Array.from(api.project([5,6],camera)),[.5,.5]);
  assert(api.project([5,6],camera,1)[1]<.5);
  assert(Object.isFrozen(api.cameraAngle));assert.equal(api.cameraAngle.azimuth,0);
  const mesh=new api.Mesh();mesh.box(1,0,2,1,2,1,[.5,.6,.7]);mesh.ball(1,1,1,.3,.3,.3,[.2,.3,.4]);
  assert(mesh.data.length>0&&mesh.data.length%18===0);assert(mesh.data.every(Number.isFinite));
});
test("all skill categories have distinct effects and server cues are deduplicated",()=>{
  const api=setup(),effects=new api.CombatEffects();
  const cue={id:1,at:0,actor:"hero",target:"enemy",source:[3,3],destination:[4,3],kind:"skill",type:"HEAL",name:"Soin",range:6,amount:-5,duration:0};
  const adventure={encounter_number:1,battle:{map:{id:"field_test"},visual_now:0,visual_events:[cue]}};
  const actors=[{id:"hero",look:{weapon:"arme_bow"},unit:{},position:[3,3]}];
  effects.ingest(adventure,actors,0);effects.ingest(adventure,actors,.1);assert.equal(effects.events.length,1);
  const kinds=new Set();
  for(const type of ["DAMAGE","HEAL","BUFF","DEBUFF","INVOCATION","RESURRECT"]){
    const event={...cue,id:++cue.id,type};const style=api.effectStyle(event,actors[0].look);kinds.add(style.kind);
    effects.events=[{...event,...style,start:0}];const mesh=new api.Mesh();effects.draw(mesh,.2,actors);
    assert(mesh.data.length>0);assert(mesh.data.every(Number.isFinite));
  }
  assert(kinds.size>=5);
  assert.equal(api.effectStyle({...cue,type:"DAMAGE",kind:"strike",range:1.5},{}).kind,"slash");
  assert.equal(api.effectStyle({...cue,type:"DAMAGE",kind:"strike",range:6},{weapon:"arme_bow"}).kind,"arrow");
  effects.events=[{...cue,...api.effectStyle({...cue,kind:"cast",duration:1}),start:0}];
  const cancelled=new api.Mesh();effects.draw(cancelled,.2,actors);assert.equal(cancelled.data.length,0);
});
test("expired cues and a different encounter never replay old hits",()=>{
  const api=setup(),effects=new api.CombatEffects();
  effects.ingest({encounter_number:1,battle:{map:{id:"x"},visual_now:100,visual_events:[{id:1,at:0}]}},[],1);
  assert.equal(effects.events.length,0);
  effects.ingest({encounter_number:2,battle:{map:{id:"x"},visual_now:100,visual_events:[]}},[],2);
  assert.equal(effects.sequence,0);
});

test("turning rotates every body and weapon vertex without mirroring hands",()=>{
 const api=setup(),actor={position:[5,6],look:{id:"chevalier_original",weapon:"arme_sword_shield",color:"#718ea1"},phase:0,moving:false,unit:{}};
 const front=new api.Mesh(),back=new api.Mesh();api.model(front,{...actor,yaw:0},0);api.model(back,{...actor,yaw:Math.PI},0);
 assert.equal(front.data.length,back.data.length);
 for(let i=0;i<front.data.length;i+=6){assert(Math.abs(back.data[i]-(10-front.data[i]))<1e-8);assert(Math.abs(back.data[i+2]-(12-front.data[i+2]))<1e-8);assert.equal(back.data[i+1],front.data[i+1]);}
 assert.equal(back.transform,undefined);
});

test("abstract monster groups are not rendered as inert NPCs",()=>{
 const api=setup(),adventure={players:[],mobs:[],battle:{map:{id:"test",sites:[]},summons:{},companions:{}},living_world:{nearby:[{id:"group",kind:"monsters",map:"test",position:[1,1]},{id:"guard",kind:"guards",role:"archer",map:"test",position:[2,2],name:"Archer"}]}};
 const items=api.actors(adventure,{id:"hero"});assert.equal(items.length,1);assert.equal(items[0].id,"world:guard");
});

test("guard steps remain continuous under irregular updates and stop at the last known point",()=>{
 const {GuardTrack}=setup(),track=new GuardTrack([0,0],0);
 const steps=[[420,[1,0]],[1040,[2,0]],[1570,[3,0]],[2230,[4,0]],[2690,[5,0]],[3340,[6,0]]];
 let next=0,previous=track.sample(0),movingFrames=0;
 for(let now=0;now<=4400;now+=10){
  while(next<steps.length&&steps[next][0]<=now){const [at,position]=steps[next++];track.push(position,at);}
  // Repeated snapshots must not restart interpolation or insert a stop.
  track.push(next?steps[next-1][1]:[0,0],now);
  const position=track.sample(now);
  if(now>1020&&now<4340){assert(position[0]>previous[0],`Guard paused at ${now} ms`);movingFrames++;}
  assert(position[0]>=previous[0]);assert.equal(position[1],0);previous=position;
 }
 assert(movingFrames>300);assert.deepEqual(Array.from(track.sample(8000)),[6,0]);
 for(let now=4500;now<=8000;now+=100)track.push([6,0],now);
 track.push([7,0],8100);assert.deepEqual(Array.from(track.sample(8100)),[6,0]);
 assert(track.sample(9050)[0]>6&&track.sample(9050)[0]<7);
 track.push([25,25],9100);assert.deepEqual(Array.from(track.sample(9100)),[25,25]);
});


test("catalogue species and tools retain distinct finite silhouettes",()=>{
 const api=setup(),content=JSON.parse(fs.readFileSync("projects/authored/content.json","utf8")).content;
 const shapes=new Map();
 for(const [id,sprite] of Object.entries(content.sprites.assets)){
   const mesh=new api.Mesh();api.model(mesh,{position:[0,0],look:{id,weapon:"",color:"#718ea1"},phase:0,moving:false,unit:{}},0);
   assert(mesh.data.length>0&&mesh.data.every(Number.isFinite),id);
   if(sprite.layer!=="weapon")shapes.set(id,JSON.stringify(mesh.data));
 }
 const distinct=["corps_rat","corps_wolf","corps_boar","corps_lizard","corps_crow","corps_bat","corps_spider","corps_scorpion","corps_beetle","corps_mushroom","corps_plant","corps_golem","corps_ghost","corps_flame","corps_slime","corps_skeleton"];
 assert.equal(new Set(distinct.map(id=>shapes.get(id))).size,distinct.length);
 const tools=["sword","dagger","spear","axe","hammer","pick","bow","staff"];
 const geometry=tools.map(kind=>{const mesh=new api.Mesh();api.model(mesh,{position:[0,0],look:{id:"garde_original",weapon:`arme_${kind}`,color:"#718ea1"},phase:0,unit:{}},0);assert(mesh.data.every(Number.isFinite));return JSON.stringify(mesh.data);});
 assert.equal(new Set(geometry).size,tools.length);
});

test("3D actors use equipment and tint from the same binding as their body",()=>{
 const api=setup(),adventure={sprites:{assets:{body:{palette:[null,"#000000","#111111","#123456"]}},bindings:{"npc:local":"body","ambient:resident":"body"},equipment:{"ambient:resident":"arme_axe"},colors:{"ambient:resident":"#ff0000"}},players:[],mobs:[],battle:{map:{id:"test",sites:[{id:"local",name:"Local",position:[1,1]}]},summons:{},companions:{}},living_world:{nearby:[{id:"local",kind:"resident",map:"test",position:[2,2],name:"Local"}]}};
 for(const actor of api.actors(adventure,{id:"hero"})){assert.equal(actor.look.weapon,"");assert.equal(actor.look.color,"#123456");}
});

test("shared crafted weapons override each class weapon while keeping its own body and tint",()=>{
 const api=setup(),players=["Mage","Priest","Necromancien"].map((class_name,index)=>({id:`p${index}`,class_name,name:class_name,hp:20,max_hp:20,gear:[{slot:"weapon",weapon_type:"staff"}]}));
 const adventure={players,mobs:[],sprites:{assets:{body:{palette:[null,"#000000","#111111","#123456"]}},bindings:Object.fromEntries(players.map(p=>[`class:${p.class_name}`,"body"])),equipment:{"class:Mage":"arme_wand","class:Priest":"arme_staff","class:Necromancien":"arme_skull_staff"}},battle:{players:Object.fromEntries(players.map((p,i)=>[p.id,{position:[i,0]}])),map:{id:"test",sites:[]},summons:{},companions:{},corpses:[]}};
 for(const actor of api.actors(adventure,players[0])){assert.equal(actor.look.weapon,"arme_staff");assert.equal(actor.look.id,"body");assert.equal(actor.look.color,"#123456");}
 players[0].gear=[];assert.equal(api.actors(adventure,players[0])[0].look.weapon,"arme_wand");
});

test("terrain follows the displayed camera and covers tall viewports",()=>{
 const api=setup(),map={width:100,height:100,cover:[]};
 const camera={x:48.8,z:41.8,halfW:9,halfH:22};
 const first=api.terrainWindow(camera);
 const moved=api.terrainWindow({...camera,z:42.1});
 assert.equal(moved.z,42);
 assert.notEqual(moved.z,first.z);
 assert(moved.radiusZ>moved.radiusX);
 const mesh=new api.Mesh();api.scenery(mesh,map,null,moved);
 const depths=mesh.data.filter((_,i)=>i%6===2);
 const visibleDepth=camera.halfH/api.cameraAngle.tilt;
 assert(Math.min(...depths)<=42.1-visibleDepth);
 assert(Math.max(...depths)>=42.1+visibleDepth);
 assert(api.terrainWindow({...camera,halfH:9}).radiusZ<moved.radiusZ);
});

test("discovery cache distinguishes different cells with the same count",()=>{
 const {sameExploration}=setup();
 assert(sameExploration(new Set(["1,1","2,2"]),new Set(["2,2","1,1"])));
 assert(!sameExploration(new Set(["1,1"]),new Set(["2,2"])));
 assert(!sameExploration(null,new Set()));
});
