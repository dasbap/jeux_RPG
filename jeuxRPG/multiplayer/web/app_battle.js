"use strict";
function requestTravel(destination) {
  const adventure = session?.tutorial;
  if (!adventure) return;
  if (adventure.field_map && adventure.battle) {
    const site = adventure.battle.map?.sites?.find(item => item.id === destination);
    if (site) {
      const me = adventure.players.find(player => player.id === session.me);
      if (!me) return;
      return moveControlled(adventure, me, site.position);
    }
    if (adventure.battle.hostiles_alive) return message("Terminez le combat avant de voyager.");
  } else if (adventure.battle) return message("Terminez le combat avant de voyager.");
  return tutorialCommand("move", {destination});
}
function selectEntity(id) {
  tacticalInteractionUntil = Date.now() + 500;
  focusedMob = focusedMob === id ? "" : id;
  combatTarget = focusedMob;
  focusedEnemy = session.tutorial.mobs?.some(mob => mob.combat_id === focusedMob && mob.stats.hp.current > 0) ? focusedMob : "";
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
    kept.add(card);
    const signature = JSON.stringify([unitName(unit), unit.hp, unit.max_hp, unit.energies, unit.hidden, unit.detected, unit.stunned, unit.effects]);
    if (card.vitalsSignature === signature) continue;
    card.vitalsSignature = signature;
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
      const bar = row.querySelector("progress"); bar.max = Math.max(1, resource.max); bar.value = Math.max(0, resource.current); bar.className = resource.type === "PV" ? "vitals-hp" : "vitals-energy"; bar.dataset.energy = resource.type.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/[^a-z]/g, ""); bar.setAttribute("aria-label", `${resource.type === "Foie" ? "Foi" : resource.type} de ${unitName(unit)}`);
      row.querySelector("span").textContent = `${Number(resource.current.toFixed(1))}/${resource.max} ${resource.type === "Foie" ? "Foi" : resource.type}`;
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
  const unit = adventure.battle.players[me.id];
  if (unit.route.length && unit.route.at(-1).join(",") === destination.join(",")) return;
  const path = gridPath(adventure.battle.map, unit.position, destination);
  if (path === null) return message("Ce chemin est inaccessible : vérifiez les passages sur la carte.", true);
  if (path.length) return tutorialCommand("battle_move", {x, y, path});
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
  const obstacles = new Set([...(map.cover || []), ...(map.blocked || [])].map(p => p.join(",")));
  const blocked = (x, y) => x < 0 || y < 0 || x >= map.width || y >= map.height || obstacles.has(`${x},${y}`);
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
  if (fieldCamera?.map !== map.id) fieldCamera = {map: map.id, span: Math.min(map.width, 24), x: unit.position[0], y: unit.position[1], follow: true};
  if (fieldCamera.follow) { fieldCamera.x = unit.position[0]; fieldCamera.y = unit.position[1]; }
  const bounds = $("world-map").getBoundingClientRect();
  const measured = bounds.width > 0 && bounds.height > 0;
  const aspect = measured ? bounds.width / bounds.height : 1 / .67;
  const height = Math.min(map.height, measured ? Math.min(map.width, fieldCamera.span) / aspect : Math.ceil(Math.min(map.width, fieldCamera.span) * .67));
  const width = measured ? Math.min(map.width, fieldCamera.span, height * aspect) : Math.min(map.width, fieldCamera.span);
  const left = Math.max(0, Math.min(map.width - width, fieldCamera.x - width / 2));
  const top = Math.max(0, Math.min(map.height - height, fieldCamera.y - height / 2));
  svg.setAttribute("viewBox", `${left * 40} ${top * 40} ${width * 40} ${height * 40}`);
  svg.onwheel = event => { event.preventDefault(); adjustFieldCamera(event.deltaY > 0 ? "out" : "in"); };
  svg.setAttribute("class", "battle-map");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", map.name);
  const element = (tag, attrs, text = "") => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    node.textContent = text;
    return node;
  };
  mapPatterns(svg, element);
  svg.setAttribute("clip-path", "inset(0)");
  const inView = position => position[0] + .5 >= left && position[0] + .5 < left + width && position[1] + .5 >= top && position[1] + .5 < top + height;
  const explored = adventure.field_map ? new Set((battle.explored || []).map(point => point.join(","))) : null;
  for (let y = Math.floor(top); y < Math.ceil(top + height); y++) for (let x = Math.floor(left); x < Math.ceil(left + width); x++) {
    const discovered = !explored || explored.has(`${x},${y}`);
    const cover = map.cover.some(p => p[0] === x && p[1] === y);
    const water = (map.water || []).some(p => p[0] === x && p[1] === y);
    const bridge = (map.bridges || []).some(p => p[0] === x && p[1] === y);
    const road = (map.paths || []).some(p => p[0] === x && p[1] === y);
    const gate = map.exits?.find(gate => gate.position[0] === x && gate.position[1] === y);
    const exit = adventure.field_map ? Boolean(gate) : (battle.exit || [0, Math.floor(map.height / 2)]).join(",") === `${x},${y}`;
    const cell = terrainCell(map, x, y, element, discovered, exit);
    cell.setAttribute("aria-label", exit ? gate?.name || "Sortie du champ de bataille · fuite possible" : cover ? `Couverture ${x},${y}` : `Marcher en ${x},${y}`);
    const move = () => {
      if (disabled) return;
      if (water && !bridge) return message("La rivière est infranchissable : rejoignez un pont.");
      if (cover) return message("Cette case est occupée par une couverture.");
      moveControlled(adventure, me, [x, y]);
    };
    cell.onclick = () => { inspectedCell = [x, y]; renderTutorial(session.tutorial, true); };
    cell.ondblclick = move;
    cell.onkeydown = event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); move(); } };
    svg.append(cell);
    if (exit) {
      const label = element("text", {x: x * 40 + 20, y: y * 40 + 24, class: "exit-label", "text-anchor": "middle", "pointer-events": "none"}, gate?.name || "Sortie");
      svg.append(label);
    }
  }
  decorateMap(svg, map, element, {left, top, width, height}, explored);
  for (const site of map.sites || []) {
    if (!inView(site.position) || explored && !explored.has(site.position.join(","))) continue;
    const node = element("g", {class: "battle-unit field-site", "data-site": site.id});
    node.append(element("circle", {cx: site.position[0] * 40 + 20, cy: site.position[1] * 40 + 20, r: 13}));
    node.append(element("text", {x: site.position[0] * 40 + 20, y: site.position[1] * 40 + 42}, site.name));
    node.onclick = () => {
      inspectedCell = site.position;
      renderTutorial(session.tutorial, true);
      const nearby = Math.hypot(unit.position[0] - site.position[0], unit.position[1] - site.position[1]) <= 1.5;
      if (nearby && (site.id === "mira" && (adventure.step === "village" || adventure.step === "hunt" && adventure.kills >= (adventure.hunt_goal || 3)) || site.dialogue)) tutorialCommand("talk", {npc: site.id});
      else if (!nearby && site.id === "mira") message("Approchez-vous de Mira : double-cliquez sur sa position pour marcher jusqu’à elle.");
      else if (!nearby && site.dialogue) message(`Approchez-vous de ${site.name} : double-cliquez sur sa position pour marcher jusqu’à lui parler.`);
      else message(site.name);
    };
    node.ondblclick = () => moveControlled(adventure, me, site.position);
    svg.append(node);
  }
  for (const [, ally] of controlledUnits(adventure, me.id)) for (const step of ally.route.filter(inView)) svg.append(element("circle", {cx: step[0] * 40 + 20, cy: step[1] * 40 + 20, r: 3, class: "route-dot"}));
  for (const step of unit.route.filter(inView)) svg.append(element("circle", {cx: step[0] * 40 + 20, cy: step[1] * 40 + 20, r: 3, class: "route-dot"}));
  const draw = (id, position, label, className) => {
    if (!inView(position)) return null;
    const group = element("g", {class: `battle-unit ${className}`, "data-unit": id});
    group.append(element("circle", {cx: position[0] * 40 + 20, cy: position[1] * 40 + 20, r: 13}));
    group.append(element("text", {x: position[0] * 40 + 20, y: position[1] * 40 + 25}, label));
    if (id === focusedMob) group.append(element("circle", {cx: position[0] * 40 + 20, cy: position[1] * 40 + 20, r: 18, class: "objective-ring"}));
    group.onclick = () => selectEntity(id);
    group.ondblclick = event => { event.preventDefault(); const current = entityPosition(session.tutorial, id); if (current) approachEntity(current); };
    svg.append(group);
    return group;
  };
  for (const player of adventure.players) draw(player.id, battle.players[player.id].position, player.id === me.id ? "Vous" : player.name.slice(0, 3), battle.players[player.id].hidden ? "hidden-player" : "visible-player");
  for (const player of presenceState?.nearby || []) {
    if (!player.position || player.map !== adventure.field_map && player.map !== battle.map.id || adventure.players.some(member => member.id === player.id)) continue;
    const x = Math.round(player.position[0]), y = Math.round(player.position[1]);
    if (x < 0 || y < 0 || x >= map.width || y >= map.height || explored && !explored.has(`${x},${y}`)) continue;
    const group = element("g", {class: `world-player ${player.ally ? "world-ally" : "world-traveller"}`, "data-nearby": player.id});
    group.append(element("circle", {cx: player.position[0] * 40 + 20, cy: player.position[1] * 40 + 20, r: 11}));
    group.append(element("text", {x: player.position[0] * 40 + 20, y: player.position[1] * 40 + 25, "text-anchor": "middle"}, player.name.slice(0, 3)));
    group.append(element("title", {}, `${player.name} · ${player.ally ? "Allié" : "Joueur"} · PvP désactivé`));
    svg.append(group);
  }
  for (const [index, mob] of adventure.mobs.entries()) { const mark = {goblin: "G", orc: "O", dragon_whelp: "D"}[mob.mob_id] || "G"; const number = mob.combat_id.match(/(?:-mob-|^mob-)(\d+)/); draw(mob.combat_id, mob.position, `${mark}${number ? Number(number[1]) + 1 : index + 1}`, "enemy-unit"); }
  for (const [id, summon] of Object.entries(battle.summons || {})) {
    const number = id.match(/:summon:(\d+)$/);
    const label = number ? `S${Number(number[1]) + 1}` : "S";
    const summonNode = draw(id, summon.position, summon.controlled ? `${label}★` : label, "summon-unit");
    summonNode?.append(element("title", {}, `${summon.name} · ${summon.hp}/${summon.max_hp} PV`));
  }
  for (const corpse of battle.corpses) draw(corpse.id, corpse.position, "✝", "corpse-unit");
  const gateMarkers = map.exits?.length ? map.exits : [{position: battle.exit || [0, Math.floor(map.height / 2)], name: "Sortie"}];
  const usedGateMarkers = [];
  for (const gate of gateMarkers) {
    const [gx, gy] = gate.position;
    const baseX = Math.max(left + .5, Math.min(left + width - .5, gx + .5)) * 40;
    const baseY = Math.max(top + .5, Math.min(top + height - .5, gy + .5)) * 40;
    let x = baseX, y = baseY;
    for (let step = 0; usedGateMarkers.some(p => Math.hypot(p[0] - x, p[1] - y) < 34) && step < (width + height) * 4; step++) {
      const distance = (Math.floor(step / 4) + 1) * 36;
      const direction = step % 4;
      x = Math.max((left + .5) * 40, Math.min((left + width - .5) * 40, baseX + (direction === 2 ? distance : direction === 3 ? -distance : 0)));
      y = Math.max((top + .5) * 40, Math.min((top + height - .5) * 40, baseY + (direction === 0 ? distance : direction === 1 ? -distance : 0)));
    }
    usedGateMarkers.push([x, y]);
    const marker = element("g", {class: "battle-unit exit-marker", "data-exit": gate.position.join(","), role: "button", tabindex: "0", "aria-label": gate.name || "Sortie"});
    marker.append(element("circle", {cx: x, cy: y, r: 16}), element("text", {x, y: y + 5}, "⇥"), element("title", {}, gate.name || "Sortie"));
    marker.onclick = () => { inspectedCell = gate.position; message(gate.name || "Sortie"); };
    marker.ondblclick = () => moveControlled(adventure, me, gate.position);
    marker.onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); moveControlled(adventure, me, gate.position); } };
    svg.append(marker);
  }
  const previousMap = $("world-map").querySelector(".battle-map");
  if (previousMap && previousMap.getAttribute("viewBox") === svg.getAttribute("viewBox")) {
    const nodes = [...svg.children].map(node => {
      const selector = node.dataset.unit ? `[data-unit="${node.dataset.unit}"]` : node.dataset.cell ? `[data-cell="${node.dataset.cell}"]` : null;
      const retained = node.tagName.toLowerCase() === "defs" ? previousMap.querySelector("defs") : selector && previousMap.querySelector(selector);
      if (retained && node.tagName.toLowerCase() === "defs") return retained;
      if (!retained) return node;
      for (const attr of [...retained.attributes]) if (!node.hasAttribute(attr.name)) retained.removeAttribute(attr.name);
      for (const attr of node.attributes) if (retained.getAttribute(attr.name) !== attr.value) retained.setAttribute(attr.name, attr.value);
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
    previousMap.onwheel = svg.onwheel;
  } else $("world-map").replaceChildren(svg);
  const retainedCards = new Set();
  for (const mob of adventure.mobs) {
    const card = [...$("mob-cards").children].find(node => node.dataset.mob === mob.combat_id) || document.createElement("article"); retainedCards.add(card); card.className = "mob-card"; card.tabIndex = 0; card.setAttribute("role", "group"); card.dataset.mob = mob.combat_id;
    let vitals = card.querySelector(".enemy-vitals");
    if (!vitals) { vitals = document.createElement("div"); vitals.className = "enemy-vitals"; card.append(vitals); }
    renderVitals(vitals, [{...mob, id: mob.combat_id, hp: mob.stats.hp.current, max_hp: mob.stats.hp.max}]);
    card.classList.toggle("selected", focusedMob === mob.combat_id);
    let quick = card.querySelector(".mob-quick-actions");
    if (!quick) {quick = document.createElement("div");quick.className = "mob-quick-actions";card.append(quick);}
    quick.ondblclick = event => event.stopPropagation();
    const retainedQuick = new Set();
    const target = {id:mob.combat_id, position:mob.position, hp:mob.stats.hp.current, max_hp:mob.stats.hp.max, enemy:true};
    for (const category of ["offense", "buff", "debuff"]) {
      const skill = favoriteSkill(me, category, me.skills.filter(value => skillCategory(value) === category));
      if (!skill || !["DAMAGE", "DEBUFF"].includes(skill.type)) continue;
      const button = [...quick.children].find(node => node.dataset.quickSkill === skill.name) || document.createElement("button");
      button.type = "button";button.dataset.quickSkill = skill.name;button.textContent = skillGlyph(skill, category);button.title = skill.name;button.setAttribute("aria-label", `${skill.name} sur ${mob.name}`);
      button.disabled = busy || !skillAllowed(me, skill, target, mob);
      button.onclick = event => {event.stopPropagation();if (button.disabled || busy) return;combatTarget = mob.combat_id;focusedMob = "";tutorialCommand("skill", {skill_name:skill.name,target:mob.combat_id});};
      retainedQuick.add(button);if (button.parentElement !== quick) quick.append(button);
    }
    for (const button of [...quick.children]) if (!retainedQuick.has(button)) button.remove();
    card.onkeydown = event => {if (event.target === card && ["Enter", " "].includes(event.key)) {event.preventDefault();selectEntity(mob.combat_id);}};
    card.onclick = () => selectEntity(mob.combat_id);
    card.ondblclick = event => { event.preventDefault(); const current = entityPosition(session.tutorial, mob.combat_id); if (current) approachEntity(current); };
    if (card.parentElement !== $("mob-cards")) $("mob-cards").append(card);
  }
  for (const card of [...$("mob-cards").children]) if (!retainedCards.has(card)) card.remove();
  renderVitals("combat-stats-details", adventure.players.flatMap(player => player.invocations));
  renderVitals("combat-resources", adventure.players.map(player => ({...player, hidden: battle.players[player.id].hidden, detected: battle.players[player.id].detected})));
  if (sectionChanged("intents", battle.intents)) {
  const table = document.createElement("table");
  for (const intent of battle.intents) {
    const row = document.createElement("tr");
    for (const text of [intent.name, intent.action, intent.remaining_seconds > 0 && /Entaille|Appel/.test(intent.action) ? `${intent.remaining_seconds.toFixed(1)} s` : ""]) { const cell = document.createElement("td"); cell.textContent = text; row.append(cell); }
    table.append(row);
  }
  $("enemy-intents").replaceChildren(table);
  }
  $("tactical-actions").replaceChildren();
  const hide = document.createElement("button"); hide.textContent = "◈"; hide.title = unit.hidden ? "Vous êtes dissimulé" : "Se cacher derrière une couverture"; hide.setAttribute("aria-label", hide.title);
  hide.disabled = disabled || unit.hidden || unit.can_hide === false || !map.cover.some(p => Math.hypot(unit.position[0] - p[0], unit.position[1] - p[1]) <= 1.5);
  hide.addEventListener("click", () => tutorialCommand("hide"));
  if (!hide.disabled) $("tactical-actions").append(hide);
  else if (unit.hidden) { const label = document.createElement("p"); label.textContent = "Dissimulé · déplacement couvert à vitesse réduite"; $("tactical-actions").append(label); }
  $("corpse-actions").replaceChildren();
  for (const corpse of battle.corpses) {
    if (Math.hypot(unit.position[0] - corpse.position[0], unit.position[1] - corpse.position[1]) > 1.5) continue;
    const button = document.createElement("button"); button.textContent = "✂";
    button.title = corpse.harvested.length ? `${corpse.name} · déjà dépecé` : `Dépecer ${corpse.name}`;
    button.setAttribute("aria-label", button.title);
    button.disabled = disabled || corpse.harvested.length > 0 || Math.hypot(unit.position[0] - corpse.position[0], unit.position[1] - corpse.position[1]) > 1.5;
    button.addEventListener("click", () => tutorialCommand("harvest", {target: corpse.id})); $("corpse-actions").append(button);
  }

}
