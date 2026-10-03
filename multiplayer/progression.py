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


def health_resources(party, now):
    units = list(party["characters"].items())
    for character in party["characters"].values():
        units.extend((invocation["id"], invocation) for invocation in character.get("invocations", []))
    encounter = party.get("battle", {}).get("started_at", 0) if party.get("battle") else 0
    units.extend((f"mob:{encounter}:{mob['combat_id']}", mob) for mob in party.get("mobs", []))
    timers = party.setdefault("hp_regen", {})
    active = set()
    changed = False
    for key, data in units:
        active.add(key)
        timer = timers.setdefault(key, {"at": now, "fraction": 0})
        hp = data["stats"]["hp"]
        minutes = max(0, int((now - timer["at"]) / 60))
        if hp["current"] <= 0 or hp["current"] >= hp["max"]:
            timer.update(at=now, fraction=0)
            continue
        if not minutes:
            continue
        amount = hp["max"] * .01 * minutes + timer["fraction"]
        gained = int(round(amount, 10))
        hp["current"] = min(hp["max"], hp["current"] + gained)
        timer.update(at=timer["at"] + minutes * 60, fraction=0 if hp["current"] == hp["max"] else amount - gained)
        changed = changed or gained > 0
    party["hp_regen"] = {key: value for key, value in timers.items() if key in active}
    if party.get("mobs"):
        party["mob"] = party["mobs"][0]
    return changed


def resources(party, now):
    from .tutorial import unpack, pack
    health_changed = health_resources(party, now)
    last = party.setdefault("resource_at", now)
    if now - last < RATIO:
        return health_changed
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


def casting(skill):
    physical = skill.DamageType and skill.DamageType.name == "PHYSICAL"
    duration = .4 if physical else 2.0 if skill.skill_type.name == "INVOCATION" else 1.5
    return {"seconds": duration, "concentration": not bool(physical)}
