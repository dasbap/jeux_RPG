"use strict";
function worldPaths(adventure, destination) {
  const graph = adventure.world.graph;
  if (!graph) return null;
  const sources = new Set([adventure.position]);
  if (adventure.transit) { sources.add(adventure.transit.source); sources.add(adventure.transit.destination); }
  return Object.fromEntries([...sources].map(source => {
    const queue = [[source, []]], visited = new Set();
    for (const [node, route] of queue) {
      if (node === destination) return [source, route];
      if (visited.has(node)) continue;
      visited.add(node);
      for (const next of graph[node] || []) if (!visited.has(next)) queue.push([next, [...route, next]]);
    }
    return [source, null];
  }));
}
function tutorialCommand(action, params = {}) {
  if (["move", "travel"].includes(action) && session?.tutorial) {
    const paths = worldPaths(session.tutorial, params.destination);
    if (paths) params = {...params, paths};
  }
  if (session) return command(action, {session_id: session.id, revision: session.revision, ...(["battle_move", "stop_move", "unit_order", "strike", "skill", "hide", "harvest", "control_units", "unit_skill", "leave_battle"].includes(action) ? {encounter: session.tutorial.encounter_number} : {}), ...(["move", "travel", "explore", "talk"].includes(action) && session.tutorial.world_context ? {world_context: session.tutorial.world_context} : {}), ...params});
}
function paragraphs(container, texts) {
  $(container).replaceChildren();
  for (const text of texts) {
    const p = document.createElement("p");
    p.textContent = text;
    $(container).append(p);
  }
}
function mountWorldMap(source, container = $("world-map")) {
  const retained = [...container.children].find(node => node.dataset.map === source.dataset.map);
  if (!retained) { container.append(source); installWorldCamera(source); return source; }
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
  installWorldCamera(retained);
  return retained;
}
function equipmentBonuses(piece) {
  return [["hp", "PV"], ["endurance", "endurance"], ["force", "force"], ["intelligence", "intelligence"], ["sagesse", "sagesse"]].filter(([key]) => piece[key] > 0).map(([key, label]) => `+${piece[key]} ${label}`).join(" · ");
}
function renderWorld(adventure, me, mapContainer = $("world-map")) {
  paragraphs("equipment-details", me.gear.length ? me.gear.map(p => `${p.name} +${p.level} · ${equipmentBonuses(p)}`) : ["Aucun équipement équipé. La forge propose six pièces indépendantes."]);
  const items = Object.entries(me.inventory).filter(([, quantity]) => quantity > 0);
  paragraphs("inventory-details", items.length ? items.map(([item, quantity]) => `${quantity} ${item} · matériau pour la forge`) : ["Votre inventaire est vide."]);
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
  const generalWidth = Math.max(610, ...places.map(p => p.x + 130)), generalHeight = Math.max(260, ...places.map(p => p.y + 70));
  const svg = svgElement("svg", {viewBox: `0 0 ${generalWidth} ${generalHeight}`, role: "group", "aria-label": "Carte des lieux et chemins découverts", class: "zone-map"});
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
  for (const member of socialState?.team?.members || []) {
    if (!member.online || member.player_id === me.id) continue;
    const place = places.find(point => point.id === member.zone);
    if (!place) continue;
    const group = svgElement("g", {class: "world-player world-ally", "data-ally": member.player_id});
    group.append(svgElement("circle", {cx: place.x + 24, cy: place.y - 12, r: 8}));
    group.append(svgElement("text", {x: place.x + 24, y: place.y - 28, class: "place-label"}, member.name));
    group.append(svgElement("title", {}, `${member.name} · ${member.location} · serveur ${member.realm}`));
    svg.append(group);
  }
  if (mapMarker) {
    const marker = world.objectives.find(m => m.zone === mapMarker.zone && m.point === mapMarker.point);
    if (marker) svg.append(svgElement("circle", {cx: marker.x, cy: marker.y, r: 24, class: "objective-ring", "aria-label": "Objectif à découvrir ou rejoindre"}));
  }
  svg.dataset.map = "general";
  const worldMapNodes = [mountWorldMap(svg, mapContainer)];
  if (place.points.length) {
    const entry = place.entry || [70, 110];
    const localWidth = Math.max(610, entry[0] + 130, ...place.points.map(p => (p.x ?? 450) + 130)), localHeight = Math.max(220, entry[1] + 70, ...place.points.map(p => (p.y ?? 175) + 70));
    const local = svgElement("svg", {viewBox: `0 0 ${localWidth} ${localHeight}`, role: "group", "aria-label": `Points de ${place.name}`, class: "zone-map"});
    local.append(svgElement("text", {x: localWidth / 2, y: 20, class: "place-label"}, `Points de ${place.name}`));
    local.append(svgElement("circle", {cx: entry[0], cy: entry[1], r: 10, class: "visited-node"}));
    local.append(svgElement("text", {x: entry[0], y: entry[1] + 28, class: "place-label"}, "Entrée"));
    if (adventure.position === place.id) local.append(svgElement("text", {x: entry[0], y: entry[1] - 25, class: "place-label"}, "Vous êtes ici"));
    const positions = new Map([[place.id, {x: entry[0], y: entry[1]}], ...place.points.map((point, index) => [point.id, {x: point.x ?? (index % 2 ? 450 : 270), y: point.y ?? (index < 2 ? 65 : 175)}])]);
    for (const [source, position] of positions) for (const destination of world.graph[source] || []) {
      const endpoint = positions.get(destination);
      if (endpoint && source < destination) local.append(svgElement("line", {x1: position.x, y1: position.y, x2: endpoint.x, y2: endpoint.y, class: "known-route"}));
    }
    place.points.forEach(point => {
      const {x, y} = positions.get(point.id);
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
    worldMapNodes.push(mountWorldMap(local, mapContainer));
  }
  for (const child of [...mapContainer.children]) if (!worldMapNodes.includes(child)) child.remove();
  paragraphs("place-details", [`${place.name} · ${place.type} · ${place.id === world.current ? "vous êtes ici" : place.visited ? "déjà visité" : "encore non visité"}`, place.description]);
  $("map-routes").replaceChildren();
  for (const route of world.routes.filter(r => r.from === place.id || r.to === place.id)) {
    const p = document.createElement("p");
    p.textContent = `${route.name} · ${route.distance_km} km · ${(route.distance_km / 6 * 3600 / 3).toFixed(0)} s de marche : ${places.find(p => p.id === route.from).name} ${route.bidirectional === false ? "→" : "↔"} ${places.find(p => p.id === route.to).name}`;
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
      `Matériaux donnés par victoire : ${mob.loot.map(item => `${item.quantity === item.max_quantity ? item.quantity : `${item.quantity}–${item.max_quantity}`} ${item.item} (${(100 * item.chance).toFixed(1)} %, ${item.attempts} tirage(s))`).join(", ")}`,
      `Expérience de référence au niveau 1 : ${mob.xp.hunt} XP. Varie selon le niveau du mob et du joueur qui porte le dernier coup. Entraînement : aucun butin ni XP.`,
      `Cartes de spawn découvertes : ${[...(mob.spawn_maps || [])].sort((a, b) => a.name.localeCompare(b.name) * ($("bestiary-sort").value === "desc" ? -1 : 1)).map(p => p.name).join(", ")}`,
      `Matériaux rares au dépeçage : ${(mob.rare_loot || []).map(p => `${p.item} (${(100 * p.chance).toFixed(1)} %, ${p.attempts} tirage(s), ${p.min}–${p.max} par réussite)`).join(", ")}`, `Capacités : ${(mob.abilities || []).map(a => `${a.name} (niveau ${a.level})`).join(", ") || "attaque classique"}`, mob.materials_usage]) {
      const p = document.createElement("p");
      p.textContent = text;
      card.append(p);
    }
    $("bestiary-details").append(card);
  }
}
function toggleGameMenu(open = $("game-menu-items").hidden) {
  $("game-menu-items").hidden = !open;
  $("game-menu-toggle").setAttribute("aria-expanded", String(open));
}
function showView(view) {
  toggleGameMenu(false);
  if (currentView === view && document.body.classList.contains("hud-menu-open")) {document.body.classList.remove("hud-menu-open");currentView = "map";if(session?.tutorial) renderTutorial(session.tutorial);return;}
  if (["social", "options", "stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"].includes(view)) currentView = view;
  document.body.classList.toggle("hud-menu-open", Boolean(session?.tutorial));
  renderSocial();
  if (session && session.tutorial) renderTutorial(session.tutorial);
}
