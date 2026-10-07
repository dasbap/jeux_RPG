"use strict";
for (const id of ["bestiary-map", "bestiary-search", "bestiary-sort"]) $(id).addEventListener(id === "bestiary-search" ? "input" : "change", () => { if (session?.tutorial) renderTutorial(session.tutorial); });

const touchControls = globalThis.createRpgTouchControls?.({
  state: () => {
    const adventure = session?.tutorial, actor = adventure?.battle?.players[session.me];
    return {active: Boolean(actor), busy, key: `${session?.id}:${adventure?.encounter_number}`, actor};
  },
  move: direction => {
    const adventure = session?.tutorial, actor = adventure?.battle?.players[session.me];
    const me = adventure?.players.find(player => player.id === session.me);
    if (!actor || busy || me.hp <= 0 || me.stunned || me.casting) return false;
    const destination = actor.position.map((value, i) => value + direction[i]);
    const path = gridPath(adventure.battle.map, actor.position, destination);
    if (!path?.length || path.length > 2) return false;
    tutorialCommand("battle_move", {x: destination[0], y: destination[1], path});
    return true;
  },
  stop: () => tutorialCommand("stop_move"),
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
