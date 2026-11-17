"use strict";
// Keep held input through a zone transition; RPGMotion submits validated positions.
(() => {
  const keys=new Map(),directions={KeyW:[0,-1],KeyZ:[0,-1],ArrowUp:[0,-1],KeyS:[0,1],ArrowDown:[0,1],KeyA:[-1,0],KeyQ:[-1,0],ArrowLeft:[-1,0],KeyD:[1,0],ArrowRight:[1,0]};
  let timer=null,last="",lastSent=0,engaged=false,context="";
  const typing=target=>target?.closest?.("input,textarea,select,[contenteditable=true],dialog[open]");
  function state(){
    const a=typeof session!=="undefined"?session?.tutorial:null;
    if(!a?.battle||a.battle.movement_model!=="continuous-v1"||document.hidden||document.body.classList.contains("hud-menu-open"))return null;
    const me=a.players.find(p=>p.id===session.me);
    return me&&me.hp>0&&!me.stunned?{a,me,key:`${session.id}:${a.encounter_number}:${a.field_map}`} : null;
  }
  function halt(){keys.clear();last="";context="";if(timer!==null)clearInterval(timer);timer=null;}
  function tick(){
    const current=state();
    if(!current){
      if(engaged)globalThis.RPGMotion?.set([0,0]);engaged=false;
      const me=session?.tutorial?.players?.find(p=>p.id===session.me);
      if(!keys.size||document.hidden||document.body.classList.contains("hud-menu-open")||!session||me?.hp<=0||me?.stunned)halt();
      return;
    }
    if(context!==current.key){context=current.key;last="";lastSent=0;engaged=false;}
    let vector=[0,0];for(const v of keys.values())vector=vector.map((x,i)=>Math.max(-1,Math.min(1,x+v[i])));
    const next=vector.join(),now=performance.now();
    if(next==="0,0"){
      if(engaged){if(globalThis.RPGMotion)RPGMotion.set([0,0]);else tutorialCommand("stop_move");engaged=false;}
      halt();return;
    }
    if(globalThis.RPGMotion){RPGMotion.set(vector);context=current.key;engaged=true;if(fieldCamera)fieldCamera.follow=true;return;}
    if(busy||next===last&&now-lastSent<200)return;
    context=current.key;last=next;lastSent=now;engaged=true;
    if(typeof fieldCamera!=="undefined"&&fieldCamera)fieldCamera.follow=true;
    tutorialCommand("move_axis",{x:vector[0],y:vector[1]});
  }
  window.addEventListener("keydown",event=>{
    if(event.target?.closest?.("#touch-stick"))return;
    if(typing(event.target)||event.ctrlKey||event.metaKey||event.altKey||!state())return;
    if(event.code==="Space"){event.preventDefault();if(!event.repeat)globalThis.RPGScene3D?.attack();return;}
    if(!directions[event.code])return;
    event.preventDefault();keys.set(event.code,directions[event.code]);
    if(timer===null)timer=setInterval(tick,40);tick();
  });
  window.addEventListener("keyup",event=>{if(!directions[event.code]||!keys.has(event.code))return;event.preventDefault();keys.delete(event.code);tick();});
  function release(){keys.clear();if(engaged){if(globalThis.RPGMotion)RPGMotion.set([0,0]);else if(!busy)tutorialCommand("stop_move");}engaged=false;halt();}
  window.addEventListener("blur",release);document.addEventListener("visibilitychange",()=>{if(document.hidden)release();});
})();
