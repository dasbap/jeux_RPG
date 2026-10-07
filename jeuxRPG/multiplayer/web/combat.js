"use strict";
function renderSkillHud(adventure, me, mob, canAttack, selected) {
  const root = $("skill-hud");
  if (!root) return;
  const categories = {
    offense: me.skills.filter(skill => skillCategory(skill) === "offense").slice(0, 5),
    buff: me.skills.filter(skill => skillCategory(skill) === "buff").slice(0, 5),
    debuff: me.skills.filter(skill => skillCategory(skill) === "debuff").slice(0, 5),
  };
  const popover = $("skill-popover"), tooltip = $("skill-tooltip");
  let openCategory = root.dataset.openCategory || "";
  const closePopover = () => { openCategory = ""; root.dataset.openCategory = ""; popover.hidden = true; popover.replaceChildren(); };
  const hideTooltip = () => { tooltip.hidden = true; tooltip.textContent = ""; };
  const showTooltip = (element, skill) => {
    tooltip.textContent = `${skill.name} — ${skillDetails(skill)}`;
    tooltip.hidden = false;
    tooltip.dataset.anchor = element.dataset.skill || skill.name;
  };
  function bindHold(element, shortAction, longAction, skill = null) {
    element.hudShortAction = shortAction;
    element.hudLongAction = longAction || (skill ? () => showTooltip(element, skill) : null);
    if (element.dataset.holdBound) return;
    element.dataset.holdBound = "true";
    element.addEventListener("pointerdown", event => {
      if (event.button !== 0 || busy || root.hudGesture) return;
      event.preventDefault();
      root.classList.remove("collapsed");
      const gesture = {pointerId:event.pointerId, start:element, over:element, held:false, timer:0};
      root.hudGesture = gesture;
      root.setPointerCapture?.(event.pointerId);
      gesture.timer = setTimeout(() => {
        if (root.hudGesture !== gesture) return;
        gesture.held = true;
        gesture.over?.hudLongAction?.();
      }, 420);
    });
    element.onclick = event => {event.preventDefault(); if (event.detail === 0 && !busy) element.hudShortAction?.();};
    element.onkeydown = event => {if (["ArrowDown", "F2"].includes(event.key)) {event.preventDefault(); element.hudLongAction?.();}};
  }
  function useSkill(skill) {
    const [target] = skillTargets(adventure, me, skill, mob);
    if (!target) return message(`Aucune cible valide pour ${skill.name}.`);
    combatTarget = target.id;
    focusedMob = ""; focusedEnemy = "";
    tutorialCommand("skill", {skill_name: skill.name, target: target.id});
  }
  function iconButton(skill, category, extraClass = "", retained = null) {
    const button = retained || document.createElement("button");
    button.type = "button";
    button.className = `skill-icon skill-${category} ${extraClass}`;
    button.dataset.skill = skill.name;
    button.setAttribute("aria-label", skill.name);
    const glyph = skillGlyph(skill, category);
    if (button.textContent !== glyph) button.textContent = glyph;
    const [target] = skillTargets(adventure, me, skill, mob);
    button.disabled = busy;
    button.classList.toggle("skill-unavailable", !target);
    button.setAttribute("aria-disabled", String(!target));
    bindHold(button, () => { saveFavoriteSkill(me, category, skill); closePopover(); useSkill(skill); }, null, skill);
    return button;
  }
  function openMenu(category, anchor) {
    if (openCategory === category && !popover.hidden) return closePopover();
    openCategory = category; root.dataset.openCategory = category;
    popover.replaceChildren();
    popover.className = `skill-popover skill-popover-${category}`;
    for (const skill of categories[category]) popover.append(iconButton(skill, category, "skill-choice"));
    popover.classList.add(`arc-count-${categories[category].length}`);
    popover.hidden = !categories[category].length;
    if (!popover.hidden) popover.dataset.anchor = anchor.id;
  }
  for (const [category, containerId] of [["offense","skill-offense"],["buff","skill-buff"],["debuff","skill-debuff"]]) {
    const container = $(containerId);
    const skill = favoriteSkill(me, category, categories[category]);
    if (!skill) { container.hidden = true; container.replaceChildren(); continue; }
    container.hidden = false;
    const retained = container.firstElementChild?.dataset.skill === skill.name ? container.firstElementChild : null;
    const button = iconButton(skill, category, "skill-favorite", retained);
    bindHold(button, () => useSkill(skill), () => openMenu(category, container), skill);
    if (!retained) container.replaceChildren(button);
  }
  const attack = $("skill-main-attack");
  const attackButton = attack.firstElementChild || document.createElement("button");
  attackButton.type = "button";
  attackButton.className = "skill-icon skill-attack";
  attackButton.setAttribute("aria-label", "Attaque simple");
  if (attackButton.textContent !== "⚔") attackButton.textContent = "⚔";
  const attackCandidates = (adventure.mobs || []).map(m => ({id:m.combat_id,name:m.name,position:m.position,hp:m.stats.hp.current,max_hp:m.stats.hp.max,enemy:true}));
  const attackAvailable = Boolean(selected?.enemy && canAttack(selected) || attackCandidates.some(canAttack));
  attackButton.disabled = busy;
  attackButton.classList.toggle("skill-unavailable", !attackAvailable);
  attackButton.setAttribute("aria-disabled", String(!attackAvailable));
  bindHold(attackButton, () => {
    const enemies = (adventure.mobs || []).map(m => ({id:m.combat_id,name:m.name,position:m.position,hp:m.stats.hp.current,max_hp:m.stats.hp.max,enemy:true}));
    const target = (selected?.enemy && canAttack(selected) ? selected : enemies.filter(canAttack).sort((a,b) => a.hp - b.hp)[0]);
    if (!target) return message("Aucune cible à portée pour l’attaque.");
    combatTarget = target.id; focusedMob = ""; focusedEnemy = "";
    tutorialCommand("strike", {target: target.id});
  }, null);
  if (!attackButton.parentElement) attack.append(attackButton);
  if (!popover.hidden && openCategory) {
    for (const button of [...popover.children]) {
      const skill = categories[openCategory]?.find(value => value.name === button.dataset.skill);
      if (skill) iconButton(skill, openCategory, "skill-choice", button); else button.remove();
    }
  }
  root.hudHideTooltip = hideTooltip;
  if (!root.dataset.gestureBound) {
    root.dataset.gestureBound = "true";
    root.addEventListener("pointermove", event => {
      const gesture = root.hudGesture;
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      event.preventDefault();
      const hit = document.elementFromPoint?.(event.clientX, event.clientY)?.closest(".skill-icon");
      const next = hit && root.contains(hit) && !hit.disabled ? hit : null;
      if (next === gesture.over) return;
      clearTimeout(gesture.timer);
      root.hudHideTooltip?.();
      gesture.over?.classList.remove("skill-gesture-target");
      gesture.over = next;
      if (next) {
        next.classList.add("skill-gesture-target");
        if (next !== gesture.start) { gesture.held = true; next.hudLongAction?.(); }
      }
    });
    const finish = event => {
      const gesture = root.hudGesture;
      if (!gesture || event && gesture.pointerId !== event.pointerId) return;
      clearTimeout(gesture.timer);
      root.hudGesture = null;
      gesture.over?.classList.remove("skill-gesture-target");
      root.hudHideTooltip?.();
      if (root.hasPointerCapture?.(gesture.pointerId)) root.releasePointerCapture(gesture.pointerId);
      if (event?.type === "pointerup" && !busy && gesture.over && (!gesture.held || gesture.over !== gesture.start)) gesture.over.hudShortAction?.();
    };
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) root.addEventListener(type, finish);
    window.addEventListener("blur", () => finish());
    document.addEventListener("visibilitychange", () => {if (document.hidden) finish();});
  }
  root.onpointerleave = event => {
    if (event.buttons || root.hudGesture) return;
    closePopover();
    root.classList.remove("collapsed");
    hideTooltip();
  };
  root.onpointerenter = () => root.classList.remove("collapsed");
  root.onpointerdown = event => {
    if (!event.target.closest(".skill-icon")) closePopover();
  };
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
  if (fighting) {
    if ($("message").parentElement !== $("combat-action-panel")) $("combat-action-panel").prepend($("message"));
  } else if ($("message").parentElement === $("combat-action-panel")) $("registration").before($("message"));
  $("combat-layout").hidden = !fighting;
  $("field-camera").hidden = false;
  let touchMove = $("field-move-selected");
  if (!touchMove) {
    touchMove = document.createElement("button");
    touchMove.id = "field-move-selected";
    touchMove.textContent = "Marcher ici";
    touchMove.title = "Touchez une case de la carte, puis ce bouton pour vous déplacer.";
    touchMove.addEventListener("click", () => {
      if (!session?.tutorial?.battle || !inspectedCell || busy) return;
      const me = session.tutorial.players.find(player => player.id === session.me);
      if (focusedMob && entityPosition(session.tutorial, focusedMob)?.join(",") === inspectedCell.join(",")) approachEntity(inspectedCell);
      else moveControlled(session.tutorial, me, inspectedCell);
    });
    $("field-camera").append(touchMove);
  }
  let autoTarget = $("combat-auto-target");
  if (!autoTarget) {autoTarget = document.createElement("button"); autoTarget.id = "combat-auto-target"; autoTarget.textContent = "Ciblage auto"; autoTarget.onclick = () => {focusedMob=""; focusedEnemy=""; combatTarget=""; renderTutorial(session.tutorial);}; $("field-camera").append(autoTarget);}
  autoTarget.hidden = true;
  touchMove.hidden = !fighting;
  $("field-location").textContent = fighting ? adventure.battle.map.name : "Cliquez sur une carte pour choisir celle à zoomer";
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
  $("outing-vitals").hidden = fighting;
  if (!fighting) renderVitals("outing-vitals", adventure.players);
  document.body.classList.toggle("combat-active", Boolean(session?.tutorial));
  $("chat-toggle").hidden = !session?.tutorial;
  if (!fighting) combatFullscreenRequested = false;
  if (!fighting && document.fullscreenElement === $("battle")) document.exitFullscreen?.().catch(() => {});
  $("map-help").textContent = adventure.field_map ? "Carte fixe : double clic pour marcher, molette ou boutons pour zoomer, flèches pour déplacer la vue. Les sorties relient les zones." : fighting ? "Un clic inspecte les entités d’une case ; un double clic déplace le personnage ou les alliés contrôlés. Les blocs bruns servent de couverture." : "Un clic consulte un lieu ou un point ; un double clic lance le déplacement.";
  $("character-menu").hidden = false;
  $("lobby").hidden = fighting;
  const context = `${session.id}:${adventure.step}:${fighting}:${adventure.encounter_number || 0}`;
  if (context !== viewContext) {
    if (!["social", "options", "stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"].includes(currentView)) currentView = "map";
    combatTarget = "";
    focusedMob = "";
    focusedEnemy = "";
    inspectedCell = null;
    mapPlace = "";
    mapPoint = "";
    viewContext = context;
  }
  touchMove.disabled = busy || !inspectedCell;
  const me = adventure.players.find(player => player.id === session.me);
  const fieldSites = new Set((adventure.field_interactions || []).map(site => site.id));
  const canTalk = (adventure.position === "mira" && !fighting || fieldSites.has("mira")) && !adventure.moving;
  const atForge = (adventure.position === "forge" && !fighting || fieldSites.has("forge")) && !adventure.moving;
  const canCraft = atForge && adventure.step === "craft" && !me.equipment;
  const hasQuest = adventure.quest !== "unaccepted";
  $("map-view").hidden = false;
  for (const view of ["social", "options", "stats", "equipment", "inventory", "bestiary", "achievements"]) $(`${view}-view`).hidden = currentView !== view;
  $("quest-view").hidden = currentView !== "quest";
  $("combat-view").hidden = !fighting;
  $("npc-view").hidden = !canTalk;
  $("craft-view").hidden = !atForge;
  for (const id of ["npc-view", "craft-view"]) { const parent = fighting ? $("combat-action-panel") : document.querySelector(".zone-actions"); if ($(id).parentElement !== parent) parent.append($(id)); }
  const questParent = document.querySelector(".quest-box");
  if ($("quest-view").parentElement !== questParent) questParent.append($("quest-view"));
  $("standby-view").hidden = fighting || canTalk || atForge;
  $("fighters").hidden = true;
  for (const view of ["social", "options", "stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"]) {
    $(`show-${view}`).setAttribute("aria-pressed", String(currentView === view));
  }
  $("back-view").hidden = !document.body.classList.contains("hud-menu-open");
  $("back-view").textContent = fighting ? "Retour au combat" : "Retour à l'exploration";
  $("battle-title").textContent = adventure.step === "complete" ? "Aventure accomplie" : "Votre tutoriel";
  $("attack").hidden = true;
  $("leave").hidden = true;
  $("result").textContent = adventure.step === "complete" ? "Vous êtes arrivé au village de Brume." : "";
  $("location").textContent = adventure.location;
  const currentZone = adventure.world?.places?.find(place => place.id === adventure.world.current);
  const zoneKey = `${session.id}:${adventure.field_map || adventure.world.current}:${adventure.battle?.map.id || ""}`;
  if ($("zone-banner").dataset.zone !== zoneKey) {
    $("zone-banner").dataset.zone = zoneKey;
    $("zone-banner").classList.remove("zone-arrival");
    void $("zone-banner").offsetWidth;
    $("zone-banner").classList.add("zone-arrival");
  }
  $("zone-name").textContent = fighting ? adventure.battle.map.name : adventure.location;
  $("zone-level").textContent = `Niv. ${currentZone?.level ?? me.level}`;
  $("position-label").textContent = `Vous êtes ici : ${adventure.location}${fighting && adventure.transit ? " · Trajet suspendu pendant le combat" : adventure.moving ? ` · Marche : ${adventure.travel_remaining_real_seconds.toFixed(1)} s avant le prochain point` : ""}`;
  $("objective").textContent = adventure.objective;
  $("quest-progress").textContent = !hasQuest ? (adventure.quest_journal?.length ? "Quêtes des PNJ" : "Aucune quête acceptée.") : `${adventure.hunt_name || "Quête de Mira"} : ${{unaccepted: "à accepter", active: `${adventure.kills}/${adventure.hunt_goal || 3} gobelins vaincus`, completed: "accomplie"}[adventure.quest]}`;
  const vest = me.gear.find(piece => piece.slot === "torso");
  $("quest-description").textContent = vest && adventure.quest === "completed" ? adventure.step === "craft" ? "Veste fabriquée et équipée : votre objectif de forge est accompli. Attendez que votre compagnon fabrique sa veste." : adventure.step === "complete" ? "Veste fabriquée et équipée. Vous avez rejoint Brume : tutoriel terminé." : "Veste fabriquée et équipée : objectif accompli. Prochaine étape : rejoindre le village de Brume." : !hasQuest ? "Explorez les lieux et leurs points stratégiques pour rencontrer des PNJ qui proposent des quêtes." : adventure.quest === "completed" ? "Mira vous a remis votre récompense. Utilisez les matériaux de votre sac pour fabriquer et équiper votre veste à la forge." : `${adventure.hunt_description || "Battez les gobelins de la lisière puis revenez parler à Mira."} · Objectif : ${adventure.hunt_goal || 3} gobelin(s).`;
  for (const quest of adventure.quest_journal || []) $("quest-progress").textContent += ` · ${quest.name} : ${quest.progress}/${quest.count} (${quest.status === "completed" ? "accomplie" : "en cours"})`;
  $("quest-progress").textContent += ` · ${adventure.achievements?.kills || 0} créature(s) vaincue(s) dans cette aventure`;
  if (sectionChanged("character", [session.id, me])) {
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
  }
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
    if (!adventure.moving && !adventure.world.routes.some(route => route.id === adventure.position)) action("tutorial-actions", "Explorer à pied", "enter_zone");
    if (!adventure.field_mode && ["clearing", "clearing_fight", "lisiere", "hunt", "training"].includes(adventure.position)) action("tutorial-actions", "Explorer ce lieu", "explore");
  }
  if (!fighting) { if (sectionChanged("world", [adventure.world, me, currentView, mapPlace, mapPoint, mapMarker, adventure.position, adventure.moving, adventure.travel_remaining_real_seconds, busy])) renderWorld(adventure, me); renderAchievements(adventure.achievements); }
  $("npc-dialogue").textContent = adventure.step === "village" ? `Mira : ${adventure.hunt_description || "Des gobelins menacent la lisière."} · ${adventure.hunt_goal || 3} gobelin(s).` : adventure.quest === "completed" ? "Mira : merci pour votre aide ! La forge est désormais accessible." : adventure.kills < (adventure.hunt_goal || 3) ? `Mira : il reste ${(adventure.hunt_goal || 3) - adventure.kills} gobelin(s) à battre dans la lisière.` : `Mira : vous avez vaincu les ${adventure.hunt_goal || 3} gobelins ! Votre récompense vous attend. Ensuite, faites fabriquer votre veste à la forge.`;
  if (canTalk && (adventure.step === "village" || adventure.step === "hunt" && adventure.kills >= (adventure.hunt_goal || 3))) action("npc-actions", adventure.step === "village" ? "Accepter la quête" : "Rendre la quête", "talk", {npc: "mira"});
  button("quest-actions", "Localiser le lieu de la quête", () => { mapMarker = {zone: hasQuest && adventure.kills < (adventure.hunt_goal || 3) ? "lisiere" : "rosee", point: hasQuest && adventure.kills < (adventure.hunt_goal || 3) ? "hunt" : "mira"}; renderTutorial(session.tutorial); message("Le lieu de la quête est entouré sur la carte générale."); });
  $("forge-status").textContent = adventure.quest !== "completed" ? "Forge verrouillée : terminez la quête de Mira et rendez-la sur la place du village." : "Forge débloquée : fabriquez ou améliorez chaque pièce indépendamment jusqu’à +10.";
  if (vest && adventure.step === "travel" && atForge && !adventure.moving) action("craft-actions", "Rejoindre Village de Brume", "travel", {destination: "brume"});
  if (vest && adventure.quest === "completed") $("forge-status").textContent = `Veste équipée (+${vest.level}). ${adventure.step === "craft" ? "Votre compagnon doit encore fabriquer la sienne." : "Fabrication validée : rejoignez Brume pour terminer le tutoriel."}`;
  $("craft-materials").textContent = `Votre sac : ${Object.entries(me.inventory).map(([item, quantity]) => `${quantity} ${item}`).join(", ") || "aucun matériau"}.`;
  if (sectionChanged("forge", [session.id, atForge, me.forge, adventure.quest, busy])) {
  $("forge-catalogue").replaceChildren();
  if (atForge) for (const recipe of me.forge) {
    const card = document.createElement("article"); card.className = "codex-card"; card.dataset.recipe = recipe.recipe;
    const title = document.createElement("h4"); title.textContent = recipe.equipped ? `${recipe.equipped.name} +${recipe.equipped.level}` : recipe.name; card.append(title);
    const info = document.createElement("p"); info.textContent = recipe.cost ? `Coût : ${Object.entries(recipe.cost).map(([k,v]) => `${v} ${k}`).join(", ")}` : "Amélioration maximale +10 atteinte."; card.append(info);
    const bonus = document.createElement("p"); bonus.textContent = `Bonus : ${equipmentBonuses(recipe.equipped || recipe)}.`; card.append(bonus);
    const adjective = document.createElement("p"); adjective.textContent = `À +10 : ${recipe.name} ${recipe.adjective}. Chaque pièce s'améliore indépendamment.`; card.append(adjective);
    if (recipe.cost) { const craft = document.createElement("button"); craft.dataset.action = recipe.equipped ? "upgrade" : "craft"; craft.textContent = recipe.equipped ? `Améliorer à +${recipe.equipped.level + 1}` : "Fabriquer et équiper"; craft.disabled = busy || adventure.quest !== "completed" || !recipe.affordable; craft.addEventListener("click", () => tutorialCommand(recipe.equipped ? "upgrade" : "craft", {recipe: recipe.recipe})); card.append(craft); }
    $("forge-catalogue").append(card);
  }
  }
  $("mob-name").textContent = fighting ? `${(adventure.mobs || []).length} ennemi(s) visible(s)` : "";
  $("mob-hp").textContent = fighting ? (adventure.mobs || [adventure.mob]).map(m => `${m.name} : ${m.stats.hp.current}/${m.stats.hp.max} PV`).join(" · ") : "";
  const enemies = fighting ? (adventure.mobs ?? (adventure.mob ? [{...adventure.mob, combat_id: "mob"}] : [])).map(m => ({id: m.combat_id, name: m.name, position: m.position, hp: m.stats.hp.current, max_hp: m.stats.hp.max, enemy: true})) : [];
  const mob = enemies[0] || null;
  const canAttack = target => Boolean(target.enemy && target.hp > 0 && me.hp > 0 && !me.stunned && !me.casting && me.cooldown_real_seconds <= 0 && me.can_attack && battleAllowed(adventure, me.id, target.id, me.attack_range));
  if (focusedMob && (enemies.some(target => target.id === focusedMob && target.hp <= 0) || focusedEnemy === focusedMob && !enemies.some(target => target.id === focusedEnemy && target.hp > 0))) {focusedMob = ""; focusedEnemy = ""; combatTarget = "";}
  const offensive = target => canAttack(target) || me.skills.some(skill => ["DAMAGE", "DEBUFF"].includes(skill.type) && skillAllowed(me, skill, target, mob));
  const distanceToMe = target => {const position = adventure.battle?.players[me.id]?.position; return position && target.position ? Math.hypot(position[0]-target.position[0], position[1]-target.position[1]) : Infinity;};
  const sortedEnemies = enemies.filter(target => target.hp > 0).sort((a,b) => Number(offensive(b))-Number(offensive(a)) || (offensive(a) ? a.hp-b.hp : distanceToMe(a)-distanceToMe(b)) || a.id.localeCompare(b.id));
  if (fighting && !focusedMob) {
    const supports = target => !controlledUnits(adventure, me.id).length && me.skills.some(skill => ["HEAL", "BUFF"].includes(skill.type) && skillAllowed(me, skill, target, mob));
    const current = [...enemies, ...adventure.players].find(target => target.id === combatTarget);
    const ready = !me.casting && !me.stunned && me.cooldown_real_seconds <= 0;
    if (!current || current.hp <= 0 || ready && (current.enemy ? !offensive(current) : !supports(current))) {
      const ally = adventure.players.filter(target => target.hp > 0 && supports(target)).sort((a, b) => a.hp / a.max_hp - b.hp / b.max_hp || a.id.localeCompare(b.id))[0];
      const enemy = sortedEnemies[0];
      combatTarget = ally?.id || enemy?.id || "";
    }
  }
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
  $("target-controls").hidden = true;
  const selected = [...enemies, ...adventure.players].find(target => target.id === combatTarget);
  $("combat-status").textContent = !fighting ? "" : !adventure.battle.hostiles_alive ? "La zone est calme. Vous pouvez explorer, dépecer les corps proches ou rejoindre une sortie." : me.casting ? `${me.casting.name} · incantation : ${me.casting.remaining_seconds.toFixed(1)} s · immobile${me.casting.concentration ? " · dégâts = interruption" : ""}` : me.hp <= 0 ? "Vous êtes à terre. Votre compagnon peut terminer le combat." : me.cooldown_real_seconds > 0 ? `Prochaine action dans ${me.cooldown_real_seconds.toFixed(1)} s.` : me.stunned ? "Vous êtes étourdi : aucune action n'est disponible." : selected ? `Cible ${focusedMob ? "choisie" : "automatique"} : ${selected.name}. Choisissez une attaque ou une compétence.` : "Aucune action disponible sur une cible.";
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
    const attackTarget = focusedMob ? selected : sortedEnemies.find(canAttack) || sortedEnemies[0];
    action("combat-actions", "Attaque simple", "strike", {target: attackTarget?.id}, !attackTarget || !canAttack(attackTarget));
    for (const skill of me.skills.filter(s => s.type === "INVOCATION")) {
      const element = action("self-skills", `Invoquer · ${skill.name} · ${skill.cost} ${skill.energy} · ${skill.cast_seconds} s`, "skill", {skill_name: skill.name, target: me.id}, !skillAllowed(me, skill, me, mob));
      element.title = me.casting ? "Incantation en cours." : me.invocations.length >= me.invocation_limit ? "Limite d’invocations atteinte." : "Invoquer sur soi, sans changer la cible sélectionnée.";
    }
    for (const skill of me.skills.filter(s => s.type !== "INVOCATION")) {
      const skillTarget = focusedMob ? selected : [...(skill.type === "RESURRECT" ? adventure.players.filter(target => target.hp <= 0) : ["HEAL", "BUFF"].includes(skill.type) ? adventure.players.filter(target => target.hp > 0).sort((a,b) => a.hp/a.max_hp-b.hp/b.max_hp) : sortedEnemies)].find(target => skillAllowed(me, skill, target, mob));
      const element = action("skills", `${skill.name} · ${skill.cost} ${skill.energy} · ${skill.cast_seconds} s${skill.concentration ? " · concentration" : ""}`, "skill", {skill_name: skill.name, target: skillTarget?.id}, !skillTarget || !skillAllowed(me, skill, skillTarget, mob));
      element.className = "secondary";
      element.title = skill.description;
    }
  }
  const regionOpen = Boolean(session?.tutorial) && document.body.classList.contains("hud-menu-open") && currentView === "map";
  $("region-view").hidden = !regionOpen;
  const detailsParent = regionOpen ? $("region-view") : $("map-view");
  if ($("map-details").parentElement !== detailsParent) detailsParent.append($("map-details"));
  if (document.body.classList.contains("hud-menu-open") && ["map", "equipment", "inventory", "bestiary", "achievements"].includes(currentView) && sectionChanged("hud-consultation", [session.id, currentView, adventure.world, me.gear, me.inventory, adventure.achievements, socialState?.team, mapPlace, mapPoint, mapMarker, $("bestiary-map").value, $("bestiary-search").value, $("bestiary-sort").value, busy])) {
    renderWorld(adventure, me, $("region-map"));
    renderAchievements(adventure.achievements);
    if (regionOpen) $("map-details").open = true;
  }
  const controlledHud = fighting && controlledUnits(adventure, me.id).length > 0;
  $("combat-view").classList.toggle("controlled-hud", controlledHud);
  $("skill-hud").hidden = !fighting || controlledHud;
  $("combat-actions").hidden = !controlledHud;
  $("skills").hidden = !controlledHud;
  if (fighting && !controlledHud) renderSkillHud(adventure, me, mob, canAttack, selected);
  if (!fighting) $("unit-controls").hidden = true;
  for (const [id, retained] of stableActions) for (const child of [...$(id).children]) if (!retained.has(child)) child.remove();
  $("combat-auto-target").setAttribute("aria-pressed", String(!focusedMob));
  touchControls?.sync();
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
    if (exit) svg.append(element("text", {x: x * 40 + 20, y: y * 40 + 24, class: "exit-label", "text-anchor": "middle"}, gate?.name || "Sortie"));
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
      else message(site.id === "mira" && !nearby ? "Approchez-vous de Mira : double-cliquez sur sa position pour marcher jusqu’à elle." : site.name);
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
