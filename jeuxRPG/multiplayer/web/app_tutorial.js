"use strict";
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
  const fieldInteractions = adventure.field_interactions || [];
  const fieldSites = new Set(fieldInteractions.map(site => site.id));
  const worldPoints = adventure.world?.places?.flatMap(place => place.points || []) || [];
  const currentPoint = worldPoints.find(point => point.id === adventure.position);
  const nearbyNpc = fieldInteractions.map(site => ({...worldPoints.find(point => point.id === site.id), ...site})).find(site => site.dialogue || site.type === "pnj") || (!fighting && currentPoint?.type === "pnj" ? currentPoint : null);
  const canTalk = Boolean(nearbyNpc) && !adventure.moving;
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
  const talkingToMira = nearbyNpc?.id === "mira";
  $("npc-title").textContent = nearbyNpc ? `Parler à ${nearbyNpc.name}` : "Dialogue";
  $("npc-dialogue").textContent = nearbyNpc && !talkingToMira ? `${nearbyNpc.name} : ${nearbyNpc.dialogue || nearbyNpc.description || "Bonjour, voyageur."}` : adventure.step === "village" ? `Mira : ${adventure.hunt_description || "Des gobelins menacent la lisière."} · ${adventure.hunt_goal || 3} gobelin(s).` : adventure.quest === "completed" ? "Mira : merci pour votre aide ! La forge est désormais accessible." : adventure.kills < (adventure.hunt_goal || 3) ? `Mira : il reste ${(adventure.hunt_goal || 3) - adventure.kills} gobelin(s) à battre dans la lisière.` : `Mira : vous avez vaincu les ${adventure.hunt_goal || 3} gobelins ! Votre récompense vous attend. Ensuite, faites fabriquer votre veste à la forge.`;
  if (canTalk && nearbyNpc && !talkingToMira) action("npc-actions", "Parler", "talk", {npc: nearbyNpc.id});
  else if (canTalk && talkingToMira && (adventure.step === "village" || adventure.step === "hunt" && adventure.kills >= (adventure.hunt_goal || 3))) action("npc-actions", adventure.step === "village" ? "Accepter la quête" : "Rendre la quête", "talk", {npc: "mira"});
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
