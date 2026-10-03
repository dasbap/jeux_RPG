from . import progression


def apply(mob, player, force, now):
    mob.setdefault("bleeding", []).append({"source": player, "damage": max(2, int(force * .05)), "next": now + 2 * progression.RATIO, "ticks": 3})


def status(mob, now):
    stacks = mob.get("bleeding", [])
    if not stacks:
        return []
    remaining = max(stack["next"] + (stack["ticks"] - 1) * 2 * progression.RATIO for stack in stacks)
    return [{"group": "debuff", "type": "DOT", "name": f"Saignement ×{len(stacks)}", "value": len(stacks), "duration": 1, "remaining_seconds": max(0, remaining - now) / progression.RATIO, "synthetic": True}]


def advance(party, now, random):
    from .tutorial import unpack, pack, sync_mobs
    from . import tactics
    messages = []
    defeated = []
    for mob in party["mobs"]:
        if not mob.get("bleeding"):
            continue
        enemy = unpack(mob)
        before = enemy.hp.current_value
        for stack in list(mob.get("bleeding", [])):
            if stack["next"] > now:
                continue
            source = party["characters"].get(stack["source"])
            if source and enemy.is_alive():
                enemy.drop_xp = lambda killer: ""
                enemy.lose_hp(unpack(source), stack["damage"])
            stack["ticks"] -= 1
            stack["next"] = now + 2 * progression.RATIO
        mob["bleeding"] = [stack for stack in mob.get("bleeding", []) if stack["ticks"] > 0]
        mob.update(pack(enemy))
        if enemy.hp.current_value < before:
            mob["calling_until"] = None
            if enemy.is_alive():
                party["battle"]["enemy_alerted"] = True
            messages.append(f"{mob['name']} subit {before - enemy.hp.current_value} dégâts de saignement.")
        if not enemy.is_alive():
            defeated.append(mob)
    for mob in defeated:
        party["mobs"].remove(mob)
        tactics.defeated(party, mob, now, random, messages)
    sync_mobs(party)
    return messages
