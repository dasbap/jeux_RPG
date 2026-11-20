"use strict";
initAtlasMenus();
for (const id of ["bestiary-map", "bestiary-search", "bestiary-sort"]) $(id).addEventListener(id === "bestiary-search" ? "input" : "change", () => { if (session?.tutorial) renderBestiary(session.tutorial); });
for(const id of ["equipment-slot","equipment-search"])$(id).addEventListener(id==="equipment-search"?"input":"change",()=>{const adventure=session?.tutorial,me=adventure?.players.find(player=>player.id===session.me);if(me)renderEquipment(adventure,me);});
for(const id of ["inventory-kind","inventory-search"])$(id).addEventListener(id==="inventory-search"?"input":"change",()=>{const adventure=session?.tutorial,me=adventure?.players.find(player=>player.id===session.me);if(me)renderInventory(adventure,me);});

const touchControls = globalThis.createRpgTouchControls?.({
  state: () => {
    const adventure = session?.tutorial, actor = adventure?.battle?.players[session.me];
    return {active: Boolean(actor)&&!globalThis.RPGLandscape?.blocked&&!document.body.classList.contains("rpg-loading"), busy:adventure?.battle?.movement_model==="continuous-v1"?false:busy, continuous:adventure?.battle?.movement_model==="continuous-v1", key: `${session?.id}:${adventure?.encounter_number}`, actor};
  },
  move: direction => {
    const adventure = session?.tutorial, actor = adventure?.battle?.players[session.me];
    const me = adventure?.players.find(player => player.id === session.me);
    if (!actor || me.hp <= 0 || me.stunned) return false;
    if(adventure.battle.movement_model==="continuous-v1") {
      if(globalThis.RPGMotion)RPGMotion.set(direction);else tutorialCommand("move_axis",{x:direction[0],y:direction[1]});return true;
    }
    if(busy||me.casting)return false;
    const destination = actor.position.map((value, i) => value + direction[i]);
    const path = gridPath(adventure.battle.map, actor.position, destination);
    if (!path?.length || path.length > 2) return false;
    tutorialCommand("battle_move", {x: destination[0], y: destination[1], path});
    return true;
  },
  stop: () => globalThis.RPGMotion&&session?.tutorial?.battle?.movement_model==="continuous-v1"?RPGMotion.set([0,0]):tutorialCommand("stop_move"),
  actions: () => []
});



if (typeof fetch === 'function') fetch('/api/classes').then(response => { if (!response.ok) throw new Error('Classes indisponibles'); return response.json(); }).then(available => {
  for (const item of available) {
    classes[item.id] = item.name;
    if (![...$('class-name').options].some(option => option.value === item.id)) {
      classes[item.id] = item.name;
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = item.name;
      $('class-name').append(option);
      $('new-character-class').append(option.cloneNode(true));
    }
  }
}).catch(() => {});


$("chat-toggle").addEventListener("click", () => {
  const open = document.body.classList.toggle("chat-open");
  $("chat-toggle").setAttribute("aria-expanded", String(open));
  if (open) $("chat-message").focus();
});
$("chat-channel").addEventListener("change", () => $("chat-panel").classList.toggle("group-chat", $("chat-channel").value === "group"));

for (const [view, label] of Object.entries({social:"Social", options:"Options", stats:"Personnage", equipment:"Équipement", inventory:"Inventaire", quest:"Quêtes", map:"Carte", bestiary:"Bestiaire", achievements:"Succès"})) {
  const button = $("show-" + view);
  button.title = button.textContent;
  button.setAttribute("aria-label", button.textContent);
  button.textContent = label;
  button.replaceChildren(menuIcon({social:"social",options:"settings",stats:"head",equipment:"torso",quest:"quest",bestiary:"beast",inventory:"waist",map:"map",achievements:"star"}[view]),menuNode("span","",label));
}

$("mob-list-toggle").addEventListener("click", () => {
  const collapsed = document.body.classList.toggle("mobs-collapsed");
  $("mob-list-toggle").setAttribute("aria-expanded", String(!collapsed));
  $("mob-list-toggle").setAttribute("aria-label", collapsed ? "Afficher la liste des monstres" : "Réduire la liste des monstres");
});

$("forge-close").addEventListener("click", () => $("craft-view").close());

$("minimap-toggle").addEventListener("click", () => {
  const expanded = $("hud-navigation").classList.toggle("minimap-expanded");
  $("minimap-toggle").setAttribute("aria-expanded", String(expanded));
  $("minimap-toggle").setAttribute("aria-label", expanded ? "Réduire la minicarte" : "Agrandir la minicarte");
});
$("minimap-world").addEventListener("click", () => showView("map", {toggle:false}));

// Routes through the same validated actions as clicks and touch controls.
globalThis.RPGKeybindings=globalThis.createRpgKeybindings?.({
  actions:[
    {id:"attack",name:"Attaquer",key:"Space",combat:true},
    {id:"target",name:"Cible ennemie suivante",key:"Tab",combat:true},
    {id:"harvest_target",name:"Cibler un corps dépeçable",key:"x",combat:true},
    {id:"harvest",name:"Dépecer le corps ciblé / proche",key:"g",combat:true},
    {id:"talk",name:"Parler / examiner à proximité",key:"f",combat:true},
    {id:"inventory",name:"Inventaire",key:"i"},{id:"equipment",name:"Équipement",key:"e"},
    {id:"quest",name:"Journal de quêtes",key:"j"},{id:"map",name:"Carte",key:"m"},
    {id:"bestiary",name:"Bestiaire",key:"b"},{id:"stats",name:"Personnage",key:"c"},
    {id:"options",name:"Options",key:"o"},{id:"social",name:"Social",key:"p"},
    {id:"achievements",name:"Succès",key:"u"},{id:"chat",name:"Ouvrir la discussion",key:"t"},
    {id:"recenter",name:"Recentrer la caméra",key:"r",combat:true},
    {id:"offense",name:"Compétence offensive favorite",key:"1",combat:true},
    {id:"buff",name:"Renforcement favori",key:"2",combat:true},
    {id:"debuff",name:"Affaiblissement favori",key:"3",combat:true},
    {id:"help",name:"Aide des touches",key:"h"},
  ],
  available:action=>{
    const a=session?.tutorial,me=a?.players.find(p=>p.id===session.me);
    if(!a||!me||["social","chat"].includes(action.id)&&gameMode==="solo")return false;
    return !action.combat||!document.body.classList.contains("hud-menu-open")&&me.hp>0&&!me.stunned;
  },
  help:()=>showView("options",{toggle:false}),
  run:(action,direction)=>{
    const a=session.tutorial,me=a.players.find(p=>p.id===session.me);
    if(!action.combat){
      if(action.id==="chat"){globalThis.RPGMotion?.set([0,0]);if(!document.body.classList.contains("chat-open"))$("chat-toggle").click();else $("chat-message").focus();return;}
      if(action.id==="help")return RPGKeybindings.help();globalThis.RPGMotion?.set([0,0]);return showView(action.id);}
    if(action.id==="recenter"){if(a.battle){fieldCamera={...(fieldCamera||{}),follow:true};returnCameraToPlayer();}return;}
    if(action.id==="harvest_target")return cycleHarvestTarget(a,me,direction);
    if(action.id==="harvest")return harvestSelectedCorpse(a,me);
    if(action.id==="target") {
      if(!a.battle)return message("Aucun ennemi à cibler ici.");
      const position=globalThis.RPGMotion?.position?.(a,me.id)||a.battle.players[me.id]?.position;
      if(!position)return;
      const enemies=(a.mobs||[]).filter(m=>m.stats.hp.current>0&&(m.hostile!==false||m.provoked)&&m.position)
        .sort((x,y)=>Math.hypot(x.position[0]-position[0],x.position[1]-position[1])-Math.hypot(y.position[0]-position[0],y.position[1]-position[1])||x.combat_id.localeCompare(y.combat_id));
      if(!enemies.length)return message("Aucun ennemi à cibler ici.");
      const index=enemies.findIndex(m=>m.combat_id===focusedMob);
      const next=enemies[index<0?(direction<0?enemies.length-1:0):(index+direction+enemies.length)%enemies.length];
      // selectEntity toggles a selected entity; a lone target must stay selected.
      if(focusedMob!==next.combat_id)selectEntity(next.combat_id);
      return;
    }
    if(busy)return;
    if(action.id==="talk") {
      if(a.moving)return message("Arrêtez-vous près d'un personnage pour lui parler.");
      const nearby=a.field_interactions||[],points=a.world?.places?.flatMap(p=>p.points||[])||[];
      const site=nearby.find(s=>s.id===focusedMob)||nearby.find(s=>s.dialogue||s.interaction==="inspect"||points.some(p=>p.id===s.id&&p.type==="pnj"))
        ||(!a.battle?points.find(p=>p.id===a.position&&["pnj","indice"].includes(p.type)):null);
      if(!site)return message("Approchez-vous d'un personnage ou d'un objet à examiner.");
      globalThis.RPGMotion?.set([0,0]);return tutorialCommand("talk",{npc:site.id});
    }
    if(!a.battle)return;
    if(action.id==="attack")return globalThis.RPGScene3D?.attack();
    const button=$(`skill-${action.id}`)?.querySelector("button");
    if(button&&!button.disabled&&button.getAttribute("aria-disabled")!=="true")button.click();
    else message("Cette compétence n'est pas disponible.");
  },
});

if(globalThis.RPGKeybindings){
  const help=menuNode("button");help.id="show-keybindings";help.type="button";
  help.append(menuIcon("settings"),menuNode("span","","Raccourcis clavier"));
  help.onclick=()=>RPGKeybindings.help();$("game-menu-items").append(help);
}

const rosterMenuButton=$("choose-character-menu");
if(rosterMenuButton)rosterMenuButton.replaceChildren(menuIcon("head"),menuNode("span","","Mes personnages"));

function harvestCandidates(adventure,me) {
  const position=globalThis.RPGMotion?.position?.(adventure,me.id)||adventure.battle?.players[me.id]?.position;
  if(!position)return [];
  return (adventure.battle?.corpses||[]).filter(c=>!c.harvested?.length&&Object.values(c.loot||{}).some(n=>n>0))
    .map(c=>({...c,distance:Math.hypot(c.position[0]-position[0],c.position[1]-position[1])}))
    .sort((a,b)=>a.distance-b.distance||a.id.localeCompare(b.id));
}
function cycleHarvestTarget(adventure,me,direction=1) {
  const corpses=harvestCandidates(adventure,me);
  if(!corpses.length)return message("Aucun corps dépeçable ici.");
  const index=corpses.findIndex(c=>c.id===focusedMob),next=corpses[index<0?(direction<0?corpses.length-1:0):(index+direction+corpses.length)%corpses.length];
  if(focusedMob!==next.id)selectEntity(next.id);
  message(`Corps ciblé : ${next.name} · ${next.distance.toFixed(1)} cases. ${globalThis.RPGKeybindings?.label("harvest")||"G"} pour dépecer.`);
}
function harvestSelectedCorpse(adventure,me) {
  if(busy||me.casting||!adventure.battle)return;
  const corpses=harvestCandidates(adventure,me),range=adventure.battle.corpse_interact_range??1.5;
  const corpse=corpses.find(c=>c.id===focusedMob)||corpses.find(c=>c.distance<=range);
  if(!corpse)return message(corpses.length?"Approchez-vous d’un corps dépeçable, ou ciblez-le avec le raccourci de ciblage des corps.":"Aucun corps dépeçable ici.");
  if(focusedMob!==corpse.id)selectEntity(corpse.id);
  if(corpse.distance>range){moveControlled(adventure,me,corpse.position);return message("Approche du corps. Dépecez-le une fois à portée.");}
  globalThis.RPGMotion?.set([0,0]);return tutorialCommand("harvest",{target:corpse.id});
}
