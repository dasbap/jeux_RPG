"use strict";
// Keep held input through a zone transition; RPGMotion submits validated positions.
(() => {
  const keys=new Map(),directions={KeyW:[0,-1],KeyZ:[0,-1],ArrowUp:[0,-1],KeyS:[0,1],ArrowDown:[0,1],KeyA:[-1,0],KeyQ:[-1,0],ArrowLeft:[-1,0],KeyD:[1,0],ArrowRight:[1,0]};
  let timer=null,last="",lastSent=0,engaged=false,context="";
  const typing=target=>target?.closest?.('input,textarea,select,[contenteditable]:not([contenteditable="false"]),dialog[open]');
  function state(){
    const a=typeof session!=="undefined"?session?.tutorial:null;
    if(document.body.classList.contains("rpg-loading")||typing(document.activeElement)||document.querySelector("dialog[open]")||!a?.battle||a.battle.movement_model!=="continuous-v1"||document.hidden||document.body.classList.contains("hud-menu-open"))return null;
    const me=a.players.find(p=>p.id===session.me);
    return me&&me.hp>0&&!me.stunned?{a,me,key:`${session.id}:${a.encounter_number}:${a.field_map}`} : null;
  }
  function halt(){keys.clear();last="";context="";if(timer!==null)clearInterval(timer);timer=null;}
  function tick(){
    const current=state();
    if(!current){
      if(engaged)globalThis.RPGMotion?.set([0,0]);engaged=false;
      const me=session?.tutorial?.players?.find(p=>p.id===session.me);
      if(!keys.size||document.body.classList.contains("rpg-loading")&&document.body.dataset.loadingScene!=="true"||typing(document.activeElement)||document.querySelector("dialog[open]")||document.hidden||document.body.classList.contains("hud-menu-open")||!session||me?.hp<=0||me?.stunned)halt();
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
    if(event.defaultPrevented||event.target?.closest?.("#touch-stick"))return;
    if(typing(event.target)||event.ctrlKey||event.metaKey||event.altKey||!state())return;
    if(event.code==="Space"){if(globalThis.RPGKeybindings)return;event.preventDefault();if(!event.repeat)globalThis.RPGScene3D?.attack();return;}
    if(!directions[event.code])return;
    event.preventDefault();keys.set(event.code,directions[event.code]);
    if(timer===null)timer=setInterval(tick,40);tick();
  });
  window.addEventListener("keyup",event=>{if(!directions[event.code]||!keys.has(event.code))return;event.preventDefault();keys.delete(event.code);tick();});
  function release(){keys.clear();if(engaged){if(globalThis.RPGMotion)RPGMotion.set([0,0]);else if(!busy)tutorialCommand("stop_move");}engaged=false;halt();}
  window.addEventListener("blur",release);document.addEventListener("visibilitychange",()=>{if(document.hidden)release();});
})();
"use strict";
// A single action dispatcher keeps custom bindings out of gameplay validation.
globalThis.createRpgKeybindings = api => {
  const storageKey="rpg-keybindings-v1", actions=api.actions, defaults=Object.fromEntries(actions.map(a=>[a.id,a.key]));
  const reserved=new Set(["z","q","s","d","w","a","Enter","Escape"]);
  const valid=key=>typeof key==="string" && !reserved.has(key) && (/^[a-z0-9]$/.test(key)||["Space","Tab"].includes(key));
  const keyOf=event=>event.code==="Space"?"Space":event.key==="Tab"||event.code==="Tab"?"Tab":/^Digit[0-9]$/.test(event.code)?event.code.slice(-1):event.key?.toLowerCase();
  const label=key=>({Space:"Espace",Tab:"Tab"}[key]||key?.toUpperCase()||"");
  let bindings={...defaults},editing=null;
  try {
    const saved=JSON.parse(localStorage.getItem(storageKey));
    if(saved && typeof saved==="object") {
      const candidate={},used=new Set();
      for(const action of actions)if(valid(saved[action.id])&&!used.has(saved[action.id])){candidate[action.id]=saved[action.id];used.add(saved[action.id]);}
      for(const action of actions)if(!candidate[action.id]){const key=[action.key,..."abcdefghijklmnopqrstuvwxyz0123456789","Space","Tab"].find(key=>valid(key)&&!used.has(key));candidate[action.id]=key;used.add(key);}
      if(Object.values(candidate).every(valid))bindings=candidate;
    }
  } catch {}
  const panel=document.createElement("section");panel.id="keybindings";panel.className="keybindings";
  const heading=document.createElement("h4");heading.textContent="Raccourcis clavier";heading.tabIndex=-1;
  const description=document.createElement("p");description.textContent="Cliquez sur une touche pour la remplacer. Échap annule. Déplacements : ZQSD, WASD ou flèches ; Échap ouvre ou ferme les menus. Maj + ciblage parcourt les ennemis ou les corps en sens inverse.";
  const status=document.createElement("p");status.id="keybinding-status";status.setAttribute("role","status");status.setAttribute("aria-live","polite");
  const list=document.createElement("div");list.className="keybinding-list";
  const buttons=new Map();
  for(const action of actions) {
    const row=document.createElement("div");row.className="keybinding-row";
    const name=document.createElement("span");name.textContent=action.name;
    const button=document.createElement("button");button.type="button";button.dataset.binding=action.id;
    button.onclick=()=>{editing=action.id;update();status.textContent=`Nouvelle touche pour « ${action.name} » ? Échap pour annuler.`;};
    buttons.set(action.id,button);row.append(name,button);list.append(row);
  }
  const reset=document.createElement("button");reset.type="button";reset.className="secondary";reset.textContent="Rétablir les touches par défaut";
  reset.onclick=()=>{bindings={...defaults};editing=null;save();update();status.textContent="Touches par défaut rétablies.";};
  panel.append(heading,description,list,status,reset);document.getElementById("options-view")?.append(panel);
  function save(){try{localStorage.setItem(storageKey,JSON.stringify(bindings));}catch{status.textContent="Touches actives pour cette session ; stockage local indisponible.";}}
  function update(){
    for(const action of actions) {
      const button=buttons.get(action.id);button.textContent=editing===action.id?"Appuyez sur une touche…":label(bindings[action.id]);
      button.setAttribute("aria-label",`${action.name} : ${label(bindings[action.id])}, modifier`);button.setAttribute("aria-pressed",String(editing===action.id));
      const menu=document.getElementById(`show-${action.id}`);
      if(menu){menu.title=`${action.name} (${label(bindings[action.id])})`;menu.setAttribute("aria-keyshortcuts",bindings[action.id]==="Space"?"Space":label(bindings[action.id]));}
    }
  }
  function bind(id,key){
    if(!valid(key)){status.textContent="Touche réservée au déplacement, au dialogue ou au navigateur. Choisissez une lettre, un chiffre, Espace ou Tab.";return false;}
    const conflict=actions.find(a=>a.id!==id&&bindings[a.id]===key);
    if(conflict){status.textContent=`${label(key)} est déjà utilisée pour « ${conflict.name} ».`;return false;}
    bindings[id]=key;editing=null;status.textContent="Raccourci enregistré.";save();update();return true;
  }
  function help(){api.help();panel.scrollIntoView?.({block:"start",behavior:"smooth"});heading.focus({preventScroll:true});}
  function keydown(event){
    if(document.body.classList.contains("rpg-loading"))return;
    if(editing){
      event.preventDefault();event.stopImmediatePropagation();
      if(event.repeat)return;
      if(event.key==="Escape"){editing=null;update();status.textContent="Modification annulée.";return;}
      if(event.ctrlKey||event.metaKey||event.altKey||event.shiftKey){status.textContent="Choisissez une touche seule, sans modificateur.";return;}
      bind(editing,keyOf(event));return;
    }
    if(document.body.classList.contains("rpg-loading")||event.defaultPrevented||event.isComposing||event.ctrlKey||event.metaKey||event.altKey||document.hidden)return;
    if(event.target?.closest?.('input,textarea,select,[contenteditable]:not([contenteditable="false"]),dialog[open]')||document.querySelector("dialog[open]"))return;
    const key=keyOf(event),action=actions.find(a=>bindings[a.id]===key);
    if(!action||event.shiftKey&&!["target","harvest_target"].includes(action.id)&&!/^Digit/.test(event.code))return;
    // Preserve native button activation and keyboard focus navigation in menus.
    if(key==="Space"&&event.target?.closest?.('button,a,summary,[role="button"]'))return;
    if(!api.available(action))return;
    event.preventDefault();event.stopImmediatePropagation();
    if(!event.repeat)api.run(action,["target","harvest_target"].includes(action.id)&&event.shiftKey?-1:1);
  }
  function cancelCapture(event){if(editing&&!panel.contains(event.target)){editing=null;update();status.textContent="Modification annul?e.";}}
  window.addEventListener("pointerdown",cancelCapture,true);
  window.addEventListener("keydown",keydown,true);update();
  return {label:id=>label(bindings[id]),bind,help,panel,
    hint:()=>`${label(bindings.attack)} : attaque · ${label(bindings.target)} : cible · ${label(bindings.talk)} : parler · ${label(bindings.harvest)} : dépecer · ${label(bindings.harvest_target)} : corps · ${label(bindings.inventory)} : sac · ${label(bindings.help)} : touches`,
    destroy:()=>{window.removeEventListener("keydown",keydown,true);window.removeEventListener("pointerdown",cancelCapture,true);panel.remove();}};
};
