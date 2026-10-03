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
  paragraphs("equipment-details", [me.equipment ? `Torse : ${me.equipment}` : "Torse : aucun équipement équipé.", me.equipment ? "Bonus actifs : +10 PV maximum et +3 endurance." : "La forge de Rosée permet de fabriquer votre premier équipement."]);
  const items = Object.entries(me.inventory).filter(([, quantity]) => quantity > 0);
  paragraphs("inventory-details", items.length ? items.map(([item, quantity]) => `${quantity} ${item} · matériau de gobelin pour la veste de la lisière`) : ["Votre inventaire est vide."]);
  const world = adventure.world;
  const places = world.places;
  const locked = busy || Boolean(adventure.mob || adventure.mobs?.length || adventure.moving || adventure.transit || adventure.journey?.length);
  function choosePoint(point) {
    mapPoint = point.id;
    $("map-details").open = !point.can_interact;
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
      const half = route.distance_km / 5 * 3600 / 2;
      const fraction = Math.max(0, Math.min(1, 1 - adventure.travel_remaining_real_seconds * 20 / half));
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
    const choose = () => { mapPlace = p.id; mapPoint = ""; $("map-details").open = true; showView("map"); };
    group.addEventListener("click", choose);
    group.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); choose(); } });
    svg.append(group);
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
    p.textContent = `${route.name} · ${route.distance_km} km · ${(route.distance_km / 5 * 3600 / 20).toFixed(0)} s de marche : ${places.find(p => p.id === route.from).name} ↔ ${places.find(p => p.id === route.to).name}`;
    $("map-routes").append(p);
    if (route.destination && !locked) {
      const button = document.createElement("button");
      button.textContent = `Prendre le chemin vers ${places.find(p => p.id === route.destination).name}`;
      button.disabled = locked;
      button.addEventListener("click", () => tutorialCommand("travel", {destination: route.destination}));
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
    move.addEventListener("click", () => tutorialCommand("move", {destination: point.id}));
    $("point-actions").append(move);
  }
  if (!locked && place.id !== world.current) {
    const move = document.createElement("button");
    move.textContent = `Rejoindre ${place.name}`;
    move.disabled = busy;
    move.addEventListener("click", () => tutorialCommand("move", {destination: place.id}));
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
  for (const mob of world.bestiary) {
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
      `Lieux observés : ${mob.locations.join(", ")}`, mob.materials_usage]) {
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
  const fighting = Boolean(adventure.mob || adventure.mobs?.length);
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
  $("fighters").hidden = !fighting;
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
    if (["clearing", "clearing_fight", "lisiere", "hunt", "training"].includes(adventure.position)) action("tutorial-actions", "Explorer ce lieu", "explore");
  }
  renderWorld(adventure, me);
  $("npc-dialogue").textContent = adventure.step === "village" ? "Mira : des gobelins menacent notre lisière. Pourriez-vous en battre trois ? Gardez leurs peaux et leurs crocs pour la forge." : adventure.quest === "completed" ? "Mira : merci pour votre aide ! La forge est désormais accessible." : adventure.kills < 3 ? `Mira : il reste ${3 - adventure.kills} gobelin(s) à battre dans la lisière.` : "Mira : vous avez vaincu les trois gobelins ! Votre récompense vous attend. Ensuite, faites fabriquer votre veste à la forge.";
  if (canTalk && (adventure.step === "village" || adventure.step === "hunt" && adventure.kills === 3)) action("npc-actions", adventure.step === "village" ? "Accepter la quête" : "Rendre la quête", "talk", {npc: "mira"});
  if (hasQuest) button("quest-actions", "Localiser le lieu de la quête sur la carte", () => { mapPlace = "rosee"; mapPoint = "mira"; showView("map"); });
  $("forge-status").textContent = adventure.quest !== "completed" ? "Forge verrouillée : terminez la quête de Mira et rendez-la sur la place du village." : me.equipment ? "Votre veste est déjà fabriquée et équipée." : "Forge débloquée : vous pouvez fabriquer votre veste si vous avez les matériaux.";
  $("craft-materials").textContent = `Votre sac : ${me.inventory.peau || 0} peau(s), ${me.inventory.croc || 0} croc(s).`;
  if (canCraft) action("craft-actions", "Fabriquer et équiper la veste", "craft", {recipe: "veste"}, (me.inventory.peau || 0) < 2 || (me.inventory.croc || 0) < 3);
  $("mob-name").textContent = fighting ? `Combat ${adventure.encounter_number || 1} · ${(adventure.mobs || []).length} / ${adventure.combat_size || 1} gobelin(s) vivant(s) · rang D` : "";
  $("mob-hp").textContent = fighting ? (adventure.mobs || [adventure.mob]).map(m => `${m.name} : ${m.stats.hp.current}/${m.stats.hp.max} PV`).join(" · ") : "";
  const enemies = fighting ? (adventure.mobs?.length ? adventure.mobs : [{...adventure.mob, combat_id: "mob"}]).map(m => ({id: m.combat_id, name: m.name, hp: m.stats.hp.current, max_hp: m.stats.hp.max, enemy: true})) : [];
  const mob = enemies[0] || null;
  const canAttack = target => Boolean(target.enemy && target.hp > 0 && me.hp > 0 && !me.stunned && me.cooldown_real_seconds <= 0 && me.can_attack);
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
  $("combat-status").textContent = !fighting ? "" : me.hp <= 0 ? "Vous êtes à terre. Votre compagnon peut terminer le combat." : me.cooldown_real_seconds > 0 ? `Prochaine action dans ${me.cooldown_real_seconds.toFixed(1)} s.` : me.stunned ? "Vous êtes étourdi : aucune action n'est disponible." : selected ? "Choisissez une attaque ou une compétence pour cette cible." : "Aucune action disponible sur une cible.";
  if (fighting && me.hp > 0) {
    if (selected && canAttack(selected)) action("combat-actions", "Attaque simple", "strike", {target: selected.id});
    if (selected) for (const skill of me.skills.filter(s => skillAllowed(me, s, selected, mob))) {
      const element = action("skills", `${skill.name} · ${skill.cost} ${skill.energy}`, "skill", {skill_name: skill.name, target: selected.id});
      element.className = "secondary";
      element.title = skill.description;
    }
  }
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
    try {
      data = await api("/api/commands", {request_id: crypto.randomUUID(), action, params});
    } catch (error) {
      if (error.code !== "stale_revision" || !params.session_id) throw error;
      const state = await api("/api/state");
      if (!state.session || state.session.id !== params.session_id) throw error;
      data = await api("/api/commands", {request_id: crypto.randomUUID(), action, params: {...params, revision: state.session.revision}});
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
