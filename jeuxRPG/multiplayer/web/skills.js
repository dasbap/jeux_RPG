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
