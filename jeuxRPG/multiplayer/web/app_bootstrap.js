"use strict";
for (const id of ["bestiary-map", "bestiary-search", "bestiary-sort"]) $(id).addEventListener(id === "bestiary-search" ? "input" : "change", () => { if (session?.tutorial) renderBestiary(session.tutorial); });

const touchControls = globalThis.createRpgTouchControls?.({
  state: () => {
    const adventure = session?.tutorial, actor = adventure?.battle?.players[session.me];
    return {active: Boolean(actor), busy:adventure?.battle?.movement_model==="continuous-v1"?false:busy, continuous:adventure?.battle?.movement_model==="continuous-v1", key: `${session?.id}:${adventure?.encounter_number}`, actor};
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

for (const [view, label] of Object.entries({social:"Social", options:"Options", stats:"Perso.", equipment:"Équip.", inventory:"Sac", quest:"Quêtes", map:"Carte", bestiary:"Bestiaire", achievements:"Succès"})) {
  const button = $("show-" + view);
  button.title = button.textContent;
  button.setAttribute("aria-label", button.textContent);
  button.textContent = label;
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
