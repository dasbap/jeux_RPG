"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("rpg-token") || "";
let session = null;
let sessionId = sessionStorage.getItem("rpg-session") || "";
let busy = false;
let polling = false;
let currentView = "map";
let viewContext = "";
let combatTarget = "";
let mapPlace = "";
let mapPoint = "";
let mapMarker = null;
let focusedMob = "";
const classes = {Knight: "Chevalier", Mage: "Mage", Archer: "Archer", Priest: "Prêtre", Necromancien: "Nécromancien"};
function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}
async function api(path, body, authenticated = true) {
  const headers = {};
  if (authenticated && token) headers.Authorization = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {method: body ? "POST" : "GET", headers, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(5000)});
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.message || "Requête refusée.");
    error.code = data.error;
    throw error;
  }
  return data;
}
function remember() {
  sessionStorage.setItem("rpg-token", token);
  sessionStorage.setItem("rpg-session", sessionId);
}
function render(state) {
  $("registration").hidden = Boolean(token);
  $("lobby").hidden = !token;
  $("player-name").textContent = `${state.player.name} · ${classes[state.player.class_name]}`;
  $("connection").textContent = "Connecté · état partagé";
  $("room-controls").hidden = Boolean(session && session.state !== "finished");
  $("battle").hidden = !session;
  $("invitation").hidden = !(session && session.state === "lobby" && session.owner === session.me && sessionStorage.getItem("rpg-invite-session") === session.id);
  $("tutorial-panel").hidden = !(session && session.tutorial);
  $("character-menu").hidden = !(session && session.tutorial);
  $("duel-target-controls").hidden = true;
  if (!session) return;
  $("battle-title").textContent = {lobby: "En attente du second joueur", running: "Duel en cours", finished: "Duel terminé"}[session.state];
  $("version").textContent = `État ${session.revision}`;
  if (!session.tutorial) $("tutorial-panel").before($("fighters"));
  $("fighters").replaceChildren();
  $("fighters").hidden = Boolean(session.tutorial);
  for (const player of session.tutorial ? session.tutorial.players : session.players) {
    const article = document.createElement("article");
    article.className = `fighter${player.id === session.me ? " mine" : ""}`;
    const title = document.createElement("h3");
    title.textContent = `${player.name}${player.id === session.me ? " · vous" : ""}`;
    const type = document.createElement("div");
    type.className = "class";
    type.textContent = `${classes[player.class_name]}${player.level ? ` · niveau ${player.level}` : ""}`;
    const bar = document.createElement("div");
    bar.className = "health";
    bar.setAttribute("role", "meter");
    bar.setAttribute("aria-label", `Points de vie de ${player.name}`);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", String(player.max_hp));
    bar.setAttribute("aria-valuenow", String(player.hp));
    const fill = document.createElement("div");
    fill.className = "health-fill";
    fill.style.width = `${100 * player.hp / player.max_hp}%`;
    bar.append(fill);
    const hp = document.createElement("div");
    hp.textContent = `${player.hp} / ${player.max_hp} PV`;
    article.append(title, type, bar, hp);
    $("fighters").append(article);
  }
  const me = session.players.find(player => player.id === session.me);
  $("start").hidden = session.state !== "lobby" || session.owner !== session.me;
  $("start").disabled = busy || session.players.length !== 2;
  $("party-tutorial").hidden = session.state !== "lobby" || session.owner !== session.me;
  $("party-tutorial").disabled = busy;
  $("attack").hidden = session.state !== "running";
  $("attack").disabled = busy || me.cooldown_real_seconds > 0;
  $("duel-target").replaceChildren();
  if (!session.tutorial && session.state === "running" && me.hp > 0 && me.cooldown_real_seconds <= 0) {
    for (const opponent of session.players.filter(p => p.id !== session.me && p.hp > 0)) {
      const option = document.createElement("option");
      option.value = opponent.id;
      option.textContent = opponent.name;
      $("duel-target").append(option);
    }
    $("duel-target-controls").hidden = $("duel-target").options.length === 0;
  }
  $("attack").textContent = me.cooldown_real_seconds > 0 ? `Attaque dans ${me.cooldown_real_seconds.toFixed(1)} s` : "Attaquer";
  $("leave").hidden = session.state === "finished";
  $("leave").disabled = busy;
  $("new-room").hidden = session.state !== "finished";
  const winner = session.players.find(player => player.id === session.winner);
  $("result").textContent = session.state === "finished" ? (winner ? `${winner.name} remporte le duel.` : "Session terminée.") : "";
  if (session.tutorial) renderTutorial(session.tutorial);
  $("events").replaceChildren();
  for (const event of session.events) {
    const li = document.createElement("li");
    li.textContent = event.message;
    $("events").append(li);
  }
}
function tutorialCommand(action, params = {}) {
  if (session) return command(action, {session_id: session.id, revision: session.revision, ...params});
}
function paragraphs(container, texts) {
  $(container).replaceChildren();
  for (const text of texts) {
    const p = document.createElement("p");
    p.textContent = text;
    $(container).append(p);
  }
}
function renderWorld(adventure, me) {
  paragraphs("equipment-details", me.gear.length ? me.gear.map(p => `${p.name} +${p.level} · +${p.hp} PV · +${p.endurance} endurance`) : ["Aucun équipement équipé. La forge propose six pièces indépendantes."]);
  const items = Object.entries(me.inventory).filter(([, quantity]) => quantity > 0);
  paragraphs("inventory-details", items.length ? items.map(([item, quantity]) => `${quantity} ${item} · matériau de gobelin pour la forge`) : ["Votre inventaire est vide."]);
  const world = adventure.world;
  const places = world.places;
  const locked = busy || Boolean(adventure.battle || adventure.mob || adventure.mobs?.length || adventure.moving || adventure.transit || adventure.journey?.length);
  function choosePoint(point) {
    mapPoint = point.id;

    if (point.locked_reason) message(point.locked_reason);
    showView("map");
    if (locked || !point.can_interact) return;
    if (point.id === "leon") return tutorialCommand("talk", {npc: "leon"});
    if (adventure.position !== point.id) return tutorialCommand("move", {destination: point.id});
    if (point.action === "explore") return tutorialCommand("explore");
  }
  if (!places.some(p => p.id === mapPlace)) mapPlace = world.current;
  const place = places.find(p => p.id === mapPlace);
  $("map-place").replaceChildren();
  for (const p of places) {
    const option = document.createElement("option");
    option.value = p.id;
    option.textContent = `${p.name} · ${p.visited ? "visité" : "non visité"}`;
    $("map-place").append(option);
  }
  $("map-place").value = mapPlace;
  const namespace = "http://www.w3.org/2000/svg";
  function svgElement(tag, attrs = {}, text = "") {
    const element = document.createElementNS(namespace, tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
    if (text) element.textContent = text;
    return element;
  }
  const svg = svgElement("svg", {viewBox: "0 0 610 260", role: "group", "aria-label": "Carte des lieux et chemins découverts", class: "zone-map"});
  for (const route of world.routes) {
    const from = places.find(p => p.id === route.from);
    const to = places.find(p => p.id === route.to);
    svg.append(svgElement("line", {x1: from.x, y1: from.y, x2: to.x, y2: to.y, class: route.destination ? "known-route accessible-route" : "known-route"}));
    svg.append(svgElement("text", {x: (from.x + to.x) / 2 + (from.x === to.x ? 90 : 0), y: (from.y + to.y) / 2 + (from.x === to.x ? -3 : 38), class: "route-label"}, route.name));
    if (adventure.position === route.id) {
      const half = route.distance_km / 6 * 3600 / 2;
      const fraction = Math.max(0, Math.min(1, 1 - adventure.travel_remaining_real_seconds * 3 / half));
      const forward = adventure.transit?.destination === route.id ? adventure.journey?.[0] === route.to : adventure.transit?.destination === route.to;
      const progress = adventure.transit?.destination === route.id ? fraction / 2 : .5 + fraction / 2;
      const proportion = forward ? progress : 1 - progress;
      const x = from.x + (to.x - from.x) * proportion;
      const y = from.y + (to.y - from.y) * proportion;
      svg.append(svgElement("circle", {cx: x, cy: y, r: 8, class: "visited-node"}));
      svg.append(svgElement("text", {x, y: y - 20, class: "place-label"}, "Vous êtes ici"));
    }
  }
  for (const p of places) {
    const group = svgElement("g", {role: "button", tabindex: "0", "aria-label": `${p.name}, ${p.visited ? "visité" : "non visité"}`, "aria-pressed": String(p.id === mapPlace), class: "map-node"});
    group.append(svgElement("circle", {cx: p.x, cy: p.y, r: p.id === world.current ? 15 : 11, class: p.visited ? "visited-node" : "unknown-node"}));
    group.append(svgElement("text", {x: p.x, y: p.y + 29, class: "place-label"}, p.name));
    if (p.id === world.current && !world.routes.some(r => r.id === adventure.position)) group.append(svgElement("text", {x: p.x, y: p.y - 24, class: "place-label"}, "Vous êtes ici"));
    const choose = () => { mapPlace = p.id; mapPoint = ""; showView("map"); };
    group.addEventListener("click", choose);
    group.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); choose(); } });
    svg.append(group);
  }
  if (mapMarker) {
    const marker = world.objectives.find(m => m.zone === mapMarker.zone && m.point === mapMarker.point);
    if (marker) svg.append(svgElement("circle", {cx: marker.x, cy: marker.y, r: 24, class: "objective-ring", "aria-label": "Objectif à découvrir ou rejoindre"}));
  }
  $("world-map").replaceChildren(svg);
  if (place.points.length) {
    const local = svgElement("svg", {viewBox: "0 0 610 220", role: "group", "aria-label": `Points de ${place.name}`, class: "zone-map"});
    local.append(svgElement("text", {x: 305, y: 20, class: "place-label"}, `Points de ${place.name}`));
    local.append(svgElement("circle", {cx: 70, cy: 110, r: 10, class: "visited-node"}));
    local.append(svgElement("text", {x: 70, y: 138, class: "place-label"}, "Entrée"));
    if (adventure.position === place.id) local.append(svgElement("text", {x: 70, y: 85, class: "place-label"}, "Vous êtes ici"));
    place.points.forEach((point, index) => {
      const x = index % 2 ? 450 : 270;
      const y = index < 2 ? 65 : 175;
      local.append(svgElement("line", {x1: 70, y1: 110, x2: x, y2: y, class: "known-route"}));
      const node = svgElement("g", {role: "button", tabindex: "0", "aria-label": point.name, "aria-disabled": String(locked), "data-point": point.id, class: "map-node"});
      node.append(svgElement("circle", {cx: x, cy: y, r: adventure.position === point.id ? 15 : 10, class: "visited-node"}));
      const icons = {pnj: "●", atelier: "⚒", rencontre: "⚔", repère: "◆"};
      node.append(svgElement("text", {x, y: y + 4, class: "point-icon"}, icons[point.type] || "◆"));
      node.append(svgElement("text", {x, y: y + 25, class: "place-label"}, point.name));
      if (mapMarker?.zone === place.id && mapMarker.point === point.id) node.append(svgElement("circle", {cx: x, cy: y, r: 23, class: "objective-ring"}));
      if (adventure.position === point.id) node.append(svgElement("text", {x, y: y - 25, class: "place-label"}, "Vous êtes ici"));
      const choose = () => choosePoint(point);
      node.addEventListener("click", choose);
      node.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); choose(); } });
      local.append(node);
    });
    $("world-map").append(local);
  }
  paragraphs("place-details", [`${place.name} · ${place.type} · ${place.id === world.current ? "vous êtes ici" : place.visited ? "déjà visité" : "encore non visité"}`, place.description]);
  $("map-routes").replaceChildren();
  for (const route of world.routes.filter(r => r.from === place.id || r.to === place.id)) {
    const p = document.createElement("p");
    p.textContent = `${route.name} · ${route.distance_km} km · ${(route.distance_km / 6 * 3600 / 3).toFixed(0)} s de marche : ${places.find(p => p.id === route.from).name} ↔ ${places.find(p => p.id === route.to).name}`;
    $("map-routes").append(p);
    if (route.destination && !locked) {
      const button = document.createElement("button");
      button.textContent = `Prendre le chemin vers ${places.find(p => p.id === route.destination).name}`;
      button.disabled = locked;
      button.addEventListener("click", () => requestTravel(route.destination, places.find(p => p.id === route.destination).name, route.destination));
      $("map-routes").append(button);
    }
  }
  $("map-points").replaceChildren();
  $("point-actions").replaceChildren();
  for (const point of place.points) {
    const button = document.createElement("button");
    button.textContent = point.name;
    button.className = "secondary";
    button.setAttribute("aria-pressed", String(point.id === mapPoint));
    button.addEventListener("click", () => choosePoint(point));
    $("map-points").append(button);
  }
  const point = place.points.find(p => p.id === mapPoint);
  paragraphs("point-details", point ? [`${point.name} · ${point.type}${adventure.position === point.id ? " · Vous êtes ici" : ""}`, point.description, point.locked_reason || (point.action ? "Une interaction est disponible ici." : adventure.mob ? "Terminez le combat pour interagir avec les lieux." : "Aucune interaction disponible à cette étape.")] : [place.points.length ? "Sélectionnez un point pour consulter ses détails et interactions." : "Les points de ce lieu seront révélés lors de votre visite."]);
  if (!locked && point && adventure.position !== point.id && point.id !== "leon") {
    const move = document.createElement("button");
    move.textContent = "Se déplacer à ce point";
    move.disabled = busy;
    move.addEventListener("click", () => requestTravel(point.id, point.name, place.id));
    $("point-actions").append(move);
  }
  if (!locked && place.id !== world.current) {
    const move = document.createElement("button");
    move.textContent = `Rejoindre ${place.name}`;
    move.disabled = busy;
    move.addEventListener("click", () => requestTravel(place.id, place.name, place.id));
    $("map-routes").append(move);
  }
  if (!locked && point?.action) {
    const button = document.createElement("button");
    button.textContent = point.action === "explore" ? "Explorer ce point" : "Interagir avec ce point";
    button.disabled = busy;
    button.addEventListener("click", () => point.action === "explore" ? tutorialCommand("explore") : showView(point.action === "dialogue" ? "npc" : "craft"));
    $("point-actions").append(button);
  }
  $("bestiary-details").replaceChildren();
  if (!world.bestiary.length) paragraphs("bestiary-details", ["Aucun monstre rencontré. Le bestiaire se complète à chaque découverte."]);
  const damageTypes = {PHYSICAL: "physique", MAGIC: "magique", SACRED: "sacré"};
  const selectedMap = $("bestiary-map").value;
  const maps = [...new Map(world.bestiary.flatMap(m => m.spawn_maps || []).map(m => [m.id, m])).values()];
  $("bestiary-map").replaceChildren();
  const allMaps = document.createElement("option"); allMaps.value = ""; allMaps.textContent = "Toutes les cartes découvertes"; $("bestiary-map").append(allMaps);
  for (const map of maps) { const option = document.createElement("option"); option.value = map.id; option.textContent = map.name; $("bestiary-map").append(option); }
  $("bestiary-map").value = maps.some(m => m.id === selectedMap) ? selectedMap : "";
  $("bestiary-sort-label").hidden = maps.length < 2;
  const query = $("bestiary-search").value.trim().toLocaleLowerCase();
  const filtered = world.bestiary.filter(m => (!$("bestiary-map").value || m.spawn_maps.some(p => p.id === $("bestiary-map").value)) && `${m.name} ${m.loot.map(p => p.item).join(" ")} ${(m.rare_loot || []).map(p => p.item).join(" ")}`.toLocaleLowerCase().includes(query));
  if (world.bestiary.length && !filtered.length) paragraphs("bestiary-details", ["Aucun mob découvert ne correspond à ces filtres."]);
  for (const mob of filtered) {
    const card = document.createElement("article");
    card.className = "codex-card";
    const title = document.createElement("h4");
    title.textContent = `${mob.name} · rang ${mob.rank}`;
    card.append(title);
    for (const text of [mob.description,
      `PV : ${mob.hp.first_encounter} au premier combat, ${mob.hp.hunt} en chasse ou entraînement.`,
      `Force ${mob.stats.force} · Endurance ${mob.stats.endurance} · Intelligence ${mob.stats.intelligence} · Sagesse ${mob.stats.sagesse}`,
      `Faiblesses : ${mob.weaknesses.map(t => damageTypes[t] || t).join(", ") || "aucune"}`,
      `Résistances : ${mob.resistances.map(t => damageTypes[t] || t).join(", ") || "aucune"}`,
      `Matériaux donnés par victoire : ${mob.loot.map(item => `${item.quantity} ${item.item}`).join(", ")}`,
      `Expérience : ${mob.xp.first_encounter} au premier combat, ${mob.xp.hunt} par chasse. Entraînement : aucun butin ni XP.`,
      `Cartes de spawn découvertes : ${[...(mob.spawn_maps || [])].sort((a, b) => a.name.localeCompare(b.name) * ($("bestiary-sort").value === "desc" ? -1 : 1)).map(p => p.name).join(", ")}`,
      `Matériaux rares au dépeçage : ${(mob.rare_loot || []).map(p => `${p.item} (${(100 * p.chance).toFixed(0)} %)`).join(", ")}`, mob.materials_usage]) {
      const p = document.createElement("p");
      p.textContent = text;
      card.append(p);
    }
    $("bestiary-details").append(card);
  }
}
function showView(view) {
  if (["stats", "equipment", "inventory", "map", "bestiary"].includes(view)) currentView = view;
  if (session && session.tutorial) renderTutorial(session.tutorial);
}
function skillAllowed(me, skill, target, mob) {
  if (!mob || me.hp <= 0 || me.stunned || me.cooldown_real_seconds > 0 || !skill.available || skill.cooldown > 0) return false;
  const energy = me.energies.find(e => e.type === skill.energy);
  if (!battleAllowed(session.tutorial, me.id, target.id, skill.range)) return false;
  if (!energy || energy.current < skill.cost || !skill.targets.includes(target.id)) return false;
  if (["DAMAGE", "DEBUFF"].includes(skill.type)) return target.enemy && target.hp > 0;
  if (skill.type === "INVOCATION") return target.id === me.id && me.invocations.length < me.invocation_limit;
  if (target.enemy || target.id !== me.id && !skill.can_target_others) return false;
  if (skill.type === "RESURRECT") return target.hp <= 0;
  if (target.hp <= 0) return false;
  if (skill.type === "HEAL") return target.hp < target.max_hp;
  return skill.type === "BUFF";
}
function renderTutorial(adventure) {
  $("combat-view").prepend($("fighters"));
  const fighting = Boolean(adventure.battle);
  $("combat-layout").hidden = !fighting;
  if (fighting) {
    $("combat-player-panel").append($("combat-view"));
    $("combat-map-panel").append($("map-strip"));
    $("combat-enemy-panel").append($("combat-enemies"));
  } else {
    document.querySelector(".zone-actions").append($("combat-view"));
    $("tutorial-panel").insertBefore($("map-strip"), document.querySelector(".adventure-grid"));
    $("combat-view").append($("combat-enemies"));
  }
  $("battle").classList.toggle("combat-mode", fighting);
  document.body.classList.toggle("combat-active", fighting);
  $("map-help").textContent = fighting ? "Cliquez sur une case pour marcher. Les blocs bruns servent de couverture. Cliquez sur les PV d’un mob pour le localiser." : "Cliquez sur une icône de votre zone pour la rejoindre et interagir. Les autres zones restent consultables.";
  $("character-menu").hidden = fighting;
  $("lobby").hidden = fighting;
  const context = `${session.id}:${adventure.step}:${fighting}:${adventure.encounter_number || 0}`;
  if (context !== viewContext) {
    if (!["stats", "equipment", "inventory", "map", "bestiary"].includes(currentView)) currentView = "map";
    combatTarget = "";
    mapPlace = "";
    mapPoint = "";
    viewContext = context;
  }
  const me = adventure.players.find(player => player.id === session.me);
  const canTalk = adventure.position === "mira" && !fighting && !adventure.moving;
  const atForge = adventure.position === "forge" && !fighting && !adventure.moving;
  const canCraft = atForge && adventure.step === "craft" && !me.equipment;
  const hasQuest = adventure.quest !== "unaccepted";
  $("map-view").hidden = false;
  for (const view of ["stats", "equipment", "inventory", "bestiary"]) $(`${view}-view`).hidden = currentView !== view && !(currentView === "map" && view === "stats");
  $("quest-view").hidden = false;
  $("combat-view").hidden = !fighting;
  $("npc-view").hidden = !canTalk;
  $("craft-view").hidden = !atForge;
  $("standby-view").hidden = fighting || canTalk || atForge;
  $("fighters").hidden = true;
  for (const view of ["stats", "equipment", "inventory", "quest", "map", "bestiary"]) {
    $(`show-${view}`).setAttribute("aria-pressed", String(currentView === view));
  }
  $("back-view").hidden = true;
  $("back-view").textContent = fighting ? "Retour au combat" : "Retour à l'exploration";
  $("battle-title").textContent = adventure.step === "complete" ? "Aventure accomplie" : "Votre tutoriel";
  $("attack").hidden = true;
  $("leave").hidden = true;
  $("result").textContent = adventure.step === "complete" ? "Vous êtes arrivé au village de Brume." : "";
  $("location").textContent = adventure.location;
  $("position-label").textContent = `Vous êtes ici : ${adventure.location}${fighting && adventure.transit ? " · Trajet suspendu pendant le combat" : adventure.moving ? ` · Marche : ${adventure.travel_remaining_real_seconds.toFixed(1)} s avant le prochain point` : ""}`;
  $("objective").textContent = adventure.objective;
  $("quest-progress").textContent = !hasQuest ? "Aucune quête acceptée." : `Quête de Mira : ${{unaccepted: "à accepter", active: `${adventure.kills}/3 gobelins vaincus`, completed: "accomplie"}[adventure.quest]}`;
  $("quest-description").textContent = !hasQuest ? "Explorez les lieux et leurs points stratégiques pour rencontrer des PNJ qui proposent des quêtes." : adventure.quest === "completed" ? "Mira vous a remis votre récompense. Utilisez les matériaux de votre sac pour fabriquer et équiper votre veste à la forge." : "Battez trois gobelins de la lisière, puis revenez parler à Mira à Rosée. Gardez les matériaux pour fabriquer votre veste.";
  $("character-details").replaceChildren();
  for (const text of [
    `Expérience : ${me.exp}/${me.next_level_exp} · niveau ${me.level}`,
    `PV : ${me.hp}/${me.max_hp} · Force ${me.stats.force} · Endurance ${me.stats.endurance} · Intelligence ${me.stats.intelligence} · Sagesse ${me.stats.sagesse}`,
    `Énergie : ${me.energies.map(e => `${e.type} ${e.current}/${e.max}`).join(" · ")}`,
    `Invocations : ${me.invocations.map(i => `${i.name} (${i.hp} PV)`).join(", ") || "aucune"}`,
    `Compétences acquises : ${me.skills.map(s => `${s.name} (${s.cost} ${s.energy})`).join(", ")}`,
    `Prochaines compétences : ${me.upcoming_skills.map(s => `${s.name} au niveau ${s.level}`).join(", ") || "toutes acquises"}`,
  ]) {
    const p = document.createElement("p");
    p.textContent = text;
    $("character-details").append(p);
  }
  for (const id of ["tutorial-actions", "npc-actions", "quest-actions", "craft-actions", "combat-actions", "skills"]) $(id).replaceChildren();
  function button(container, label, handler, disabled = false) {
    const element = document.createElement("button");
    element.textContent = label;
    element.disabled = busy || disabled;
    element.addEventListener("click", handler);
    $(container).append(element);
    return element;
  }
  function action(container, label, name, params = {}, disabled = false) {
    return button(container, label, () => tutorialCommand(name, params), disabled);
  }
  $("standby-title").textContent = adventure.moving ? "En chemin" : "Exploration";
  $("standby-description").textContent = adventure.moving ? "Vous marchez vers votre destination. Une rencontre peut interrompre le trajet." : ["clearing", "clearing_fight", "lisiere", "hunt", "training"].includes(adventure.position) ? "Explorez les alentours pour rencontrer des créatures." : adventure.position === "rosee" ? "Cliquez sur Mira pour parler de sa quête, ou sur la forge pour consulter son accès." : "Choisissez un point sur la carte pour poursuivre votre aventure.";
  if (!fighting && !adventure.moving) {
    for (const route of adventure.world.routes.filter(route => route.destination)) {
      const destination = adventure.world.places.find(place => place.id === route.destination);
      button("tutorial-actions", `Rejoindre ${destination.name}`, () => requestTravel(destination.id, destination.name, destination.id));
    }
    if (["clearing", "clearing_fight", "lisiere", "hunt", "training"].includes(adventure.position)) action("tutorial-actions", "Explorer ce lieu", "explore");
  }
  renderWorld(adventure, me);
  $("npc-dialogue").textContent = adventure.step === "village" ? "Mira : des gobelins menacent notre lisière. Pourriez-vous en battre trois ? Gardez leurs peaux et leurs crocs pour la forge." : adventure.quest === "completed" ? "Mira : merci pour votre aide ! La forge est désormais accessible." : adventure.kills < 3 ? `Mira : il reste ${3 - adventure.kills} gobelin(s) à battre dans la lisière.` : "Mira : vous avez vaincu les trois gobelins ! Votre récompense vous attend. Ensuite, faites fabriquer votre veste à la forge.";
  if (canTalk && (adventure.step === "village" || adventure.step === "hunt" && adventure.kills === 3)) action("npc-actions", adventure.step === "village" ? "Accepter la quête" : "Rendre la quête", "talk", {npc: "mira"});
  button("quest-actions", "Localiser le lieu de la quête", () => { mapMarker = {zone: hasQuest && adventure.kills < 3 ? "lisiere" : "rosee", point: hasQuest && adventure.kills < 3 ? "hunt" : "mira"}; renderTutorial(session.tutorial); message("Le lieu de la quête est entouré sur la carte générale."); });
  $("forge-status").textContent = adventure.quest !== "completed" ? "Forge verrouillée : terminez la quête de Mira et rendez-la sur la place du village." : "Forge débloquée : fabriquez ou améliorez chaque pièce indépendamment jusqu’à +10.";
  $("craft-materials").textContent = `Votre sac : ${Object.entries(me.inventory).map(([item, quantity]) => `${quantity} ${item}`).join(", ") || "aucun matériau"}.`;
  $("forge-catalogue").replaceChildren();
  if (atForge) for (const recipe of me.forge) {
    const card = document.createElement("article"); card.className = "codex-card";
    const title = document.createElement("h4"); title.textContent = recipe.equipped ? `${recipe.equipped.name} +${recipe.equipped.level}` : recipe.name; card.append(title);
    const info = document.createElement("p"); info.textContent = recipe.cost ? `Coût : ${Object.entries(recipe.cost).map(([k,v]) => `${v} ${k}`).join(", ")}` : "Amélioration maximale +10 atteinte."; card.append(info);
    const bonus = document.createElement("p"); bonus.textContent = `Bonus : +${recipe.equipped?.hp ?? recipe.hp} PV, +${recipe.equipped?.endurance ?? recipe.endurance} endurance.`; card.append(bonus);
    const adjective = document.createElement("p"); adjective.textContent = `À +10 : ${recipe.name} ${recipe.adjective}. Chaque pièce s'améliore indépendamment.`; card.append(adjective);
    if (recipe.cost) { const craft = document.createElement("button"); craft.textContent = recipe.equipped ? `Améliorer à +${recipe.equipped.level + 1}` : "Fabriquer et équiper"; craft.disabled = busy || adventure.quest !== "completed" || !recipe.affordable; craft.addEventListener("click", () => tutorialCommand(recipe.equipped ? "upgrade" : "craft", {recipe: recipe.recipe})); card.append(craft); }
    $("forge-catalogue").append(card);
  }
  $("mob-name").textContent = fighting ? `Combat ${adventure.encounter_number || 1} · ${(adventure.mobs || []).length} / ${adventure.combat_size || 1} ennemi(s) visible(s)` : "";
  $("mob-hp").textContent = fighting ? (adventure.mobs || [adventure.mob]).map(m => `${m.name} : ${m.stats.hp.current}/${m.stats.hp.max} PV`).join(" · ") : "";
  const enemies = fighting ? (adventure.mobs ?? (adventure.mob ? [{...adventure.mob, combat_id: "mob"}] : [])).map(m => ({id: m.combat_id, name: m.name, hp: m.stats.hp.current, max_hp: m.stats.hp.max, enemy: true})) : [];
  const mob = enemies[0] || null;
  const canAttack = target => Boolean(target.enemy && target.hp > 0 && me.hp > 0 && !me.stunned && me.cooldown_real_seconds <= 0 && me.can_attack && battleAllowed(adventure, me.id, target.id, me.attack_range));
  const possibleTargets = fighting ? [...enemies, ...adventure.players].filter(target => canAttack(target) || me.skills.some(skill => skillAllowed(me, skill, target, mob))) : [];
  $("combat-target").replaceChildren();
  for (const target of possibleTargets) {
    const option = document.createElement("option");
    option.value = target.id;
    option.textContent = `${target.name}${target.id === me.id ? " · vous" : ""}`;
    $("combat-target").append(option);
  }
  if (possibleTargets.length && !possibleTargets.some(target => target.id === combatTarget)) combatTarget = possibleTargets[0].id;
  $("combat-target").value = possibleTargets.length ? combatTarget : "";
  $("target-controls").hidden = !fighting || possibleTargets.length === 0;
  const selected = possibleTargets.find(target => target.id === combatTarget);
  $("combat-status").textContent = !fighting ? "" : !adventure.battle.hostiles_alive ? "Tous les ennemis sont morts. Approchez les corps pour les dépecer, puis quittez le champ de bataille." : me.hp <= 0 ? "Vous êtes à terre. Votre compagnon peut terminer le combat." : me.cooldown_real_seconds > 0 ? `Prochaine action dans ${me.cooldown_real_seconds.toFixed(1)} s.` : me.stunned ? "Vous êtes étourdi : aucune action n'est disponible." : selected ? "Choisissez une attaque ou une compétence pour cette cible." : "Aucune action disponible sur une cible.";
  if (fighting) renderBattle(adventure, me);
  if (fighting && me.hp > 0) {
    if (selected && canAttack(selected)) action("combat-actions", "Attaque simple", "strike", {target: selected.id});
    if (selected) for (const skill of me.skills.filter(s => skillAllowed(me, s, selected, mob))) {
      const element = action("skills", `${skill.name} · ${skill.cost} ${skill.energy}`, "skill", {skill_name: skill.name, target: selected.id});
      element.className = "secondary";
      element.title = skill.description;
    }
  }
}
function requestTravel(destination, name, zone) {
  if (zone !== session.tutorial.world.current && !window.confirm(`Voulez-vous vous déplacer à ${name} ?`)) return;
  return tutorialCommand("move", {destination});
}
function gridSight(map, source, target) {
  let [x, y] = source;
  const [tx, ty] = target;
  const dx = Math.abs(tx - x), dy = Math.abs(ty - y), sx = x < tx ? 1 : -1, sy = y < ty ? 1 : -1;
  let error = dx - dy;
  while (x !== tx || y !== ty) {
    const twice = error * 2;
    if (twice > -dy) { error -= dy; x += sx; }
    if (twice < dx) { error += dx; y += sy; }
    if (map.cover.some(p => p[0] === x && p[1] === y)) return false;
  }
  return true;
}
function battleAllowed(adventure, player, target, range) {
  if (!adventure?.battle) return false;
  const source = adventure.battle.players[player]?.position;
  const destination = adventure.mobs.find(m => m.combat_id === target)?.position || adventure.battle.players[target]?.position;
  return Boolean(source && destination && Math.hypot(source[0] - destination[0], source[1] - destination[1]) <= range && gridSight(adventure.battle.map, source, destination));
}
function gridPath(map, source, destination) {
  const blocked = (x, y) => x < 0 || y < 0 || x >= map.width || y >= map.height || map.cover.some(p => p[0] === x && p[1] === y);
  if (blocked(...destination)) return null;
  const key = p => p.join(",");
  const queue = [source];
  const parents = new Map([[key(source), null]]);
  for (let index = 0; index < queue.length; index++) {
    const node = queue[index];
    if (key(node) === key(destination)) {
      const result = [];
      let point = node;
      while (parents.get(key(point)) !== null) { result.unshift(point); point = parents.get(key(point)); }
      return result;
    }
    for (const point of [[node[0] + 1, node[1]], [node[0] - 1, node[1]], [node[0], node[1] + 1], [node[0], node[1] - 1]]) {
      if (!blocked(...point) && !parents.has(key(point))) { parents.set(key(point), node); queue.push(point); }
    }
  }
  return null;
}
function renderBattle(adventure, me) {
  const battle = adventure.battle, map = battle.map;
  const unit = battle.players[me.id];
  const disabled = busy || me.hp <= 0 || me.stunned || me.cooldown_real_seconds > 0;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${map.width * 40} ${map.height * 40}`);
  svg.setAttribute("class", "battle-map");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", map.name);
  const element = (tag, attrs, text = "") => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    node.textContent = text;
    return node;
  };
  for (let y = 0; y < map.height; y++) for (let x = 0; x < map.width; x++) {
    const cover = map.cover.some(p => p[0] === x && p[1] === y);
    const cell = element("rect", {x: x * 40, y: y * 40, width: 40, height: 40, class: cover ? "battle-cover" : "battle-cell", role: "button", tabindex: "0", "aria-label": cover ? `Couverture ${x},${y}` : `Marcher en ${x},${y}`, "data-cell": `${x},${y}`});
    const move = () => {
      if (disabled) return;
      const path = gridPath(map, unit.position, [x, y]);
      if (!path?.length) return message("Cette case est occupée par une couverture ou correspond à votre position.");
      tutorialCommand("battle_move", {x, y, path});
    };
    cell.addEventListener("click", move);
    cell.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); move(); } });
    svg.append(cell);
  }
  for (const step of unit.route) svg.append(element("circle", {cx: step[0] * 40 + 20, cy: step[1] * 40 + 20, r: 3, class: "route-dot"}));
  const draw = (id, position, label, className) => {
    const group = element("g", {class: `battle-unit ${className}`, "data-unit": id});
    group.append(element("circle", {cx: position[0] * 40 + 20, cy: position[1] * 40 + 20, r: 13}));
    group.append(element("text", {x: position[0] * 40 + 20, y: position[1] * 40 + 25}, label));
    if (id === focusedMob) group.append(element("circle", {cx: position[0] * 40 + 20, cy: position[1] * 40 + 20, r: 18, class: "objective-ring"}));
    group.addEventListener("click", () => { focusedMob = id; combatTarget = id; renderTutorial(session.tutorial); });
    svg.append(group);
  };
  for (const player of adventure.players) draw(player.id, battle.players[player.id].position, player.id === me.id ? "Vous" : player.name.slice(0, 3), battle.players[player.id].hidden ? "hidden-player" : "visible-player");
  for (const mob of adventure.mobs) draw(mob.combat_id, mob.position, mob.combat_id === "mob" ? "G1" : `G${mob.combat_id.split("-")[1]}`, "enemy-unit");
  for (const corpse of battle.corpses) draw(corpse.id, corpse.position, "✝", "corpse-unit");
  $("world-map").replaceChildren(svg);
  $("mob-cards").replaceChildren();
  for (const mob of adventure.mobs) {
    const card = document.createElement("button"); card.className = "mob-card"; card.dataset.mob = mob.combat_id;
    const title = document.createElement("strong"); title.textContent = `${mob.name} · ${mob.stats.hp.current}/${mob.stats.hp.max} PV`;
    const bar = document.createElement("progress"); bar.max = mob.stats.hp.max; bar.value = mob.stats.hp.current; bar.setAttribute("aria-label", `PV de ${mob.name}`);
    card.append(title, bar);
    card.addEventListener("click", () => { focusedMob = mob.combat_id; combatTarget = mob.combat_id; renderTutorial(session.tutorial); });
    $("mob-cards").append(card);
  }
  paragraphs("combat-resources", adventure.players.map(p => `${p.name} · ${p.hp}/${p.max_hp} PV · ${p.energies.map(e => `${e.type} ${e.current.toFixed(0)}/${e.max}`).join(" · ")}${battle.players[p.id].hidden ? " · dissimulé" : " · visible"}`));
  const table = document.createElement("table");
  for (const intent of battle.intents) {
    const row = document.createElement("tr");
    for (const text of [intent.name, intent.action, intent.remaining_seconds > 0 && /Entaille|Appel/.test(intent.action) ? `${intent.remaining_seconds.toFixed(1)} s` : ""]) { const cell = document.createElement("td"); cell.textContent = text; row.append(cell); }
    table.append(row);
  }
  $("enemy-intents").replaceChildren(table);
  $("tactical-actions").replaceChildren();
  const hide = document.createElement("button"); hide.textContent = unit.hidden ? "Vous êtes dissimulé" : "Se cacher derrière une couverture";
  hide.disabled = disabled || unit.hidden || !map.cover.some(p => Math.hypot(unit.position[0] - p[0], unit.position[1] - p[1]) <= 1.5);
  hide.addEventListener("click", () => tutorialCommand("hide")); $("tactical-actions").append(hide);
  $("corpse-actions").replaceChildren();
  for (const corpse of battle.corpses) {
    const button = document.createElement("button"); button.textContent = corpse.harvested.length ? `${corpse.name} · déjà dépecé` : `Dépecer ${corpse.name}`;
    button.disabled = disabled || corpse.harvested.length > 0 || Math.hypot(unit.position[0] - corpse.position[0], unit.position[1] - corpse.position[1]) > 1.5;
    button.addEventListener("click", () => tutorialCommand("harvest", {target: corpse.id})); $("corpse-actions").append(button);
  }
  if (!adventure.battle.hostiles_alive) { const leave = document.createElement("button"); leave.textContent = "Quitter le champ de bataille"; leave.disabled = disabled; leave.addEventListener("click", () => tutorialCommand("leave_battle")); $("tactical-actions").append(leave); }
}

async function refresh() {
  if (!token) {
    $("connection").textContent = "Prêt · créez votre personnage";
    return;
  }
  if (polling || busy) return;
  polling = true;
  try {
    const state = await api("/api/state");
    if (state.session) {
      session = state.session;
      sessionId = session.id;
    } else if (sessionId) {
      session = await api(`/api/sessions/${sessionId}`);
    } else session = null;
    remember();
    render(state);
  } catch (error) {
    $("connection").textContent = "Connexion interrompue";
    if (error.code === "unauthorized") {
      token = "";
      sessionId = "";
      remember();
      $("registration").hidden = false;
      $("lobby").hidden = true;
      $("battle").hidden = true;
      message("Votre clé n'est plus valide. Reconnectez-vous.", true);
    } else if (error.code === "not_found") {
      sessionId = "";
      session = null;
      remember();
    }
  } finally { polling = false; }
}
async function command(action, params = {}) {
  if (busy) return;
  busy = true;
  if (session?.tutorial) renderTutorial(session.tutorial);
  message("");
  $("attack").disabled = true;
  try {
    let data;
    let currentParams = params;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        data = await api("/api/commands", {request_id: crypto.randomUUID(), action, params: currentParams});
        break;
      } catch (error) {
        if (error.code !== "stale_revision" || !currentParams.session_id || attempt === 4) throw error;
        const state = await api("/api/state");
        if (!state.session || state.session.id !== currentParams.session_id) throw error;
        currentParams = {...currentParams, revision: state.session.revision};
      }
    }
    session = data.session;
    sessionId = session.id;
    remember();
    if (data.invite) {
      sessionStorage.setItem("rpg-invite", data.invite);
      sessionStorage.setItem("rpg-invite-session", session.id);
      $("invite-code").textContent = data.invite;
      $("invitation").hidden = false;
    }
    if (session.state !== "lobby") $("invitation").hidden = true;
  } catch (error) {
    message(error.message, true);
  } finally { busy = false; await refresh(); }
}
$("register-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  try {
    const data = await api("/api/register", {name: $("name").value, class_name: $("class-name").value}, false);
    token = data.token;
    sessionId = "";
    remember();
    message("Personnage créé. Commencez le tutoriel ou invitez un compagnon.");
  } catch (error) { message(error.message, true); }
  finally { busy = false; await refresh(); }
});
$("restore-form").addEventListener("submit", async event => {
  event.preventDefault();
  token = $("restore-token").value.trim();
  sessionId = "";
  remember();
  $("restore-token").value = "";
  await refresh();
});
for (const view of ["stats", "equipment", "inventory", "quest", "map", "bestiary"]) $(`show-${view}`).addEventListener("click", () => showView(view));
$("map-place").addEventListener("change", () => { mapPlace = $("map-place").value; mapPoint = ""; showView("map"); });
$("back-view").addEventListener("click", () => showView(session?.tutorial?.mob ? "combat" : "standby"));
$("combat-target").addEventListener("change", () => {
  combatTarget = $("combat-target").value;
  if (session?.tutorial) renderTutorial(session.tutorial);
});
$("create").addEventListener("click", () => command("create"));
$("tutorial").addEventListener("click", () => command("tutorial"));
$("party-tutorial").addEventListener("click", () => command("tutorial"));
$("join-form").addEventListener("submit", event => {
  event.preventDefault();
  command("join", {invite: $("invite-input").value.trim()});
});
for (const action of ["start", "attack", "leave"]) $(action).addEventListener("click", () => {
  if (session) command(action, {session_id: session.id, revision: session.revision, ...(action === "attack" ? {target: $("duel-target").value} : {})});
});
$("new-room").addEventListener("click", () => command("create"));
$("logout").addEventListener("click", () => {
  token = "";
  session = null;
  sessionId = "";
  for (const key of ["rpg-token", "rpg-session", "rpg-invite", "rpg-invite-session"]) sessionStorage.removeItem(key);
  location.reload();
});
async function copy(text, outputId) {
  try { await navigator.clipboard.writeText(text); message("Copié."); }
  catch { $(outputId).hidden = false; $(outputId).textContent = text; message("Sélectionnez le texte pour le copier."); }
}
$("copy-token").addEventListener("click", () => copy(token, "token-output"));
$("copy-invite").addEventListener("click", () => copy($("invite-code").textContent, "invite-code"));
const invite = sessionStorage.getItem("rpg-invite");
if (invite) { $("invite-code").textContent = invite; $("invitation").hidden = false; }
setInterval(refresh, 500);
refresh();

for (const id of ["bestiary-map", "bestiary-search", "bestiary-sort"]) $(id).addEventListener(id === "bestiary-search" ? "input" : "change", () => { if (session?.tutorial) renderTutorial(session.tutorial); });
