import math
from .content import WORLD


RATIO = 3.0
ACTION_SECONDS = 1.2


def required(level):
    return int(WORLD['xp_base'] * level ** WORLD['xp_exponent'])


def configure(character):
    character._required_exp_for_next_level = lambda: required(character.level)
    for skill in character.skills.values():
        base_cost = getattr(skill, "_poc_cost", skill.energie_cost)
        skill._poc_cost = base_cost
        capacity = next(energy.value for energy in character.energie if isinstance(energy, skill.energie_target))
        balance = getattr(skill,"balance",{})
        skill.energie_cost = skill.catalog_cost if hasattr(skill,"catalog_cost") else balance.get("cost_fixed") if balance.get("cost_fixed") is not None else min(capacity,max(balance.get("cost_min",5),math.ceil(base_cost*balance.get("cost_factor",1.5))))
    return character


def simple_damage(character):
    profile = character.combat_profile
    stat = getattr(character,profile.get('attack_stat','force'))
    return max(profile.get('attack_min',2),int(profile.get('attack_base',2)+stat.current_value*profile.get('attack_factor',.2)))


def attack_range(character,skill=None):
    if skill and hasattr(skill,'catalog_range'):
        return skill.catalog_range
    if skill and skill.skill_type.name not in ('DAMAGE','DEBUFF'):
        return 6
    return character.combat_profile.get('attack_range',1.5)


def scale_skill(character, skill):
    stat = character.force if skill.DamageType and skill.DamageType.name == "PHYSICAL" else character.sagesse if skill.DamageType and skill.DamageType.name == "SACRED" or skill.skill_type.name == "HEAL" else character.intelligence
    for name, effect in skill.effects.items():
        if effect.value and name.lower() in ("damage", "heal"):
            if hasattr(skill,'catalog_growth'):
                effect.value += round(skill.catalog_growth*(character.level-1))
            balance = getattr(skill,'balance',{})
            effect.value = max(1,int(effect.value*balance.get('effect_factor',.55)+stat.current_value*balance.get('stat_factor',.25)))


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
            if minutes or timer["fraction"]:
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
    if hasattr(skill,'catalog_cast'):
        return skill.catalog_cast.copy()
    physical = skill.DamageType and skill.DamageType.name == "PHYSICAL"
    duration = .4 if physical else 2.0 if skill.skill_type.name == "INVOCATION" else 1.5
    return {"seconds": duration, "concentration": not bool(physical)}
