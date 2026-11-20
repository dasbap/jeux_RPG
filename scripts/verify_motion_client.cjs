"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const {test}=require("node:test");
function setup({wall=false,casting=false}={}){
  let time=100,interval=null;const calls=[],resolves=[],rejects=[];
  const unit={position:[4,4],route:[],hidden:false,motion_axis:[0,0],motion_until:0,...(casting?{casting:{ends_at:20}}:{})};
  const me={id:"hero",hp:25,stunned:false};
  const adventure={field_map:"arena",encounter_number:1,battle:{movement_model:"continuous-v1",map:{id:"arena",width:20,height:20,cover:wall?[[5,4]]:[],blocked:[],water:[],bridges:[]},visual_now:10,players:{hero:unit},motion_rules:{ratio:3,speed:1/1.2,stealth_speed:1/2.4,attack_factor:.55}}};
  const context=vm.createContext({session:{id:"test",revision:1,me:"hero",tutorial:adventure},busy:true,performance:{now:()=>time},requestId:()=>"motion-request",refresh:async()=>{},
    setInterval:fn=>{interval=fn;return 1;},clearInterval:()=>{interval=null;},api:async(path,body)=>{calls.push(body);return new Promise((resolve,reject)=>{resolves.push(resolve);rejects.push(reject);});}});
  vm.runInContext(fs.readFileSync("jeuxRPG/multiplayer/web/motion_client.js","utf8"),context);
  const motion=context.RPGMotion;motion.sync(adventure,me,time);motion.sample(adventure,me,time);
  return {motion,adventure,me,calls,resolves,rejects,context,setTime:v=>{time=v;},frame:()=>motion.sample(adventure,me,time),tick:()=>interval?.()};
}

test("retreating beyond melee range cannot attack from the last acknowledged position",()=>{
 const s=setup();s.context.busy=false;s.me.attack_range=1.5;
 s.adventure.players=[s.me];s.adventure.mobs=[{combat_id:"enemy",position:[5,4],stats:{hp:{current:20}}}];
 s.context.gridSight=()=>true;
 const battle=fs.readFileSync("jeuxRPG/multiplayer/web/app_battle.js","utf8");
 vm.runInContext(battle.slice(battle.indexOf("function battleAllowed("),battle.indexOf("function gridPath(")),s.context);
 s.motion.set([-1,0]);
 for(let time=116;time<800;time+=16){s.setTime(time);s.frame();}
 assert.equal(s.context.battleAllowed(s.adventure,"hero","enemy",1.5),false);
});

test("combat position reports are exact copies and share ordering with movement packets",async()=>{
 const s=setup();s.motion.set([1,0]);s.setTime(116);const local=s.frame();
 const action=s.motion.report();assert.deepEqual(Array.from(action.position),Array.from(local));assert(action.position_seq>s.calls[0].params.position_seq);
 action.position[0]=999;assert(s.motion.position(s.adventure,"hero")[0]<5);
 s.resolves[0]({session:{id:"test",revision:2,acknowledged:true}});await new Promise(resolve=>setImmediate(resolve));
 s.motion.set([0,0]);assert(s.calls[1].params.position_seq>action.position_seq);
});

test("a speed retry retains its old ordering so it cannot undo a newer attack position",async()=>{
 const s=setup();s.motion.set([1,0]);
 const first=s.calls[0].params.position_seq,attack=s.motion.report();
 s.rejects[0](Object.assign(new Error("Wait"),{code:"movement_speed"}));await new Promise(resolve=>setImmediate(resolve));
 s.setTime(400);s.tick();assert.equal(s.calls[1].params.position_seq,first);assert(first<attack.position_seq);
});

test("a reloaded client continues after the server position sequence",()=>{
 const s=setup();s.adventure.battle.players.hero.position_sequence=500;s.motion.sync(s.adventure,s.me,100);
 s.motion.set([1,0]);assert(s.calls[0].params.position_seq>500);
});
test("a key moves the visual model on the next frame while an action is busy and network reply is delayed",()=>{
  const s=setup(),original=JSON.stringify(s.adventure);
  s.motion.set([1,0]);assert.equal(s.calls.length,1);assert.equal(s.calls[0].action,"move_axis");
  s.setTime(116);const p=s.frame();assert(p[0]>4.03&&p[0]<4.05);
  assert.equal(JSON.stringify(s.adventure),original,"Prediction never modifies authoritative coordinates or combat state");
});
test("rapid reversals are coalesced and releasing a key queues the stop independently of combat",async()=>{
  const s=setup();s.motion.set([1,0]);s.motion.set([-1,0]);s.motion.set([0,0]);
  assert.equal(s.calls.length,1);s.resolves[0]({session:{id:"test",revision:2,acknowledged:true}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(s.calls.length,2);assert.equal(s.calls[1].action,"stop_move");
  assert.deepEqual(Array.from(s.motion.axis),[0,0]);
});
test("prediction respects the same wall radius and casts apply the server slowdown",()=>{
  const wall=setup({wall:true});wall.motion.set([1,0]);
  for(let t=116;t<=308;t+=16){wall.setTime(t);const p=wall.frame();assert(p[0]<=4.280001);}
  const slow=setup({casting:true});slow.motion.set([1,0]);slow.setTime(116);
  assert(Math.abs(slow.frame()[0]-(4+.016*2.5*.55))<1e-6);
});
test("analog changes update visuals immediately but network packets are rate limited",async()=>{
  const s=setup();s.motion.set([1,0]);s.resolves[0]({session:{id:"test",revision:2,acknowledged:true}});
  await new Promise(resolve=>setImmediate(resolve));
  s.setTime(120);s.motion.set([.3,.7]);s.setTime(140);s.motion.set([-.3,.7]);
  assert.equal(s.calls.length,1);assert.deepEqual(Array.from(s.motion.axis),[-.3,.7]);
  s.setTime(181);s.tick();assert.equal(s.calls.length,2);
  assert.equal(s.calls[1].params.x,-.3);assert.equal(s.calls[1].params.y,.7);
});
test("movement keeps its permitted speed without acknowledgement-based braking and resets on map change",()=>{
  const s=setup();s.motion.set([1,0]);s.setTime(116);s.frame();s.setTime(340);const first=s.frame();
  s.setTime(400);const second=s.frame();assert(Math.abs(second[0]-first[0]-.06*2.5)<1e-7);
  s.adventure.field_map="other";s.motion.sync(s.adventure,s.me,410);
  assert.deepEqual(Array.from(s.motion.axis),[0,0]);
});

test("normal server positions do not interfere with a legal local position, even at rest",async()=>{
  const s=setup();s.motion.set([1,0]);
  s.resolves[0]({session:{id:"test",revision:2,acknowledged:true}});await new Promise(resolve=>setImmediate(resolve));
  for(let t=116;t<=292;t+=16){s.setTime(t);s.frame();}
  s.motion.set([0,0]);const previous=s.frame();
  const unit=s.adventure.battle.players.hero;unit.position=[4.10,4];unit.motion_axis=[0,0];s.adventure.battle.visual_now=10.6;
  s.setTime(300);s.motion.sync(s.adventure,s.me,300);const after=s.frame();
  assert(Math.abs(after[0]-previous[0])<.01,"A received position must not teleport the model");
  let last=after;
  for(let t=316;t<=1300;t+=16){s.setTime(t);const p=s.frame();assert(Math.hypot(p[0]-last[0],p[1]-last[1])<=.45*.016+1e-6);last=p;}
  assert.deepEqual(Array.from(last),Array.from(previous));
  assert.equal(s.motion.diagnostics.hardResets,0);
});

test("stale timestamps are rejected even if a packet has a newer revision",()=>{
  const s=setup(),previous=JSON.parse(JSON.stringify(s.context.session)),older=JSON.parse(JSON.stringify(previous));
  older.revision++;older.tutorial.battle.visual_now=9.9;older.tutorial.battle.players.hero.position=[3,4];
  assert.equal(s.motion.accept(previous,older),false);
  assert.equal(s.motion.sync(older.tutorial,s.me,200),false);
  assert.equal(s.frame(),null);
  older.tutorial.encounter_number++;
  assert.equal(s.motion.accept(previous,older),true,"A new encounter has its own clock and coordinates");
});

test("a command acknowledgement does not discard a newer full position snapshot",()=>{
  const s=setup(),acknowledged={...s.context.session,revision:10};
  const next=JSON.parse(JSON.stringify(s.context.session));next.revision=5;next.tutorial.battle.visual_now=10.3;
  assert.equal(s.motion.accept(acknowledged,next),true,"Compare full snapshots independently of metadata acknowledgements");
  const obsolete=JSON.parse(JSON.stringify(next));obsolete.revision=4;obsolete.tutorial.battle.visual_now=10.4;
  assert.equal(s.motion.accept(next,obsolete),false,"An actual snapshot revision regression is still rejected");
});

test("first input after changing zone sends the arrival position before any render",()=>{
  const s=setup();s.adventure.field_map="next";s.adventure.encounter_number++;
  s.adventure.battle.map.id="next";s.adventure.battle.players.hero.position=[14,4];
  s.motion.set([1,0]);
  assert.deepEqual(Array.from(s.calls[0].params.position),[14,4]);
  assert.equal(s.calls[0].params.encounter,2);
  s.setTime(116);assert(s.frame()[0]>14&&s.frame()[0]<14.05);
});

test("new zone snapshots bypass metadata acknowledgements; older zones never return",()=>{
  const s=setup(),previous={...s.context.session,revision:10},next=JSON.parse(JSON.stringify(s.context.session));
  next.revision=5;next.tutorial.encounter_number=2;next.tutorial.field_map="next";next.tutorial.battle.map.id="next";
  assert.equal(s.motion.accept(previous,next),true);
  const old=JSON.parse(JSON.stringify(s.context.session));old.revision=99;
  assert.equal(s.motion.accept(next,old),false,"Even a higher metadata revision cannot restore a previous encounter");
});

test("release sends the exact local stopping position for validation",async()=>{
  const s=setup();s.motion.set([1,0]);s.setTime(116);s.frame();
  s.resolves[0]({session:{id:"test",revision:2,acknowledged:true}});await new Promise(resolve=>setImmediate(resolve));
  s.motion.set([0,0]);
  const position=s.calls[1].params.position;
  assert(position[0]>4);assert.equal(s.calls[1].action,"stop_move");
  assert.equal(s.motion.diagnostics.maxCorrectionStep,0);
});

test("a terrain rejection permits a correction, unlike a temporary speed allowance deficit",async()=>{
  const s=setup();s.motion.set([1,0]);s.setTime(116);s.frame();
  s.rejects[0](Object.assign(new Error("Rejected"),{code:"invalid_position"}));
  await new Promise(resolve=>setImmediate(resolve));
  s.adventure.battle.visual_now=10.3;s.motion.sync(s.adventure,s.me,120);
  assert.deepEqual(Array.from(s.frame()),[4,4]);
  assert.equal(s.motion.diagnostics.hardResets,1);
});

test("a speed refusal retries the same report without rewinding or cancelling held input",async()=>{
  const s=setup();s.motion.set([1,0]);s.setTime(116);const before=s.frame();
  s.rejects[0](Object.assign(new Error("Delayed"),{code:"movement_speed"}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(Array.from(s.motion.axis),[1,0]);assert.equal(s.calls.length,1);
  s.setTime(240);s.tick();assert.equal(s.calls.length,2);
  assert.deepEqual(Array.from(s.calls[1].params.position),[4,4],"Retry the original report instead of chasing the moving model");
  assert(s.frame()[0]>=before[0]);assert.equal(s.motion.diagnostics.hardResets,0);
});

test("jittery snapshots cannot pull a walking model backwards each packet",async()=>{
  const s=setup();s.motion.set([1,0]);
  s.resolves[0]({session:{id:"test",revision:2,acknowledged:true}});await new Promise(resolve=>setImmediate(resolve));
  const unit=s.adventure.battle.players.hero;unit.motion_axis=[1,0];unit.motion_until=20;
  let last=[4,4];
  for(let t=116;t<=580;t+=16){
    s.setTime(t);
    if((t-116)%96===0){
      // Samples represent past positions, with varying delivery delay.
      const age=(t%3)*24+64,serverAt=Math.max(100,t-age);
      s.adventure.battle.visual_now=10+(serverAt-100)/1000*3;
      unit.position=[4+(serverAt-100)/1000*2.5,4];
      s.motion.sync(s.adventure,s.me,t);
    }
    const p=s.frame();assert(p[0]>=last[0]-1e-7,`Backward frame at ${t}: ${last[0]} -> ${p[0]}`);last=p;
  }
  assert(last[0]>4.6);assert.equal(s.motion.diagnostics.hardResets,0);
  assert(s.motion.diagnostics.maxCorrectionStep<=.65*.016+1e-7);
});
