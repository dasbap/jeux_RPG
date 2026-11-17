"use strict";
// Local movement; the engine accepts positions within its server-timed speed budget.
(() => {
  let axis=[0,0],key="",pending=null,inFlight=false,timer=null,lastSent=-Infinity,retryAt=0;
  let predicted=null,lastFrame=0,mapKey="",solids=new Set(),generation=0,lastServerTime=null;
  let controlled=false,correctionPending=false,clockOffset=Infinity,cachedUnit=null;
  let snapshotRevisions=new WeakMap();
  const diagnostics={hardResets:0,staleSnapshots:0,maxCorrectionStep:0,speedRetries:0};
  const context=()=>typeof session!=="undefined"&&session?.tutorial?.battle?`${session.id}:${session.tutorial.encounter_number}:${session.tutorial.field_map||session.tutorial.battle.map.id}`:"";
  function fits(map,p){
    const r=.22,[x,y]=p;
    if(x<-.5+r||y<-.5+r||x>map.width-.5-r||y>map.height-.5-r)return false;
    for(let a=Math.floor(x-r+.5);a<=Math.floor(x+r+.5);a++)for(let b=Math.floor(y-r+.5);b<=Math.floor(y+r+.5);b++){
      if(!solids.has(`${a},${b}`))continue;
      const nx=Math.max(a-.5,Math.min(a+.5,x)),ny=Math.max(b-.5,Math.min(b+.5,y));
      if((x-nx)**2+(y-ny)**2<r*r-1e-9)return false;
    }
    return true;
  }
  function move(map,p,vector,distance){
    const length=Math.hypot(...vector);if(!length)return p;
    let result=[...p];
    for(let left=distance;left>1e-8;left-=.08){
      const step=Math.min(.08,left),next=result.map((v,i)=>v+vector[i]/length*step);
      if(fits(map,next))result=next;
      else for(const candidate of [[next[0],result[1]],[result[0],next[1]]])if(fits(map,candidate)){result=candidate;break;}
    }
    return result;
  }
  function reset(nextKey){key=nextKey;axis=[0,0];predicted=null;pending=null;lastFrame=0;lastSent=-Infinity;retryAt=0;lastServerTime=null;clockOffset=Infinity;cachedUnit=null;mapKey="";solids=new Set();controlled=false;correctionPending=false;snapshotRevisions=new WeakMap();generation++;}
  function snapshotRevision(s){
    if(!s?.tutorial||typeof s.tutorial!=="object")return s?.revision;
    if(!snapshotRevisions.has(s.tutorial))snapshotRevisions.set(s.tutorial,s.revision);
    return snapshotRevisions.get(s.tutorial);
  }
  function accept(previous,next){
    if(!previous||!next||previous.id!==next.id){snapshotRevision(next);return true;}
    const a=previous.tutorial,b=next.tutorial;
    if(a?.battle?.movement_model==="continuous-v1"&&b?.battle?.movement_model==="continuous-v1"&&a.encounter_number!==b.encounter_number){
      if(b.encounter_number<a.encounter_number||next.revision<snapshotRevision(previous)){diagnostics.staleSnapshots++;return false;}
      snapshotRevision(next);return true;
    }
    if(a?.battle?.movement_model==="continuous-v1"&&b?.battle?.movement_model==="continuous-v1"&&a.encounter_number===b.encounter_number&&a.battle.map.id===b.battle.map.id){
      if(next.revision<snapshotRevision(previous)||b.battle.visual_now<a.battle.visual_now-1e-7){diagnostics.staleSnapshots++;return false;}
      snapshotRevision(next);return true;
    }
    if(next.revision<previous.revision)return false;
    snapshotRevision(next);
    return true;
  }
  async function pump(){
    if(inFlight||!pending||performance.now()<retryAt)return;
    if(pending.axis.some(Boolean)&&performance.now()-lastSent<80)return;
    const task=pending;pending=null;
    if(task.key!==context())return;
    inFlight=true;lastSent=performance.now();const epoch=generation,position=task.position||(controlled&&predicted?[...predicted]:null);
    try{
      const s=session,a=s.tutorial;
      const data=await api("/api/commands",{request_id:requestId(),action:task.axis.some(Boolean)?"move_axis":"stop_move",
        params:{session_id:s.id,revision:s.revision,encounter:a.encounter_number,...(position?{position}:{}),...(task.axis.some(Boolean)?{x:task.axis[0],y:task.axis[1]}:{})}});
      if(epoch!==generation||task.key!==context())return;
      if(data.session?.id===session.id&&accept(session,data.session)){
        if(data.session.tutorial){session=data.session;if(typeof renderGame==="function")renderGame(session.tutorial);}
        else session={...session,revision:data.session.revision};
      }
      if(!globalThis.rpgRealtime?.connected)void refresh(true);
    }catch(error){
      if(epoch!==generation)return;
      if(error.code==="stale_encounter")void refresh(true);
      else if(error.code==="movement_speed"){
        // A clock/arrival-time deficit is not proof that the local model moved
        // too fast. Retain the server refusal, retry the same report, never rewind.
        diagnostics.speedRetries++;retryAt=performance.now()+120;
        if(!pending)pending={...task,position};
      }
      else if(["invalid_position","cannot_move"].includes(error.code)){
        correctionPending=true;axis=[0,0];pending=null;void refresh(true);
      }
    }finally{inFlight=false;if(pending)void pump();}
  }
  function tick(){
    if(key!==context()){reset(context());if(timer!==null)clearInterval(timer);timer=null;return;}
    const now=performance.now();
    if(!pending&&axis.some(Boolean)&&now-lastSent>=200)pending={axis:[...axis],key};
    if(pending)void pump();
    if(!axis.some(Boolean)&&!pending&&!inFlight){clearInterval(timer);timer=null;}
  }
  function set(vector){
    const current=context();if(!current)return;
    if(current!==key)reset(current);
    if(!predicted){
      const adventure=session.tutorial,me=adventure.players?.find(p=>p.id===session.me)||{id:session.me,hp:1,stunned:false};
      sync(adventure,me,performance.now());
    }
    const length=Math.max(1,Math.hypot(...vector)),next=vector.map(v=>Math.max(-1,Math.min(1,v/length)));
    const different=next.some((v,i)=>v!==axis[i]);
    if(different){axis=next;if(next.some(Boolean)&&!controlled){controlled=true;lastFrame=performance.now();}pending={axis:[...axis],key};void pump();}
    if(timer===null&&(axis.some(Boolean)||pending||inFlight))timer=setInterval(tick,40);
  }
  function sync(adventure,me,now){
    const current=context();if(current!==key)reset(current);
    if(typeof session!=="undefined"&&session?.tutorial===adventure)snapshotRevision(session);
    const unit=adventure.battle.players[me.id],map=adventure.battle.map;
    const stamp=adventure.battle.visual_now,rules=adventure.battle.motion_rules||{},ratio=rules.ratio||3;
    if(Number.isFinite(lastServerTime)&&Number.isFinite(stamp)&&stamp<lastServerTime-1e-7){diagnostics.staleSnapshots++;return false;}
    const geometry=`${map.id}:${map.terrain_version}:${map.cover.length}:${map.blocked?.length}:${map.water?.length}`;
    if(geometry!==mapKey){
      mapKey=geometry;solids=new Set([...map.cover,...(map.blocked||[]),...(map.water||[]).filter(p=>!map.bridges?.some(b=>b[0]===p[0]&&b[1]===p[1]))].map(p=>p.join()));
    }
    cachedUnit=unit;
    if(Number.isFinite(stamp))clockOffset=Math.min(clockOffset,now-stamp/ratio*1000);
    lastServerTime=stamp;
    if(unit.route?.length&&!axis.some(Boolean))controlled=false;
    if(!predicted||!controlled||correctionPending){
      predicted=[...unit.position];
      if(correctionPending)diagnostics.hardResets++;
      correctionPending=false;
    }
    if(me.hp<=0||me.stunned)axis=[0,0];
    return true;
  }
  function speed(adventure,unit,now){
    const rules=adventure.battle.motion_rules||{},ratio=rules.ratio||3;
    const gameNow=Number.isFinite(clockOffset)?(now-clockOffset)/1000*ratio:adventure.battle.visual_now;
    const slowUntil=Math.max(unit.attack_slow_until||0,unit.casting?.ends_at||0);
    const base=(unit.hidden?(rules.stealth_speed||.4166667):(rules.speed||.8333333))*ratio;
    return base*(gameNow<slowUntil?(rules.attack_factor||.55):1);
  }
  function sample(adventure,me,now){
    if(!predicted||key!==context()||!controlled)return null;
    const unit=cachedUnit||adventure.battle.players[me.id],map=adventure.battle.map;
    const dt=Math.min(.1,Math.max(0,(now-(lastFrame||now))/1000));lastFrame=now;
    if(axis.some(Boolean)&&me.hp>0&&!me.stunned){
      predicted=move(map,predicted,axis,speed(adventure,unit,now)*dt*Math.min(1,Math.hypot(...axis)));
    }
    return [...predicted];
  }
  globalThis.RPGMotion={set,sync,sample,accept,rebase:()=>reset(context()),fits:(map,p)=>fits(map,p),get diagnostics(){return {...diagnostics};},get axis(){return [...axis];},get pending(){return inFlight||!!pending;}};
})();
