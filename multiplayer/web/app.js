"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("rpg-token") || "";
let session = null;
let sessionId = sessionStorage.getItem("rpg-session") || "";
let busy = false;
let polling = false;
let nextRefreshAt = 0;
let refreshFailures = 0;
let lastPlayer = null;
let stateEpoch = 0;
let pendingBattleMove = null;
let currentView = "map";
let viewContext = "";
let combatTarget = "";
let mapPlace = "";
let mapPoint = "";
let mapMarker = null;
let focusedMob = "";
let tacticalInteractionUntil = 0;
let inspectedCell = null;
const classes = {Knight: "Chevalier", Mage: "Mage", Archer: "Archer", Priest: "Prêtre", Necromancien: "Nécromancien"};
function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}
function requestId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(value => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
function invitationCode(value) {
  const trimmed = value.trim();
  try { return new URL(trimmed).hash.match(/^#invite=([A-Za-z0-9_-]{16,64})$/)?.[1] || trimmed; }
  catch { return trimmed; }
}
function invitationLink(code) {
  const url = new URL(location.href);
  url.hash = `invite=${code}`;
  url.search = "";
  return url.href;
}
async function api(path, body, authenticated = true) {
  const headers = {Accept: "application/json"};
  if (authenticated && token) headers.Authorization = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";
  if (location.hostname.endsWith(".devtunnels.ms")) headers["X-Tunnel-Skip-AntiPhishing-Page"] = "true";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(path, {method: body ? "POST" : "GET", headers, body: body ? JSON.stringify(body) : undefined, signal: controller.signal, cache: "no-store"});
    let data;
    try { data = await response.json(); }
    catch { throw Object.assign(new Error("Le tunnel ne renvoie pas l’API du jeu. Vérifiez son accès et relancez la connexion."), {code: "tunnel_response"}); }
    if (!response.ok) {
      const error = new Error(data.message || "Requête refusée.");
      error.code = data.error;
      throw error;
    }
    return data;
  } catch (error) {
    if (controller.signal.aborted) throw Object.assign(new Error(body ? "Réponse trop lente. L’action a peut-être été reçue ; actualisation de l’état en cours." : "Le serveur ou le tunnel répond trop lentement. Reconnexion automatique en cours."), {code: "timeout"});
    if (error instanceof TypeError) throw Object.assign(new Error("Connexion au serveur indisponible. Vérifiez le tunnel et votre réseau."), {code: "network"});
    throw error;
  } finally { clearTimeout(timeout); }
}

function remember() {
  sessionStorage.setItem("rpg-token", token);
  sessionStorage.setItem("rpg-session", sessionId);
}
function renderChat(chat) {
  $("chat-panel").hidden = !token;
  if (!chat) return;
  $("online-players").textContent = `En ligne : ${chat.online.map(player => player.name).join(", ") || "personne"}`;
  $("chat-channel").querySelector('[value="group"]').disabled = !session;
  if (!session && $("chat-channel").value === "group") $("chat-channel").value = "global";
  for (const channel of ["global", "group"]) {
    const list = $(`chat-${channel}`), follow = list.scrollTop + list.clientHeight >= list.scrollHeight - 20;
    const messages = chat[channel] || [];
    const retained = new Set(messages.map(item => String(item.id)));
    for (const child of [...list.children]) if (!retained.has(child.dataset.id)) child.remove();
    for (const item of messages) {
      if ([...list.children].some(child => child.dataset.id === String(item.id))) continue;
      const row = document.createElement("li"); row.dataset.id = item.id; row.textContent = `${item.name} : ${item.message}`; list.append(row);
    }
    if (follow) list.scrollTop = list.scrollHeight;
  }
}
function renderAchievements(data) {
  if (!data) return;
  $("achievement-summary").textContent = `Niveau maximum ${data.max_level} · ${data.kills} créature(s) vaincue(s) · meilleur temps ${data.best_seconds === null ? "—" : data.best_seconds.toFixed(1) + " s"}`;
  $("achievement-rows").replaceChildren();
  for (const item of data.rows) {
    const row = document.createElement("tr"); row.className = item.unlocked ? "achievement-unlocked" : "";
    for (const text of [item.name, item.progress, item.title]) { const cell = document.createElement("td"); cell.textContent = text; row.append(cell); }
    $("achievement-rows").append(row);
  }
  $("achievement-titles").textContent = `Titres obtenus : ${data.unlocked_titles.join(" · ") || "aucun"}`;
}
function render(state) {
  lastPlayer = state.player;
  renderChat(state.chat);
  $("registration").hidden = Boolean(token);
  $("lobby").hidden = !token;
  $("player-name").textContent = `${state.player.name} · ${classes[state.player.class_name]}`;
  $("connection").textContent = "Connecté · état partagé";
  $("room-controls").hidden = Boolean(session && session.state !== "finished");
  $("battle").hidden = !session;
  $("invitation").hidden = !(session && session.state === "lobby" && session.owner === session.me && sessionStorage.getItem("rpg-invite-session") === session.id);
  if (!$("invitation").hidden) {
    const code = sessionStorage.getItem("rpg-invite") || "";
    $("invite-code").textContent = code;
    $("invite-link").value = invitationLink(code);
    $("invite-status").textContent = `Invitation valable encore ${Math.ceil(session.remaining_real_seconds / 60)} min · ${session.players.length}/2 joueurs. Attendez votre compagnon avant de démarrer.`;
  }
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
  $("party-tutorial").disabled = busy || session.players.length !== 2;
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
  if (session) return command(action, {session_id: session.id, revision: session.revision, ...(["battle_move", "unit_order"].includes(action) ? {encounter: session.tutorial.encounter_number} : {}), ...(["move", "travel", "explore"].includes(action) && session.tutorial.world_context ? {world_context: session.tutorial.world_context} : {}), ...params});
}
function paragraphs(container, texts) {
  $(container).replaceChildren();
  for (const text of texts) {
    const p = document.createElement("p");
    p.textContent = text;
    $(container).append(p);
  }
}
function mountWorldMap(source) {
  const container = $("world-map");
  const retained = [...container.children].find(node => node.dataset.map === source.dataset.map);
  if (!retained) { container.append(source); return source; }
  function update(target, fresh) {
    for (const attr of [...target.attributes]) target.removeAttribute(attr.name);
    for (const attr of fresh.attributes) target.setAttribute(attr.name, attr.value);
    target.onclick = fresh.onclick; target.ondblclick = fresh.ondblclick; target.onkeydown = fresh.onkeydown;
    if (!fresh.children.length) { target.textContent = fresh.textContent; return; }
    const old = [...target.children];
    const kept = [...fresh.children].map((child, index) => {
      const destination = child.dataset.destination, point = child.dataset.point;
      const existing = destination ? old.find(node => node.dataset.destination === destination) : point ? old.find(node => node.dataset.point === point) : old[index]?.tagName === child.tagName && !old[index].dataset.destination && !old[index].dataset.point ? old[index] : null;
      if (existing) { update(existing, child); return existing; }
      return child;
    });
    for (const child of old) if (!kept.includes(child)) child.remove();
    for (const child of kept) if (child.parentElement !== target) target.append(child);
  }
  update(retained, source);
  return retained;
}
function equipmentBonuses(piece) {
  return [["hp", "PV"], ["endurance", "endurance"], ["force", "force"], ["intelligence", "intelligence"], ["sagesse", "sagesse"]].filter(([key]) => piece[key] > 0).map(([key, label]) => `+${piece[key]} ${label}`).join(" · ");
}
function renderWorld(adventure, me) {
  paragraphs("equipment-details", me.gear.length ? me.gear.map(p => `${p.name} +${p.level} · ${equipmentBonuses(p)}`) : ["Aucun équipement équipé. La forge propose six pièces indépendantes."]);
  const items = Object.entries(me.inventory).filter(([, quantity]) => quantity > 0);
  paragraphs("inventory-details", items.length ? items.map(([item, quantity]) => `${quantity} ${item} · matériau de gobelin pour la forge`) : ["Votre inventaire est vide."]);
  const world = adventure.world;
  const places = world.places;
  const locked = busy || Boolean(adventure.battle || adventure.mob || adventure.mobs?.length);
  function choosePoint(point) {
    mapPoint = point.id;
    if (point.locked_reason) message(point.locked_reason);
    showView("map");
  }
  function visitPoint(point) {
    if (locked) return;
    if (point.id === "leon" && point.can_interact) return tutorialCommand("talk", {npc: "leon"});
    if (adventure.position !== point.id || adventure.moving) return requestTravel(point.id);
    if (point.locked_reason) return message(point.locked_reason);
    if (point.action === "explore") return tutorialCommand("explore");
    choosePoint(point);
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
      const endpoint = id => id === route.from ? 0 : id === route.to ? 1 : .5;
      const transit = adventure.transit;
      const proportion = transit?.source && [route.from,route.to,route.id].includes(transit.source) && [route.from,route.to,route.id].includes(transit.destination) ? endpoint(transit.source) + (endpoint(transit.destination) - endpoint(transit.source)) * Math.max(0,Math.min(1,1 - adventure.travel_remaining_real_seconds * 3 / transit.total)) : forward ? progress : 1 - progress;
      const x = from.x + (to.x - from.x) * proportion;
      const y = from.y + (to.y - from.y) * proportion;
      svg.append(svgElement("circle", {cx: x, cy: y, r: 8, class: "visited-node"}));
      svg.append(svgElement("text", {x, y: y - 20, class: "place-label"}, "Vous êtes ici"));
    }
  }
  for (const p of places) {
    const group = svgElement("g", {role: "button", tabindex: "0", "aria-label": `${p.name}, ${p.visited ? "visité" : "non visité"}`, "aria-pressed": String(p.id === mapPlace), class: "map-node", "data-destination": p.id});
    group.append(svgElement("circle", {cx: p.x, cy: p.y, r: p.id === world.current ? 15 : 11, class: p.visited ? "visited-node" : "unknown-node"}));
    group.append(svgElement("text", {x: p.x, y: p.y + 29, class: "place-label"}, p.name));
    if (p.id === world.current && !world.routes.some(r => r.id === adventure.position)) group.append(svgElement("text", {x: p.x, y: p.y - 24, class: "place-label"}, "Vous êtes ici"));
    const choose = () => { mapPlace = p.id; mapPoint = ""; showView("map"); };
    group.onclick = choose;
    group.ondblclick = () => requestTravel(p.id);
    group.onkeydown = event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); requestTravel(p.id); } };
    svg.append(group);
  }
  if (mapMarker) {
    const marker = world.objectives.find(m => m.zone === mapMarker.zone && m.point === mapMarker.point);
    if (marker) svg.append(svgElement("circle", {cx: marker.x, cy: marker.y, r: 24, class: "objective-ring", "aria-label": "Objectif à découvrir ou rejoindre"}));
  }
  svg.dataset.map = "general";
  const worldMapNodes = [mountWorldMap(svg)];
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
      node.onclick = choose;
      node.ondblclick = () => visitPoint(point);
      node.onkeydown = event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); visitPoint(point); } };
      local.append(node);
    });
    local.dataset.map = `detail:${place.id}`;
    worldMapNodes.push(mountWorldMap(local));
  }
  for (const child of [...$("world-map").children]) if (!worldMapNodes.includes(child)) child.remove();
  paragraphs("place-details", [`${place.name} · ${place.type} · ${place.id === world.current ? "vous êtes ici" : place.visited ? "déjà visité" : "encore non visité"}`, place.description]);
  $("map-routes").replaceChildren();
  for (const route of world.routes.filter(r => r.from === place.id || r.to === place.id)) {
    const p = document.createElement("p");
    p.textContent = `${route.name} · ${route.distance_km} km · ${(route.distance_km / 6 * 3600 / 3).toFixed(0)} s de marche : ${places.find(p => p.id === route.from).name} ↔ ${places.find(p => p.id === route.to).name}`;
    $("map-routes").append(p);

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
  if (!locked && point && (adventure.position !== point.id || adventure.moving) && point.id !== "leon") {
    const move = document.createElement("button");
    move.textContent = "Se déplacer à ce point";
    move.disabled = busy;
    move.addEventListener("click", () => requestTravel(point.id, point.name, place.id));
    $("point-actions").append(move);
  }
  if (!locked && (place.id !== world.current || adventure.moving) && !world.routes.some(route => route.destination === place.id)) {
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
  if (["stats", "equipment", "inventory", "map", "bestiary", "achievements"].includes(view)) currentView = view;
  if (session && session.tutorial) renderTutorial(session.tutorial);
}
function skillAllowed(me, skill, target, mob) {
  if (!session.tutorial.battle?.hostiles_alive || me.casting || me.hp <= 0 || me.stunned || me.cooldown_real_seconds > 0 || !skill.available || skill.cooldown > 0) return false;
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
function renderCombatFeedback(adventure) {
  const events = (session.events || []).filter(event => event.game_time >= (adventure.battle?.started_at || 0)).slice(-12);
  const latest = events.at(-1);
  const notice = $("combat-notice");
  if (notice.dataset.event !== String(latest?.id || "")) {
    notice.dataset.event = String(latest?.id || "");
    notice.textContent = latest?.message || "Choisissez une cible ou déplacez-vous sur la carte.";
    notice.classList.toggle("damage-notice", /PV perdus/.test(latest?.message || ""));
    notice.classList.toggle("detection-notice", /repéré/.test(latest?.message || ""));
  }
  const log = $("combat-events"), retained = new Set();
  const followLatest = log.scrollTop + log.clientHeight >= log.scrollHeight - 12;
  for (const event of events) {
    let row = [...log.children].find(child => child.dataset.event === String(event.id));
    if (!row) { row = document.createElement("li"); row.dataset.event = String(event.id); row.textContent = event.message; log.append(row); }
    retained.add(row);
  }
  for (const row of [...log.children]) if (!retained.has(row)) row.remove();
  if (followLatest) log.scrollTop = log.scrollHeight;
}
function renderTutorial(adventure, preserveBattle = false) {
  if ($("combat-view").firstElementChild !== $("fighters")) $("combat-view").prepend($("fighters"));
  const fighting = Boolean(adventure.battle);
  $("combat-layout").hidden = !fighting;
  if (fighting) {
    for (const [parent, child] of [["combat-action-panel", "combat-view"], ["combat-player-panel", "combat-allies"], ["combat-player-panel", "unit-controls"], ["combat-map-panel", "map-strip"], ["combat-enemy-panel", "combat-enemies"]]) {
      if ($(child).parentElement !== $(parent)) $(parent).append($(child));
    }
  } else {
    const actions = document.querySelector(".zone-actions"), grid = document.querySelector(".adventure-grid");
    if ($("combat-view").parentElement !== actions) actions.append($("combat-view"));
    if ($("map-strip").nextElementSibling !== grid) $("tutorial-panel").insertBefore($("map-strip"), grid);
    if ($("combat-enemies").parentElement !== $("combat-view")) $("combat-view").append($("combat-enemies"));
  }
  $("battle").classList.toggle("combat-mode", fighting);
  document.body.classList.toggle("combat-active", fighting);
  $("map-help").textContent = fighting ? "Un clic inspecte les entités d’une case ; un double clic déplace le personnage ou les alliés contrôlés. Les blocs bruns servent de couverture." : "Un clic consulte un lieu ou un point ; un double clic lance le déplacement.";
  $("character-menu").hidden = fighting;
  $("lobby").hidden = fighting;
  const context = `${session.id}:${adventure.step}:${fighting}:${adventure.encounter_number || 0}`;
  if (context !== viewContext) {
    if (!["stats", "equipment", "inventory", "map", "bestiary", "achievements"].includes(currentView)) currentView = "map";
    combatTarget = "";
    focusedMob = "";
    inspectedCell = null;
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
  for (const view of ["stats", "equipment", "inventory", "bestiary", "achievements"]) $(`${view}-view`).hidden = currentView !== view && !(currentView === "map" && view === "stats");
  $("quest-view").hidden = false;
  $("combat-view").hidden = !fighting;
  $("npc-view").hidden = !canTalk;
  $("craft-view").hidden = !atForge;
  $("standby-view").hidden = fighting || canTalk || atForge;
  $("fighters").hidden = true;
  for (const view of ["stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"]) {
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
  const vest = me.gear.find(piece => piece.slot === "torso");
  $("quest-description").textContent = vest && adventure.quest === "completed" ? adventure.step === "craft" ? "Veste fabriquée et équipée : votre objectif de forge est accompli. Attendez que votre compagnon fabrique sa veste." : adventure.step === "complete" ? "Veste fabriquée et équipée. Vous avez rejoint Brume : tutoriel terminé." : "Veste fabriquée et équipée : objectif accompli. Prochaine étape : rejoindre le village de Brume." : !hasQuest ? "Explorez les lieux et leurs points stratégiques pour rencontrer des PNJ qui proposent des quêtes." : adventure.quest === "completed" ? "Mira vous a remis votre récompense. Utilisez les matériaux de votre sac pour fabriquer et équiper votre veste à la forge." : "Battez trois gobelins de la lisière, puis revenez parler à Mira à Rosée. Gardez les matériaux pour fabriquer votre veste.";
  $("quest-progress").textContent += ` · ${adventure.achievements?.kills || 0} créature(s) vaincue(s) dans cette aventure`;
  renderVitals("character-vitals", [me, ...me.invocations]);
  $("character-details").replaceChildren();
  for (const text of [
    `Expérience : ${me.exp}/${me.next_level_exp} · niveau ${me.level}`,
    `Force ${me.stats.force} · Endurance ${me.stats.endurance} · Intelligence ${me.stats.intelligence} · Sagesse ${me.stats.sagesse}`,
    `Invocations : ${me.invocations.map(i => `${i.name} (${i.hp} PV)`).join(", ") || "aucune"}`,
    `Statuts : ${statusText(me)}`,
    `Compétences acquises : ${me.skills.map(s => `${s.name} (${s.cost} ${s.energy})`).join(", ")}`,
    `Prochaines compétences : ${me.upcoming_skills.map(s => `${s.name} au niveau ${s.level}`).join(", ") || "toutes acquises"}`,
  ]) {
    const p = document.createElement("p");
    p.textContent = text;
    $("character-details").append(p);
  }
  for (const invocation of me.invocations) { const text = document.createElement("p"); text.textContent = statsText(invocation); $("character-details").append(text); }
  for (const id of ["tutorial-actions", "npc-actions", "quest-actions", "craft-actions"]) $(id).replaceChildren();
  const stableActions = new Map(["combat-actions", "skills", "self-skills", "unit-control-actions"].map(id => [id, new Set()]));
  function button(container, label, handler, disabled = false) {
    const retained = stableActions.get(container);
    const existing = retained && [...$(container).children].find(child => child.dataset.actionLabel === label);
    const element = existing || document.createElement("button");
    element.dataset.actionLabel = label;
    element.textContent = label;
    element.disabled = busy || disabled;
    element.onclick = handler;
    if (!existing) $(container).append(element);
    if (retained) retained.add(element);
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
      action("tutorial-actions", `Rejoindre ${destination.name}`, "travel", {destination: destination.id});
    }
    if (["clearing", "clearing_fight", "lisiere", "hunt", "training"].includes(adventure.position)) action("tutorial-actions", "Explorer ce lieu", "explore");
  }
  if (!fighting) { renderWorld(adventure, me); renderAchievements(adventure.achievements); }
  $("npc-dialogue").textContent = adventure.step === "village" ? "Mira : des gobelins menacent notre lisière. Pourriez-vous en battre trois ? Gardez leurs peaux et leurs crocs pour la forge." : adventure.quest === "completed" ? "Mira : merci pour votre aide ! La forge est désormais accessible." : adventure.kills < 3 ? `Mira : il reste ${3 - adventure.kills} gobelin(s) à battre dans la lisière.` : "Mira : vous avez vaincu les trois gobelins ! Votre récompense vous attend. Ensuite, faites fabriquer votre veste à la forge.";
  if (canTalk && (adventure.step === "village" || adventure.step === "hunt" && adventure.kills === 3)) action("npc-actions", adventure.step === "village" ? "Accepter la quête" : "Rendre la quête", "talk", {npc: "mira"});
  button("quest-actions", "Localiser le lieu de la quête", () => { mapMarker = {zone: hasQuest && adventure.kills < 3 ? "lisiere" : "rosee", point: hasQuest && adventure.kills < 3 ? "hunt" : "mira"}; renderTutorial(session.tutorial); message("Le lieu de la quête est entouré sur la carte générale."); });
  $("forge-status").textContent = adventure.quest !== "completed" ? "Forge verrouillée : terminez la quête de Mira et rendez-la sur la place du village." : "Forge débloquée : fabriquez ou améliorez chaque pièce indépendamment jusqu’à +10.";
  if (vest && adventure.step === "travel" && atForge && !adventure.moving) action("craft-actions", "Rejoindre Village de Brume", "travel", {destination: "brume"});
  if (vest && adventure.quest === "completed") $("forge-status").textContent = `Veste équipée (+${vest.level}). ${adventure.step === "craft" ? "Votre compagnon doit encore fabriquer la sienne." : "Fabrication validée : rejoignez Brume pour terminer le tutoriel."}`;
  $("craft-materials").textContent = `Votre sac : ${Object.entries(me.inventory).map(([item, quantity]) => `${quantity} ${item}`).join(", ") || "aucun matériau"}.`;
  $("forge-catalogue").replaceChildren();
  if (atForge) for (const recipe of me.forge) {
    const card = document.createElement("article"); card.className = "codex-card";
    const title = document.createElement("h4"); title.textContent = recipe.equipped ? `${recipe.equipped.name} +${recipe.equipped.level}` : recipe.name; card.append(title);
    const info = document.createElement("p"); info.textContent = recipe.cost ? `Coût : ${Object.entries(recipe.cost).map(([k,v]) => `${v} ${k}`).join(", ")}` : "Amélioration maximale +10 atteinte."; card.append(info);
    const bonus = document.createElement("p"); bonus.textContent = `Bonus : ${equipmentBonuses(recipe.equipped || recipe)}.`; card.append(bonus);
    const adjective = document.createElement("p"); adjective.textContent = `À +10 : ${recipe.name} ${recipe.adjective}. Chaque pièce s'améliore indépendamment.`; card.append(adjective);
    if (recipe.cost) { const craft = document.createElement("button"); craft.textContent = recipe.equipped ? `Améliorer à +${recipe.equipped.level + 1}` : "Fabriquer et équiper"; craft.disabled = busy || adventure.quest !== "completed" || !recipe.affordable; craft.addEventListener("click", () => tutorialCommand(recipe.equipped ? "upgrade" : "craft", {recipe: recipe.recipe})); card.append(craft); }
    $("forge-catalogue").append(card);
  }
  $("mob-name").textContent = fighting ? `${(adventure.mobs || []).length} ennemi(s) visible(s)` : "";
  $("mob-hp").textContent = fighting ? (adventure.mobs || [adventure.mob]).map(m => `${m.name} : ${m.stats.hp.current}/${m.stats.hp.max} PV`).join(" · ") : "";
  const enemies = fighting ? (adventure.mobs ?? (adventure.mob ? [{...adventure.mob, combat_id: "mob"}] : [])).map(m => ({id: m.combat_id, name: m.name, position: m.position, hp: m.stats.hp.current, max_hp: m.stats.hp.max, enemy: true})) : [];
  const mob = enemies[0] || null;
  const canAttack = target => Boolean(target.enemy && target.hp > 0 && me.hp > 0 && !me.stunned && !me.casting && me.cooldown_real_seconds <= 0 && me.can_attack && battleAllowed(adventure, me.id, target.id, me.attack_range));
  const possibleTargets = fighting ? [...enemies, ...adventure.players].filter(target => (!focusedMob || target.id === focusedMob) && (target.enemy || me.skills.some(skill => skillAllowed(me, skill, target, mob)))) : [];
  $("combat-target").replaceChildren();
  for (const target of possibleTargets) {
    const option = document.createElement("option");
    option.value = target.id;
    option.textContent = `${target.name}${target.id === me.id ? " · vous" : ""}`;
    $("combat-target").append(option);
  }
  if (!combatTarget && possibleTargets.length) {
    const placeholder = document.createElement("option"); placeholder.value = ""; placeholder.textContent = "Sélectionnez une entité sur la carte"; $("combat-target").prepend(placeholder);
  }
  $("combat-target").value = possibleTargets.length ? combatTarget : "";
  $("target-controls").hidden = !fighting;
  const selected = [...enemies, ...adventure.players].find(target => target.id === combatTarget);
  $("combat-status").textContent = !fighting ? "" : !adventure.battle.hostiles_alive ? "Tous les ennemis sont morts. Approchez les corps pour les dépecer, puis quittez le champ de bataille." : me.casting ? `${me.casting.name} · incantation : ${me.casting.remaining_seconds.toFixed(1)} s · immobile${me.casting.concentration ? " · dégâts = interruption" : ""}` : me.hp <= 0 ? "Vous êtes à terre. Votre compagnon peut terminer le combat." : me.cooldown_real_seconds > 0 ? `Prochaine action dans ${me.cooldown_real_seconds.toFixed(1)} s.` : me.stunned ? "Vous êtes étourdi : aucune action n'est disponible." : selected ? "Choisissez une attaque ou une compétence pour cette cible." : "Aucune action disponible sur une cible.";
  if (fighting) {
    renderCombatFeedback(adventure);
    const playerUnit = adventure.battle.players[me.id];
    if (playerUnit.hidden && playerUnit.route.length) $("combat-status").textContent = "Déplacement discret : vitesse réduite, dissimulation maintenue tant que vous restez couvert.";
  }
  if (fighting && !preserveBattle) renderBattle(adventure, me);
  if (fighting) {
    renderUnitControls(adventure, me, action);
    renderSelection(adventure, me);
    const controlled = controlledUnits(adventure, me.id);
    if (controlled.length) {
      const single = controlled.length === 1 ? controlled[0][1] : null;
      $("combat-action-title").textContent = single ? `Actions · ${unitName({...single,id:controlled[0][0]})}` : "Actions · groupe d’alliés";
      action("combat-actions", single ? "Attaque simple · invocation" : "Attaquer avec les alliés contrôlés", "unit_order", {units: controlled.map(([id]) => id), order: "attack", target: selected?.id, paths: {}}, !selected?.enemy || me.casting || me.cooldown_real_seconds > 0 || me.stunned || me.hp <= 0 || controlled.some(([,unit]) => unit.casting));
      for (const skill of single?.skills || []) {
        const targetAllowed = selected?.enemy && Math.hypot(single.position[0] - selected.position[0], single.position[1] - selected.position[1]) <= skill.range && gridSight(adventure.battle.map, single.position, selected.position);
        action("skills", `${skill.name} · ${skill.cost} ${skill.energy} · ${skill.cast_seconds} s`, "unit_skill", {units: [controlled[0][0]], skill_name: skill.name, target: selected?.id}, !targetAllowed || !skill.available || Boolean(single.casting) || me.casting || me.cooldown_real_seconds > 0 || me.stunned || me.hp <= 0);
      }
      if (single?.casting) $("combat-status").textContent = `${single.name} · ${single.casting.skill_name} · incantation en cours`;
    } else $("combat-action-title").textContent = `Actions · ${me.name}`;
  }
  if (fighting && !controlledUnits(adventure, me.id).length) {
    action("combat-actions", "Attaque simple", "strike", {target: selected?.id}, !selected || !canAttack(selected));
    for (const skill of me.skills.filter(s => s.type === "INVOCATION")) {
      const element = action("self-skills", `Invoquer · ${skill.name} · ${skill.cost} ${skill.energy} · ${skill.cast_seconds} s`, "skill", {skill_name: skill.name, target: me.id}, !skillAllowed(me, skill, me, mob));
      element.title = me.casting ? "Incantation en cours." : me.invocations.length >= me.invocation_limit ? "Limite d’invocations atteinte." : "Invoquer sur soi, sans changer la cible sélectionnée.";
    }
    for (const skill of me.skills.filter(s => s.type !== "INVOCATION")) {
      const element = action("skills", `${skill.name} · ${skill.cost} ${skill.energy} · ${skill.cast_seconds} s${skill.concentration ? " · concentration" : ""}`, "skill", {skill_name: skill.name, target: selected?.id}, !selected || !skillAllowed(me, skill, selected, mob));
      element.className = "secondary";
      element.title = skill.description;
    }
  }
  if (!fighting) $("unit-controls").hidden = true;
  for (const [id, retained] of stableActions) for (const child of [...$(id).children]) if (!retained.has(child)) child.remove();
}
function requestTravel(destination) {
  const adventure = session?.tutorial;
  if (!adventure) return;
  if (adventure.battle) return message("Terminez le combat avant de voyager.");
  return tutorialCommand("move", {destination});
}
function selectEntity(id) {
  tacticalInteractionUntil = Date.now() + 500;
  focusedMob = focusedMob === id ? "" : id;
  combatTarget = focusedMob;
  const adventure = session.tutorial, position = entityPosition(adventure, id);
  inspectedCell = position ? [...position] : null;
  const summon = adventure.battle?.summons?.[id], actor = adventure.players.find(p => p.id === session.me);
  if (focusedMob && summon?.owner === session.me && !summon.controlled && !busy && actor.hp > 0 && !actor.stunned && !actor.casting && actor.cooldown_real_seconds <= 0 && canPayControl(adventure, actor, summon)) tutorialCommand("control_units", {units: [id]});
  if (focusedMob === session.me && controlledUnits(adventure, session.me).length && !busy) tutorialCommand("control_units", {units: []});
  renderTutorial(session.tutorial, true);
  const ns = "http://www.w3.org/2000/svg";
  for (const card of $("mob-cards").querySelectorAll("[data-mob]")) card.classList.toggle("selected", card.dataset.mob === focusedMob);
  for (const group of $("world-map").querySelectorAll("[data-unit]")) {
    group.querySelector(".objective-ring")?.remove();
    if (group.dataset.unit === focusedMob) {
      const source = group.querySelector("circle"), ring = document.createElementNS(ns, "circle");
      for (const attr of ["cx", "cy"]) ring.setAttribute(attr, source.getAttribute(attr));
      ring.setAttribute("r", "18"); ring.setAttribute("class", "objective-ring"); group.append(ring);
    }
  }
}
function approachEntity(position) {
  const adventure = session.tutorial, me = adventure.players.find(p => p.id === session.me);
  if (me.casting || me.hp <= 0 || me.stunned) return;
  const unit = controlledUnits(adventure, me.id)[0]?.[1] || adventure.battle.players[me.id], map = adventure.battle.map;
  if (Math.hypot(unit.position[0] - position[0], unit.position[1] - position[1]) <= 1.5) return;
  const candidates = [[position[0] - 1, position[1]], [position[0] + 1, position[1]], [position[0], position[1] - 1], [position[0], position[1] + 1]];
  const paths = candidates.map(p => gridPath(map, unit.position, p)).filter(p => p !== null).sort((a,b) => a.length - b.length);
  if (!paths.length || !paths[0].length) return;
  const path = paths[0], [x,y] = path[path.length - 1];
  moveControlled(adventure, me, [x, y]);
}
function entityPosition(adventure, id) {
  return adventure.battle.players[id]?.position || adventure.battle.summons?.[id]?.position || adventure.mobs.find(m => m.combat_id === id)?.position || adventure.battle.corpses.find(c => c.id === id)?.position;
}
function controlledUnits(adventure, owner) {
  return Object.entries(adventure.battle?.summons || {}).filter(([,unit]) => unit.owner === owner && unit.controlled && unit.hp > 0);
}
function unitName(unit) {
  const number = unit.id?.match(/:summon:(\d+)$/);
  return number ? `${unit.name} · #${Number(number[1]) + 1}` : unit.name;
}
function renderVitals(container, units) {
  const parent = typeof container === "string" ? $(container) : container, kept = new Set();
  for (const unit of units) {
    const key = unit.id || unit.name;
    let card = [...parent.children].find(node => node.dataset.vitals === key);
    if (!card) {
      card = document.createElement("article"); card.className = "vitals-card"; card.dataset.vitals = key;
      const name = document.createElement("strong"); name.className = "vitals-name";
      const resources = document.createElement("div"); resources.className = "vitals-resources";
      const statuses = document.createElement("div"); statuses.className = "vitals-statuses";
      card.append(name, resources, statuses); parent.append(card);
    }
    const previousHp = Number(card.dataset.hp ?? unit.hp);
    if (unit.hp < previousHp) {
      const change = document.createElement("span"); change.className = "hp-change"; change.textContent = `−${Number((previousHp - unit.hp).toFixed(1))} PV`; card.append(change);
      setTimeout(() => change.remove(), 1200);
    }
    card.dataset.hp = String(unit.hp);
    kept.add(card); card.querySelector(".vitals-name").textContent = unitName(unit);
    const resources = [{type: "PV", current: unit.hp, max: unit.max_hp}, ...(unit.energies || [])];
    const rows = card.querySelector(".vitals-resources");
    for (let index = 0; index < resources.length; index++) {
      const resource = resources[index];
      let row = rows.children[index];
      if (!row) { row = document.createElement("div"); row.className = "vitals-row"; row.append(document.createElement("progress"), document.createElement("span")); rows.append(row); }
      const bar = row.querySelector("progress"); bar.max = Math.max(1, resource.max); bar.value = Math.max(0, resource.current); bar.className = resource.type === "PV" ? "vitals-hp" : "vitals-energy"; bar.setAttribute("aria-label", `${resource.type} de ${unitName(unit)}`);
      row.querySelector("span").textContent = `${Number(resource.current.toFixed(1))}/${resource.max} ${resource.type}`;
    }
    while (rows.children.length > resources.length) rows.lastChild.remove();
    const statuses = card.querySelector(".vitals-statuses");
    statuses.replaceChildren();
    const heading = document.createElement("span"); heading.className = "vitals-status-label"; heading.textContent = "Statuts :"; statuses.append(heading);
    if (unit.hidden || unit.detected) { const visibility = document.createElement("span"); visibility.className = "status-badge"; visibility.textContent = unit.hidden ? "Dissimulé" : "Repéré"; statuses.append(visibility); }
    for (const effect of unit.effects || []) {
      const badge = document.createElement("span"); badge.className = "status-badge";
      const seconds = effect.remaining_seconds ?? effect.duration * 1.2;
      badge.textContent = `${effect.name || effect.type} (${Math.max(0, seconds).toFixed(1)} s)`; statuses.append(badge);
    }
    if (!(unit.effects || []).length) { const empty = document.createElement("span"); empty.textContent = unit.stunned ? "Étourdi" : "aucun"; statuses.append(empty); }
  }
  for (const card of [...parent.children]) if (!kept.has(card)) card.remove();
}
function statusText(unit) {
  const effects = (unit.effects || []).map(effect => `${effect.name || effect.type} (${Math.max(0, effect.remaining_seconds ?? effect.duration * 1.2).toFixed(1)} s)`);
  if (unit.stunned && !(unit.effects || []).some(effect => effect.group === "stun")) effects.push("Étourdi");
  return effects.length ? effects.join(" · ") : "aucun";
}
function combatVitals(unit) {
  return `${unitName(unit)} · ${unit.hp}/${unit.max_hp} PV${unit.energies?.length ? " · " + unit.energies.map(e => `${e.type} ${e.current.toFixed(1)}/${e.max}`).join(" · ") : ""} · Statuts : ${statusText(unit)}`;
}
function statsText(unit) {
  const stats = unit.stats || {};
  const value = key => typeof stats[key] === "object" ? stats[key].current : stats[key] ?? "?";
  return `${unitName(unit)} · ${unit.hp}/${unit.max_hp} PV · Force ${value("force")} · Endurance ${value("endurance")} · Intelligence ${value("intelligence")} · Sagesse ${value("sagesse")}${unit.energies?.length ? " · " + unit.energies.map(e => `${e.type} ${e.current.toFixed(1)}/${e.max}`).join(" · ") : ""}`;
}
function moveControlled(adventure, me, destination) {
  if (busy) { pendingBattleMove = {destination, sessionId: session.id, encounter: session.tutorial.encounter_number, controlledIds: controlledUnits(session.tutorial, session.me).map(([id]) => id).sort()}; return; }
  adventure = session.tutorial;
  me = adventure.players.find(player => player.id === session.me);
  const controlled = controlledUnits(adventure, me.id);
  const [x,y] = destination;
  if (controlled.length) {
    const paths = Object.fromEntries(controlled.map(([id,unit]) => [id, gridPath(adventure.battle.map, unit.position, destination)]));
    if (Object.values(paths).some(path => path === null)) return message("Ce chemin est bloqué pour un allié.");
    return tutorialCommand("unit_order", {units: controlled.map(([id]) => id), order: "move", target: destination, paths});
  }
  const path = gridPath(adventure.battle.map, adventure.battle.players[me.id].position, destination);
  if (path?.length) return tutorialCommand("battle_move", {x, y, path});
}
function canPayControl(adventure, me, unit) {
  const cost = unit.control_cost;
  return !cost?.per_second || me.energies.some(e => e.type === cost.energy && e.current > 0) || (adventure.control_credit?.[me.id]?.[cost.energy] || 0) > 0;
}
function renderUnitControls(adventure, me, action) {
  const units = Object.entries(adventure.battle.summons || {}).filter(([,unit]) => unit.owner === me.id);
  $("unit-controls").hidden = !units.length;
  const controlled = controlledUnits(adventure, me.id);
  $("control-status").textContent = `${controlled.length} allié(s) contrôlé(s). Un double clic donne un ordre de déplacement ; sélectionnez un ennemi pour ordonner l’attaque.`;
  const retained = new Set();
  for (const [id,unit] of units) {
    let row = [...$("unit-control-list").children].find(child => child.dataset.unit === id);
    if (!row) { row = document.createElement("label"); row.dataset.unit = id; row.append(document.createElement("input"), document.createElement("span")); $("unit-control-list").append(row); }
    retained.add(row);
    const checkbox = row.querySelector("input"); checkbox.type = "checkbox"; checkbox.checked = Boolean(unit.controlled); checkbox.disabled = busy || !unit.controlled && (!canPayControl(adventure, me, unit) || me.hp <= 0 || me.stunned || Boolean(me.casting) || me.cooldown_real_seconds > 0);
    checkbox.onchange = () => { const ids = controlled.map(([key]) => key).filter(key => key !== id); if (checkbox.checked) ids.push(id); tutorialCommand("control_units", {units: ids}); };
    row.querySelector("span").textContent = `${unitName({...unit,id})} · ${unit.hp}/${unit.max_hp} PV · ${unit.control_cost?.per_second || 0} ${unit.control_cost?.energy || "énergie"}/s`;
  }
  for (const row of [...$("unit-control-list").children]) if (!retained.has(row)) row.remove();
  if (!units.length) return;
  action("unit-control-actions", "Tout contrôler", "control_units", {units: units.map(([id]) => id)}, me.hp <= 0 || me.stunned || Boolean(me.casting) || me.cooldown_real_seconds > 0 || units.some(([,unit]) => !canPayControl(adventure, me, unit)));
  action("unit-control-actions", "Rendre autonomes", "control_units", {units: []}, !controlled.length);
  if (controlled.length) action("unit-control-actions", "Maintenir la position", "unit_order", {units: controlled.map(([id]) => id), order: "hold", target: null, paths: {}}, me.hp <= 0 || me.stunned || Boolean(me.casting) || me.cooldown_real_seconds > 0);
}
function renderSelection(adventure, me) {
  const battle = adventure.battle;
  const entries = [...adventure.players.map(player => ({...player, position: battle.players[player.id].position})), ...Object.entries(battle.summons || {}).map(([id,unit]) => ({...unit,id})), ...adventure.mobs.map(mob => ({id: mob.combat_id, name: mob.name, position: mob.position})), ...battle.corpses.map(c => ({...c,name: c.name + " · corps"}))];
  const visible = inspectedCell ? entries.filter(e => e.position[0] === inspectedCell[0] && e.position[1] === inspectedCell[1]) : [];
  $("cell-selection-status").textContent = !inspectedCell ? "Cliquez sur une case ou une entité de la carte." : visible.length ? `Case ${inspectedCell.join(",")} · ${visible.length} entité(s) visible(s)` : "Aucune entité visible sur cette case.";
  const retained = new Set();
  for (const entity of visible) {
    let button = [...$("cell-entities").children].find(child => child.dataset.target === entity.id);
    if (!button) { button = document.createElement("button"); button.dataset.target = entity.id; $("cell-entities").append(button); }
    retained.add(button); button.textContent = unitName(entity); button.setAttribute("aria-pressed", String(focusedMob === entity.id)); button.onclick = () => selectEntity(entity.id);
  }
  for (const button of [...$("cell-entities").children]) if (!retained.has(button)) button.remove();
  const selected = battle.summons?.[focusedMob];
  paragraphs("selected-unit-stats", selected ? [selected.owner === me.id ? `Contrôle : ${selected.controlled ? "manuel" : "automatique"} · ${selected.control_cost?.per_second || 0} ${selected.control_cost?.energy || "énergie"}/s` : "Cet allié appartient à votre compagnon."] : []);
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
  const queue = [{point: source, cost: 0}];
  const parents = new Map([[key(source), null]]), costs = new Map([[key(source), 0]]);
  while (queue.length) {
    queue.sort((a,b) => a.cost - b.cost);
    const {point: node, cost} = queue.shift();
    if (cost > costs.get(key(node))) continue;
    if (key(node) === key(destination)) {
      const result = [];
      let point = node;
      while (parents.get(key(point)) !== null) { result.unshift(point); point = parents.get(key(point)); }
      return result;
    }
    for (const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]) {
      const point = [node[0] + dx, node[1] + dy], nextCost = cost + Math.hypot(dx,dy);
      if (blocked(...point) || (dx && dy && (blocked(node[0] + dx,node[1]) || blocked(node[0],node[1] + dy)))) continue;
      if (nextCost < (costs.get(key(point)) ?? Infinity)) { costs.set(key(point), nextCost); parents.set(key(point), node); queue.push({point, cost: nextCost}); }
    }
  }
  return null;
}
function renderBattle(adventure, me) {
  const battle = adventure.battle, map = battle.map;
  const unit = battle.players[me.id];
  const disabled = Boolean(me.casting) || me.hp <= 0 || me.stunned;
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
      if (cover) return message("Cette case est occupée par une couverture.");
      moveControlled(adventure, me, [x, y]);
    };
    cell.onclick = () => { inspectedCell = [x, y]; renderTutorial(session.tutorial, true); };
    cell.ondblclick = move;
    cell.onkeydown = event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); move(); } };
    svg.append(cell);
  }
  for (const [, ally] of controlledUnits(adventure, me.id)) for (const step of ally.route) svg.append(element("circle", {cx: step[0] * 40 + 20, cy: step[1] * 40 + 20, r: 3, class: "route-dot"}));
  for (const step of unit.route) svg.append(element("circle", {cx: step[0] * 40 + 20, cy: step[1] * 40 + 20, r: 3, class: "route-dot"}));
  const draw = (id, position, label, className) => {
    const group = element("g", {class: `battle-unit ${className}`, "data-unit": id});
    group.append(element("circle", {cx: position[0] * 40 + 20, cy: position[1] * 40 + 20, r: 13}));
    group.append(element("text", {x: position[0] * 40 + 20, y: position[1] * 40 + 25}, label));
    if (id === focusedMob) group.append(element("circle", {cx: position[0] * 40 + 20, cy: position[1] * 40 + 20, r: 18, class: "objective-ring"}));
    group.onclick = () => selectEntity(id);
    group.ondblclick = event => { event.preventDefault(); const current = entityPosition(session.tutorial, id); if (current) approachEntity(current); };
    svg.append(group);
  };
  for (const player of adventure.players) draw(player.id, battle.players[player.id].position, player.id === me.id ? "Vous" : player.name.slice(0, 3), battle.players[player.id].hidden ? "hidden-player" : "visible-player");
  for (const mob of adventure.mobs) draw(mob.combat_id, mob.position, mob.combat_id === "mob" ? "G1" : `G${mob.combat_id.split("-")[1]}`, "enemy-unit");
  for (const [id, summon] of Object.entries(battle.summons || {})) {
    const number = id.match(/:summon:(\d+)$/);
    const label = number ? `S${Number(number[1]) + 1}` : "S";
    draw(id, summon.position, summon.controlled ? `${label}★` : label, "summon-unit");
    svg.lastChild.append(element("title", {}, `${summon.name} · ${summon.hp}/${summon.max_hp} PV`));
  }
  for (const corpse of battle.corpses) draw(corpse.id, corpse.position, "✝", "corpse-unit");
  const previousMap = $("world-map").querySelector(".battle-map");
  if (previousMap && previousMap.getAttribute("viewBox") === svg.getAttribute("viewBox")) {
    const nodes = [...svg.children].map(node => {
      const selector = node.dataset.unit ? `[data-unit="${node.dataset.unit}"]` : node.dataset.cell ? `[data-cell="${node.dataset.cell}"]` : null;
      const retained = selector && previousMap.querySelector(selector);
      if (!retained) return node;
      for (const attr of [...retained.attributes]) retained.removeAttribute(attr.name);
      for (const attr of node.attributes) retained.setAttribute(attr.name, attr.value);
      const children = [...node.children].map((child, index) => {
        const oldChild = retained.children[index];
        if (!oldChild || oldChild.tagName !== child.tagName) return child;
        for (const attr of [...oldChild.attributes]) oldChild.removeAttribute(attr.name);
        for (const attr of child.attributes) oldChild.setAttribute(attr.name, attr.value);
        oldChild.textContent = child.textContent;
        return oldChild;
      });
      for (const child of [...retained.children]) if (!children.includes(child)) child.remove();
      for (const child of children) if (child.parentElement !== retained) retained.append(child);
      retained.onclick = node.onclick; retained.ondblclick = node.ondblclick; retained.onkeydown = node.onkeydown;
      return retained;
    });
    for (const child of [...previousMap.children]) if (!nodes.includes(child)) child.remove();
    for (const child of nodes) if (child.parentElement !== previousMap) previousMap.append(child);
  } else $("world-map").replaceChildren(svg);
  const retainedCards = new Set();
  for (const mob of adventure.mobs) {
    const card = [...$("mob-cards").children].find(node => node.dataset.mob === mob.combat_id) || document.createElement("button"); retainedCards.add(card); card.className = "mob-card"; card.dataset.mob = mob.combat_id;
    let vitals = card.querySelector(".enemy-vitals");
    if (!vitals) { vitals = document.createElement("div"); vitals.className = "enemy-vitals"; card.append(vitals); }
    renderVitals(vitals, [{...mob, id: mob.combat_id, hp: mob.stats.hp.current, max_hp: mob.stats.hp.max}]);
    card.classList.toggle("selected", focusedMob === mob.combat_id);
    card.onclick = () => selectEntity(mob.combat_id);
    card.ondblclick = event => { event.preventDefault(); const current = entityPosition(session.tutorial, mob.combat_id); if (current) approachEntity(current); };
    if (card.parentElement !== $("mob-cards")) $("mob-cards").append(card);
  }
  for (const card of [...$("mob-cards").children]) if (!retainedCards.has(card)) card.remove();
  renderVitals("combat-stats-details", adventure.players.flatMap(player => player.invocations));
  renderVitals("combat-resources", adventure.players.map(player => ({...player, hidden: battle.players[player.id].hidden, detected: battle.players[player.id].detected})));
  const table = document.createElement("table");
  for (const intent of battle.intents) {
    const row = document.createElement("tr");
    for (const text of [intent.name, intent.action, intent.remaining_seconds > 0 && /Entaille|Appel/.test(intent.action) ? `${intent.remaining_seconds.toFixed(1)} s` : ""]) { const cell = document.createElement("td"); cell.textContent = text; row.append(cell); }
    table.append(row);
  }
  $("enemy-intents").replaceChildren(table);
  $("tactical-actions").replaceChildren();
  const hide = document.createElement("button"); hide.textContent = unit.hidden ? "Vous êtes dissimulé" : "Se cacher derrière une couverture";
  hide.disabled = disabled || unit.hidden || unit.can_hide === false || !map.cover.some(p => Math.hypot(unit.position[0] - p[0], unit.position[1] - p[1]) <= 1.5);
  hide.addEventListener("click", () => tutorialCommand("hide"));
  if (!hide.disabled) $("tactical-actions").append(hide);
  else if (unit.hidden) { const label = document.createElement("p"); label.textContent = "Dissimulé · déplacement couvert à vitesse réduite"; $("tactical-actions").append(label); }
  $("corpse-actions").replaceChildren();
  for (const corpse of battle.corpses) {
    if (Math.hypot(unit.position[0] - corpse.position[0], unit.position[1] - corpse.position[1]) > 1.5) continue;
    const button = document.createElement("button"); button.textContent = corpse.harvested.length ? `${corpse.name} · déjà dépecé` : `Dépecer ${corpse.name}`;
    button.disabled = disabled || corpse.harvested.length > 0 || Math.hypot(unit.position[0] - corpse.position[0], unit.position[1] - corpse.position[1]) > 1.5;
    button.addEventListener("click", () => tutorialCommand("harvest", {target: corpse.id})); $("corpse-actions").append(button);
  }
  if (!adventure.battle.hostiles_alive) { const leave = document.createElement("button"); leave.textContent = "Quitter le champ de bataille"; leave.disabled = disabled; leave.addEventListener("click", () => tutorialCommand("leave_battle")); $("tactical-actions").append(leave); }
}

async function refresh(force = false) {
  if (!token) {
    $("connection").textContent = "Prêt · créez votre personnage";
    return;
  }
  if (polling || (!force && Date.now() < nextRefreshAt)) return;
  polling = true;
  const epoch = stateEpoch;
  try {
    const state = await api("/api/state");
    if (epoch !== stateEpoch || (state.session && session && state.session.id === session.id && state.session.revision < session.revision)) return;
    if (state.session) {
      session = state.session;
      sessionId = session.id;
    } else if (sessionId) {
      const updated = await api(`/api/sessions/${sessionId}`);
      if (epoch !== stateEpoch || (updated.id === session?.id && updated.revision < session.revision)) return;
      session = updated;
    } else session = null;
    remember();
    refreshFailures = 0;
    nextRefreshAt = 0;
    render(state);
  } catch (error) {
    refreshFailures++;
    nextRefreshAt = Date.now() + Math.min(10000, 1000 * 2 ** Math.min(4, refreshFailures - 1));
    $("connection").textContent = "Reconnexion automatique · " + (error.code === "timeout" ? "tunnel lent" : "serveur indisponible");
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
  stateEpoch++;
  busy = true;
  if (session?.tutorial) renderTutorial(session.tutorial);
  message("");
  $("attack").disabled = true;
  try {
    let data;
    let currentParams = params;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        data = await api("/api/commands", {request_id: requestId(), action, params: currentParams});
        break;
      } catch (error) {
        if (error.code !== "stale_revision" || !currentParams.session_id || attempt === 4) throw error;
        const state = await api("/api/state");
        if (!state.session || state.session.id !== currentParams.session_id) throw error;
        if (!session || session.id !== state.session.id || state.session.revision >= session.revision) session = state.session;
        currentParams = {...currentParams, revision: session.revision, ...(["move", "travel", "explore"].includes(action) && session.tutorial?.world_context ? {world_context: session.tutorial.world_context} : {})};
        if (action === "battle_move" && session.tutorial?.battle) {
          const battle = session.tutorial.battle;
          currentParams.path = gridPath(battle.map, battle.players[session.me].position, [currentParams.x, currentParams.y]);
        }
        if (action === "unit_order" && currentParams.order === "move" && session.tutorial?.battle) {
          const battle = session.tutorial.battle;
          currentParams.paths = Object.fromEntries(currentParams.units.map(id => [id, gridPath(battle.map, battle.summons[id].position, currentParams.target)]));
        }
      }
    }
    if (!session || session.id !== data.session.id || data.session.revision >= session.revision) session = data.session;
    sessionId = session.id;
    remember();
    if (data.invite) {
      sessionStorage.setItem("rpg-invite", data.invite);
      sessionStorage.setItem("rpg-invite-session", session.id);
      $("invite-code").textContent = data.invite;
      $("invite-link").value = invitationLink(data.invite);
      $("invite-status").textContent = "Invitation créée · valable 30 minutes. Partagez le lien ou le code avec votre compagnon.";
      message("Invitation créée. Le lien et le code sont affichés ci-dessus.");
      $("party-tutorial").disabled = session.players.length !== 2;
      $("invitation").hidden = false;
    }
    if (action === "join") message("Vous avez rejoint votre compagnon. Le créateur peut démarrer le tutoriel.");
    if (session.state !== "lobby") $("invitation").hidden = true;
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
    if (lastPlayer) render({player: lastPlayer});
    else if (session?.tutorial) renderTutorial(session.tutorial);
    const pending = pendingBattleMove;
    pendingBattleMove = null;
    if (pending && session?.id === pending.sessionId && session.tutorial?.battle && session.tutorial.encounter_number === pending.encounter) {
      const actor = session.tutorial.players.find(player => player.id === session.me);
      if (actor.hp > 0 && !actor.stunned && !actor.casting && (!pending.controlledIds || JSON.stringify(pending.controlledIds) === JSON.stringify(controlledUnits(session.tutorial, session.me).map(([id]) => id).sort()))) await moveControlled(session.tutorial, actor, pending.destination);
    }
    await refresh(true);
  }
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
for (const view of ["stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"]) $(`show-${view}`).addEventListener("click", () => showView(view));
$("map-place").addEventListener("change", () => { mapPlace = $("map-place").value; mapPoint = ""; showView("map"); });
$("back-view").addEventListener("click", () => showView(session?.tutorial?.mob ? "combat" : "standby"));
$("combat-target").addEventListener("change", () => {
  combatTarget = $("combat-target").value;
  focusedMob = combatTarget;
  if (session?.tutorial) renderTutorial(session.tutorial);
});
$("chat-form").addEventListener("submit", async event => {
  event.preventDefault();
  if ($("send-chat").disabled) return;
  $("send-chat").disabled = true;
  try {
    const chat = await api("/api/chat", {channel: $("chat-channel").value, message: $("chat-message").value, session_id: session?.id || null});
    $("chat-message").value = ""; $("chat-status").textContent = "Message envoyé."; renderChat(chat);
  } catch (error) { $("chat-status").textContent = error.message; }
  finally { $("send-chat").disabled = false; }
});
$("create").addEventListener("click", () => command("create"));
$("tutorial").addEventListener("click", () => command("tutorial"));
$("party-tutorial").addEventListener("click", () => command("tutorial"));
$("join-form").addEventListener("submit", event => {
  event.preventDefault();
  command("join", {invite: invitationCode($("invite-input").value)});
});
for (const action of ["start", "attack", "leave"]) $(action).addEventListener("click", () => {
  if (session) command(action, {session_id: session.id, revision: session.revision, ...(action === "attack" ? {target: $("duel-target").value} : {})});
});
$("new-room").addEventListener("click", () => command("create"));
$("logout").addEventListener("click", () => {
  $("chat-panel").hidden = true;
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
$("copy-invite-link").addEventListener("click", () => copy($("invite-link").value, "invite-link"));
$("copy-invite").addEventListener("click", () => copy($("invite-code").textContent, "invite-code"));
const incomingInvite = location.hash.match(/^#invite=([A-Za-z0-9_-]{16,64})$/)?.[1];
if (incomingInvite) { $("invite-input").value = incomingInvite; history.replaceState(null, "", location.pathname + location.search); }
const invite = sessionStorage.getItem("rpg-invite");
if (invite) { $("invite-code").textContent = invite; $("invite-link").value = invitationLink(invite); $("invitation").hidden = false; }
window.addEventListener("online", () => refresh(true));
window.addEventListener("pageshow", () => refresh(true));
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(true); });
setInterval(refresh, location.hostname === "localhost" || location.hostname === "127.0.0.1" ? 250 : 1000);
refresh();

for (const id of ["bestiary-map", "bestiary-search", "bestiary-sort"]) $(id).addEventListener(id === "bestiary-search" ? "input" : "change", () => { if (session?.tutorial) renderTutorial(session.tutorial); });
