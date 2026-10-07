"use strict";
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
function skillCategory(skill) {
  if (["DAMAGE"].includes(skill.type)) return "offense";
  if (["DEBUFF"].includes(skill.type)) return "debuff";
  if (["BUFF", "HEAL", "RESURRECT", "INVOCATION"].includes(skill.type)) return "buff";
  return "offense";
}
function skillGlyph(skill, category) {
  if (skill.type === "HEAL") return "✚";
  if (skill.type === "RESURRECT") return "✦";
  if (skill.type === "INVOCATION") return "♟";
  if (category === "debuff") return "⌁";
  if (category === "buff") return "▲";
  return "◆";
}
function favoriteSkillKey(me, category) {
  return `rpg-skill-favorite:${me.class_name || "class"}:${category}`;
}
function favoriteSkill(me, category, skills) {
  const saved = localStorage.getItem(favoriteSkillKey(me, category));
  return skills.find(skill => skill.name === saved) || skills[0] || null;
}
function saveFavoriteSkill(me, category, skill) {
  localStorage.setItem(favoriteSkillKey(me, category), skill.name);
}
function skillTargets(adventure, me, skill, mob) {
  const enemies = (adventure.mobs ?? (adventure.mob ? [{...adventure.mob, combat_id: "mob"}] : [])).map(m => ({id:m.combat_id,name:m.name,position:m.position,hp:m.stats.hp.current,max_hp:m.stats.hp.max,enemy:true}));
  const allies = adventure.players.map(player => ({...player, enemy:false}));
  const allowed = [...enemies, ...allies].filter(target => skill.targets?.includes(target.id) && skillAllowed(me, skill, target, mob));
  const current = allowed.find(target => target.id === combatTarget);
  if (current) return [current, allowed];
  const ranked = allowed.slice().sort((a,b) => {
    if (skill.type === "HEAL") return a.hp / a.max_hp - b.hp / b.max_hp;
    if (skill.type === "RESURRECT") return a.hp - b.hp;
    if (["BUFF","INVOCATION"].includes(skill.type)) return (a.id === me.id ? -1 : 0) - (b.id === me.id ? -1 : 0) || a.hp / a.max_hp - b.hp / b.max_hp;
    return a.hp - b.hp;
  });
  return [ranked[0] || null, allowed];
}
function skillDetails(skill) {
  const effects = [skill.description, skill.type ? `Type : ${skill.type}` : "", skill.cost !== undefined ? `Coût : ${skill.cost} ${skill.energy || ""}` : "", skill.range !== undefined ? `Portée : ${skill.range}` : "", skill.cast_seconds !== undefined ? `Incantation : ${skill.cast_seconds} s` : "", skill.cooldown !== undefined ? `Recharge : ${skill.cooldown} s` : "", skill.concentration ? "Concentration : interrompue par les dégâts" : ""].filter(Boolean);
  return effects.join(" · ");
}
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
