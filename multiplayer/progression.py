import math


RATIO = 3.0
ACTION_SECONDS = 1.2


def required(level):
    return int(500 * level ** 1.8)


def configure(character):
    character._required_exp_for_next_level = lambda: required(character.level)
    for skill in character.skills.values():
        base_cost = getattr(skill, "_poc_cost", skill.energie_cost)
        skill._poc_cost = base_cost
        capacity = next(energy.value for energy in character.energie if isinstance(energy, skill.energie_target))
        skill.energie_cost = 10 if skill.name == "Sword Slash" else min(capacity, max(5, math.ceil(base_cost * 1.5)))
    return character


def simple_damage(character):
    stat = character.intelligence if character.char_class in ("Mage", "Necromancien", "Priest") else character.force
    return max(2, int(2 + stat.current_value * .2))


def attack_range(character, skill=None):
    if skill and skill.skill_type.name not in ("DAMAGE", "DEBUFF"):
        return 6
    return 6 if character.char_class in ("Mage", "Archer", "Priest", "Necromancien") else 1.5


def scale_skill(character, skill):
    stat = character.force if skill.DamageType and skill.DamageType.name == "PHYSICAL" else character.sagesse if skill.DamageType and skill.DamageType.name == "SACRED" or skill.skill_type.name == "HEAL" else character.intelligence
    for name, effect in skill.effects.items():
        if effect.value and name.lower() in ("damage", "heal"):
            effect.value = max(1, int(effect.value * .55 + stat.current_value * .25))


def resources(party, now):
    from .tutorial import unpack, pack
    last = party.setdefault("resource_at", now)
    if now - last < RATIO:
        return False
    elapsed = (now - last) / RATIO
    for key, data in party["characters"].items():
        character = unpack(data)
        fractions = party.setdefault("regen_fraction", {}).setdefault(key, {})
        for energy in character.energie:
            rate = min(1.5, max(.2, energy.value * min(.1, energy.regen_rate) / 10))
            amount = elapsed * rate + fractions.get(type(energy).__name__, 0)
            gained = int(amount)
            energy.current_value = min(energy.value, energy.current_value + gained)
            fractions[type(energy).__name__] = 0 if energy.current_value == energy.value else amount - gained
        for name, skill in character.skills.items():
            skill.current_cooldown = max(0, (party.get("skill_ready", {}).get(key, {}).get(name, 0) - now) / RATIO)
        party["characters"][key] = pack(character)
    party["resource_at"] = now
    return True
