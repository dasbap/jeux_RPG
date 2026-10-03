import json
from copy import deepcopy
from functools import lru_cache

from jeuxRPG._class.character import Character
from jeuxRPG._class.res.classType import SkillType
from jeuxRPG._class.res.character.stats import basic_stat
from jeuxRPG._class.res.character.alteration import alteration
from jeuxRPG._class.sub_character.invocations.invocation import Invocation
from . import world, encounters, progression, forge, tactics, achievements, bleeding, fields

TRAVEL_ENCOUNTER_CHANCE = .25


STEPS = {
    "clearing": ("Clairière des Éveillés", "Explorez la clairière pour rencontrer votre premier gobelin."),
    "first_fight": ("Clairière des Éveillés", "Utilisez vos compétences ou votre attaque pour battre le gobelin."),
    "road": ("Sentier de Rosée", "Votre premier combat est gagné. Rejoignez le village de Rosée."),
    "village": ("Village de Rosée", "Parlez à Mira pour accepter sa quête de chasse."),
    "hunt": ("Lisière de Rosée", "Battez trois gobelins puis rapportez la nouvelle à Mira."),
    "craft": ("Forge de Rosée", "Fabriquez et équipez une veste avec les matériaux des gobelins."),
    "travel": ("Route des Deux Villages", "Votre équipement est prêt. Rejoignez le village de Brume."),
    "complete": ("Village de Brume", "Tutoriel terminé : combat, compétences, quête, butin et équipement maîtrisés."),
}


def create_character(player):
    return progression.configure(Character.create(player["class_name"], player["id"], player["name"]))


def pack(character):
    effects = []
    groups = character.status["alteration"]
    for group in ("buff", "debuff", "stun", "invulnerability"):
        for effect in groups[group]:
            if effect.duration > 0:
                effects.append({"group": group, "type": effect.type.name, "name": effect.name,
                                "value": effect.value, "duration": effect.duration,
                                "stat": effect.stat_target.__name__ if effect.stat_target else None})
    return {
        "class_name": character.char_class, "id": character.user_id, "name": character.name,
        "level": character.level, "exp": character.exp,
        "stats": {key: {"max": getattr(character, key).value, "current": getattr(character, key).current_value}
                  for key in ("hp", "force", "endurance", "intelligence", "sagesse")},
        "energies": [{"type": type(e).__name__, "max": e.value, "current": e.current_value,
                      "regen": e.regen_rate} for e in character.energie],
        "cooldowns": {key: value.current_cooldown for key, value in character.skills.items()},
        "effects": effects,
        "invocations": [pack(i) for i in character.invocations.get_all() if i.is_alive()],
    }


@lru_cache(maxsize=128)
def blueprint(class_name, level):
    character = progression.configure(Character.create(class_name, "blueprint", "Modèle"))
    if level > 1:
        character.gain_exp(sum(progression.required(value) for value in range(1, level)))
    return character


def unpack(data, master=None):
    if master is None:
        model = blueprint(data["class_name"], data["level"])
        character = deepcopy(model, {id(model.class_table): model.class_table})
        character.user_id = data["id"]
        character.name = data["name"]
    else:
        character = Character.create(data["class_name"], master=master, name=data["name"])
        Invocation.all_invocation.remove(character)
        character.drop_xp = lambda killer: ""
    character.user_id = data["id"]
    character.level = data["level"]
    character.exp = data["exp"]
    for key, value in data["stats"].items():
        stat = getattr(character, key)
        stat.value = value["max"]
        stat.current_value = value["current"]
    character.energie = []
    for value in data["energies"]:
        energy = getattr(basic_stat, value["type"])(value["max"], value["regen"])
        energy.current_value = value["current"]
        character.add_energie(energy)
    character._init_status_stats()
    for name, cooldown in data["cooldowns"].items():
        if name in character.skills:
            character.skills[name].current_cooldown = cooldown
    for value in data["effects"]:
        if value.get("synthetic"):
            continue
        stat = getattr(basic_stat, value["stat"]) if value["stat"] else None
        effect = alteration.Alteration(value["name"], character, value["value"], value["duration"],
                                       character, stat, alteration.AlterationType[value["type"]])
        character.status["alteration"][value["group"]].append(effect)
        if value["group"] in ("buff", "debuff"):
            getattr(character.get_stat(stat.__name__), "buffs" if value["group"] == "buff" else "debuffs").append(effect)
    for value in data["invocations"]:
        character.invocations.add_invocation(unpack(value, character))
    return progression.configure(character)


def recover(character):
    character.hp.current_value = character.hp.value
    for energy in character.energie:
        energy.current_value = energy.value
    for skill in character.skills.values():
        skill.reset_cooldown()


def new_party(players):
    return {"step": "clearing", "kills": 0, "quest": "unaccepted", "mob": None,
            "characters": {p["id"]: pack(create_character(p)) for p in players},
            "inventory": {p["id"]: {} for p in players}, "equipment": {},
            "ready": {p["id"]: 0 for p in players}, "visited": ["clearing"], "seen_mobs": [], "position": "clearing", "journey": [], "mobs": [], "combat_step": "clearing", "transit": None}


def npc(now):
    stay = 8 * 3600
    crossing = next(r["distance_km"] for r in world.ROUTES if r["id"] == "rosee_brume") / 6 * 3600
    phase = now % (2 * (stay + crossing))
    location = "Rosée" if phase < stay else "Brume" if stay + crossing <= phase < 2 * stay + crossing else None
    return {"name": "Léon, marchand itinérant", "location": location, "travelling": location is None}


def can_target(actor, skill, target, mob):
    if target is None or not actor.is_alive() or actor.is_stunned() or not skill.is_ready() or not skill.can_afford(actor):
        return False
    if skill.skill_type in (SkillType.DAMAGE, SkillType.DEBUFF):
        return target is mob and target.is_alive()
    if skill.skill_type == SkillType.INVOCATION:
        return target is actor and actor.invocations.can_summon()
    if target is mob or target is not actor and not skill.can_target_others:
        return False
    if skill.skill_type == SkillType.RESURRECT:
        return not target.is_alive()
    if not target.is_alive():
        return False
    if skill.skill_type == SkillType.HEAL:
        return target.hp.current_value < target.hp.value
    return skill.skill_type == SkillType.BUFF


def status_view(party, key, effects, now):
    interval = progression.ACTION_SECONDS * progression.RATIO
    next_tick = party.get("effect_at", {}).get(key, now + interval)
    return [{**deepcopy(effect), "remaining_seconds": max(0, (next_tick - now + max(0, effect["duration"] - 1) * interval) / progression.RATIO)} for effect in effects]


def view(party, me, now):
    party = json.loads(json.dumps(party, ensure_ascii=False, separators=(",", ":")))
    migrate(party, now)
    progression.resources(party, now)
    if party.get("battle"):
        tactics.sync_summons(party, now)
    result = json.loads(json.dumps({key: value for key, value in party.items() if key not in ("characters", "ready", "battle", "mobs", "mob")}, ensure_ascii=False, separators=(",", ":")))
    result["achievements"] = achievements.view(party)
    result["location"], result["objective"] = STEPS[party["step"]]
    result["location"] = world.point_name(party.get("position", world.CURRENT[party["step"]]))
    transit = party.get("transit")
    result["moving"] = bool(transit and not party["battle"])
    result["travel_remaining_real_seconds"] = max(0, transit["remaining"] - (min(now, transit.get("paused_at", transit["ready_at"])) - transit["started_at"])) / progression.RATIO if transit else 0
    result["traveller"] = npc(now)
    result["world"] = world.view(party, me, result["traveller"])
    result.pop("fields", None)
    fields.reveal(party)
    result["field_interactions"] = fields.interactions(party, me)
    result["battle"] = tactics.view(party, now, me)
    result["mobs"] = [deepcopy(m) for m in party["mobs"] if tactics.visible(party, me, m)]
    for enemy in result["mobs"]:
        enemy["effects"] = status_view(party, enemy["combat_id"], enemy["effects"], now) + bleeding.status(enemy, now)
        enemy["stunned"] = enemy.get("stunned_until", 0) > now
    result["mob"] = result["mobs"][0] if result["mobs"] else None
    result["players"] = []
    characters = {key: unpack(value) for key, value in party["characters"].items()}
    enemies = {m["combat_id"]: unpack(m) for m in result["mobs"]}
    if not enemies and result["mob"]:
        enemies = {"mob": unpack(result["mob"])}
    mob = next(iter(enemies.values()), None)
    targets = {**characters, **enemies}
    for player_id, data in party["characters"].items():
        character = characters[player_id]
        for name, skill in character.skills.items():
            skill.current_cooldown = max(0, (party["skill_ready"].get(player_id, {}).get(name, 0) - now) / progression.RATIO)
        actionable = bool(party["mobs"] and character.is_alive() and not character.is_stunned() and party["ready"][player_id] <= now and not party["battle"]["players"][player_id].get("casting"))
        result["players"].append({"id": player_id, "name": character.name, "class_name": character.char_class,
                                  "level": character.level, "exp": character.exp, "next_level_exp": progression.required(character.level),
                                  "hp": character.hp.current_value, "max_hp": character.hp.value,
                                  "stats": {key: getattr(character, key).current_value for key in ("force", "endurance", "intelligence", "sagesse")},
                                  "effects": status_view(party, player_id, data["effects"], now), "stunned": character.is_stunned(), "invocation_limit": character.invocations.get_limit(),
                                  "can_attack": actionable and not party["battle"]["players"][player_id].get("casting") if party["battle"] else False,
                                  "casting": tactics.cast_view(party, player_id, now),
                                  "energies": data["energies"], "inventory": party["inventory"][player_id],
                                  "equipment": " · ".join(f"{v['name']} +{v['level']}" for v in party["equipment"].get(player_id, {}).values()) or None,
                                  "gear": list(party["equipment"].get(player_id, {}).values()),
                                  "forge": forge.catalogue(party, player_id),
                                  "attack_range": progression.attack_range(character),
                                  "cooldown_real_seconds": max(0, party["ready"][player_id] - now) / progression.RATIO,
                                  "skills": [{"name": s.name, "description": s.description, "type": s.skill_type.name,
                                              "range": progression.attack_range(character, s),
                                              "cast_seconds": progression.casting(s)["seconds"], "concentration": progression.casting(s)["concentration"],
                                              "cost": s.energie_cost, "energy": s.energie_target.__name__,
                                              "cooldown": max(0, party["skill_ready"].get(player_id, {}).get(s.name, 0) - now) / progression.RATIO,
                                              "can_target_others": s.can_target_others,
                                              "targets": [key for key, target in targets.items() if actionable and can_target(character, s, target, target if key in enemies else mob) and tactics.allowed(party, player_id, key, progression.attack_range(character, s))],
                                              "available": party["skill_ready"].get(player_id, {}).get(s.name, 0) <= now and s.can_afford(character)}
                                             for s in character.skills.values()],
                                  "upcoming_skills": [{"level": int(level.split()[1]), "name": s.name}
                                                      for level, skills in character.class_skills_dict.items()
                                                      if level.startswith("level ") and int(level.split()[1]) > character.level
                                                      for s in skills.values()],
                                  "invocations": [{"id": i.user_id, "name": i.name, "hp": i.hp.current_value, "max_hp": i.hp.value,
                                                   "stats": {key: getattr(i, key).current_value for key in ("force", "endurance", "intelligence", "sagesse")},
                                                   "effects": status_view(party, i.user_id, pack(i)["effects"], now), "energies": pack(i)["energies"], "control_cost": deepcopy(tactics.CONTROL_RULES.get(i.char_class, {"energy": None, "per_second": 0}))}
                                                  for i in character.invocations.get_all()]})
    if result["battle"]:
        for key, unit in result["battle"]["summons"].items():
            unit["effects"] = status_view(party, key, unit.get("effects", []), now)
    result["me"] = me
    return result


def execute_one(party, player_id, action, params, now, error, random, resolved=False):
    characters = {key: unpack(value) for key, value in party["characters"].items()}
    actor = characters[player_id]
    messages = []
    if action in ("strike", "skill"):
        if not resolved:
            tactics.ready(party, player_id, now, error)
        enemies = {m["combat_id"]: unpack(m) for m in party["mobs"]}
        for target in [*characters.values(), *enemies.values()]:
            target.drop_xp = lambda killer: ""
        target_id = params["target"]
        if not isinstance(target_id, str):
            raise error("invalid_target", "Cible invalide.")
        target = enemies.get(target_id) or characters.get(target_id)
        mob = target if target_id in enemies else next(iter(enemies.values()), None)
        if target is None:
            raise error("invalid_target", "Cible absente de ce combat.")
        if action == "strike":
            if target_id not in enemies:
                raise error("invalid_target", "L'attaque simple doit viser un ennemi.")
            if not tactics.allowed(party, player_id, target_id, progression.attack_range(actor)):
                raise error("out_of_range", "La cible est hors de portée ou masquée par une couverture.", 409)
            before_hp = target.hp.current_value
            target.lose_hp(actor, progression.simple_damage(actor))
            messages.append(f"{actor.name} termine son attaque simple contre {target.name} : {max(0, before_hp - target.hp.current_value)} dégâts.")
        else:
            skill = actor.skills.get(params["skill_name"]) if isinstance(params["skill_name"], str) else None
            if skill is None:
                raise error("unknown_skill", "Compétence non acquise.")
            skill.current_cooldown = 0 if resolved else max(0, (party["skill_ready"].get(player_id, {}).get(skill.name, 0) - now) / progression.RATIO)
            if resolved:
                actor.get_energie(skill.energie_target).current_value += skill.energie_cost
            if not skill.is_ready() or not skill.can_afford(actor):
                raise error("skill_unavailable", "Énergie ou délai insuffisant.", 409)
            if not can_target(actor, skill, target, mob):
                raise error("invalid_target", "Aucune action utile sur cette cible.")
            if not tactics.allowed(party, player_id, target_id, progression.attack_range(actor, skill)):
                raise error("out_of_range", "La cible est hors de portée ou masquée.", 409)
            if not resolved:
                timing = progression.casting(skill)
                unit = party["battle"]["players"][player_id]
                unit["route"] = []
                unit["hidden"] = False
                unit["casting"] = {"skill_name": skill.name, "target": target_id, "started_at": now,
                                   "ends_at": now + timing["seconds"] * progression.RATIO,
                                   "concentration": timing["concentration"]}
                actor.consume_energie(skill.energie_cost, skill.energie_target)
                party["characters"][player_id] = pack(actor)
                party["skill_ready"].setdefault(player_id, {})[skill.name] = unit["casting"]["ends_at"] + skill.cooldown * progression.RATIO
                party["ready"][player_id] = now + progression.ACTION_SECONDS * progression.RATIO
                return [f"{actor.name} commence {skill.name} ({timing['seconds']:g} s)."], False
            progression.scale_skill(actor, skill)
            before_hp = target.hp.current_value
            try:
                success, _ = actor.use_skill(skill.name, target)
            finally:
                for invocation in list(Invocation.all_invocation):
                    if invocation.master is actor:
                        Invocation.all_invocation.remove(invocation)
            if not success:
                raise error("skill_unavailable", "La compétence ne peut pas être utilisée.", 409)
            party["skill_ready"].setdefault(player_id, {})[skill.name] = now + skill.cooldown * progression.RATIO
            messages.append(f"{actor.name} utilise {skill.name} : sort terminé sur {target.name}{' · ' + str(max(0, before_hp - target.hp.current_value)) + ' dégâts' if target_id in enemies else ''}.")
            party["effect_at"][target_id] = now + progression.ACTION_SECONDS * progression.RATIO
        party["characters"] = {key: pack(c) for key, c in characters.items()}
        tactics.sync_summons(party, now)
        survivors = []
        defeated = []
        for data in party["mobs"]:
            enemy = enemies[data["combat_id"]]
            data.update(pack(enemy))
            if data["combat_id"] == target_id:
                if action == "skill" and resolved and actor.char_class == "Knight" and skill.name == "Sword Slash" and enemy.is_alive():
                    bleeding.apply(data, player_id, actor.force.current_value, now)
                    messages.append(f"{enemy.name} saigne : {len(data['bleeding'])} cumul(s).")
                tactics.damaged(party, data, player_id, now)
            if enemy.is_alive():
                survivors.append(data)
            else:
                defeated.append(data)
        party["mobs"] = survivors
        sync_mobs(party)
        for data in defeated:
            tactics.defeated(party, data, now, random, messages)
        if not resolved:
            party["ready"][player_id] = now + progression.ACTION_SECONDS * progression.RATIO
        return messages, False
    if action == "talk":
        if party["battle"] or params["npc"] != "mira":
            raise error("invalid_npc", "PNJ inaccessible pendant le combat.", 409)
        if party["step"] == "village":
            party.update(step="hunt", quest="active")
            if party.get("field_mode"):
                party["kills"] = min(3, party.get("zone_kills", {}).get("lisiere", 0))
            messages.append("Mira : battez trois gobelins, puis dépecez les corps pour récupérer les matériaux de la forge.")
        elif party["step"] == "hunt" and party["kills"] >= 3:
            party.update(step="craft", quest="completed")
            for key, character in characters.items():
                character.gain_exp(300)
                party["characters"][key] = pack(character)
            messages.append("Mira : merci ! Chaque aventurier reçoit 300 XP. La forge est désormais ouverte.")
        else:
            raise error("quest_incomplete", "Mira attend trois gobelins vaincus.", 409)
        return messages, False
    if action == "rest" and not party["battle"]:
        actor.hp.current_value = actor.hp.value
        party["characters"][player_id] = pack(actor)
        return [f"{actor.name} se repose. Son énergie se régénère avec le temps."], False
    raise error("invalid_command", "Action inconnue.")


def migrate(party, now):
    if "position" not in party:
        world.record(party)
    party.setdefault("combat_step", party["step"])
    party.setdefault("position", world.CURRENT[party["step"]])
    party.setdefault("journey", [])
    party.setdefault("transit", None)
    party.setdefault("battle", None)
    party.setdefault("resource_at", now)
    party.setdefault("skill_ready", {})
    party.setdefault("effect_at", {})
    forge.migrate(party)
    if "mobs" not in party or party["mob"] and not party["mobs"]:
        party["mobs"] = [{**party["mob"], "combat_id": "mob", "next_attack": now + 40}] if party["mob"] else []
    if party.get("rules_version", 0) < 8:
        party["ready"] = {key: min(value, now + 3.6) for key, value in party["ready"].items()}
        party["rules_version"] = 8
        if party["mobs"] and not party["battle"]:
            tactics.begin(party, now, "explore")

    if "hp_regen" not in party:
        progression.health_resources(party, now)


def sync_mobs(party):
    party["mob"] = party["mobs"][0] if party["mobs"] else None


def spawn(party, now, random, messages, origin="travel"):
    zone = world.zone_of(party["position"])
    level = min(c["level"] for c in party["characters"].values())
    count = encounters.group_size("D", level, (4 if party["position"] == "rosee_brume" else world.LEVELS[zone]), random)
    if not count:
        messages.append("Vous ne croisez aucun gobelin.")
        return
    party["encounter_number"] = party.get("encounter_number", 0) + 1
    party["combat_size"] = count
    party["seen_spawnpoints"] = sorted(set(party.get("seen_spawnpoints", [])) | {party["position"]})
    first = party["step"] == "clearing"
    party["training"] = party["position"] == "training"
    party["combat_step"] = "first_fight" if first else party["step"]
    if first:
        party["step"] = "first_fight"
    party["mobs"] = []
    for index in range(count):
        mob = Character.create("Goblin", "tutorial-mob", f"Gobelin des bois {index + 1}")
        mob.hp.value = world.GOBLIN["hp_first"] if first else world.GOBLIN["hp_hunt"]
        mob.hp.current_value = mob.hp.value
        party["mobs"].append({**pack(mob), "combat_id": "mob" if index == 0 else f"mob-{index + 1}",
                              "rank": "D", "next_attack": now + random() * 6})
    tactics.begin(party, now, origin)
    sync_mobs(party)
    progression.health_resources(party, now)
    messages.append(f"Vous rencontrez {count} gobelin(s) de rang D.")


def arrive(party, destination, messages):
    party["position"] = destination
    zone = world.zone_of(destination)
    party["visited"] = sorted(set(party["visited"]) | {zone})
    messages.append(f"Vous arrivez à {world.point_name(destination)}.")
    if destination == "rosee" and party["step"] == "road":
        party["step"] = "village"
    if destination in ("brume", "arrival") and party["step"] == "travel":
        party["step"] = "complete"
        party["journey"] = []
    world.record(party)
    if party.get("field_mode") and destination in fields.MAPS and destination in ("rosee", "brume", "lisiere", "clearing", "hunt", "forest", "cave_1", "cave_2", "cave_3"):
        party["journey"] = []
        messages.extend(fields.enter(party, destination, [1, 16] if destination == "brume" else [1, 20] if destination == "rosee" else [1, 10], party.get("field_now", 0)))


def continue_journey(party, now, random, messages):
    if party["battle"] or party["mobs"]:
        return
    party["field_now"] = now
    transit = party["transit"]
    if transit:
        if transit.get("paused_at") is not None:
            delay = now - transit.pop("paused_at")
            transit["started_at"] += delay
            transit["ready_at"] += delay
        if transit["remaining"] <= 0:
            arrive(party, transit["destination"], messages)
            party["transit"] = None
        elif now < transit["ready_at"]:
            return
        else:
            transit["remaining"] = max(0, transit["remaining"] - transit["segment"])
            if transit["hazard"] and random() < TRAVEL_ENCOUNTER_CHANCE:
                spawn(party, now, random, messages)
                if party["mobs"]:
                    transit["paused_at"] = now
            if transit["remaining"] <= 0 and not party["mobs"]:
                arrive(party, transit["destination"], messages)
                party["transit"] = None
            elif transit["remaining"] > 0:
                transit["segment"] = min(150, transit["remaining"])
                transit["started_at"] = now
                transit["ready_at"] = now + transit["segment"]
            if party["mobs"] or party["transit"]:
                return
    if party["journey"] and not party["mobs"] and not party.get("battle"):
        destination = party["journey"].pop(0)
        source = party["position"]
        duration = world.walking_seconds(source, destination)
        first_segment = min(150, duration * (.15 + .7 * random()))
        dangerous = source in world.ROAD_POINTS or destination in world.ROAD_POINTS or world.hazard(destination)
        if destination in world.ROAD_POINTS:
            party["position"] = destination
        party["transit"] = {"source": source, "total": duration, "destination": destination, "remaining": duration,
                            "started_at": now, "ready_at": now + first_segment,
                            "segment": first_segment, "hazard": dangerous}
        messages.append(f"Vous partez vers {world.point_name(destination)}.")


def proposed_path(start, destination, known, paths, error):
    if paths is None:
        return world.path(start, destination, known)
    proposed = paths.get(start)
    if proposed is None:
        return None
    if not world.validate_path(start, destination, known, proposed):
        raise error("invalid_path", "L’itinéraire proposé ne respecte pas les chemins connus.", 409)
    return proposed[:]


def redirect_journey(party, destination, known, now, random, messages, error, paths=None):
    transit = party["transit"]
    if not transit:
        route = proposed_path(party["position"], destination, known, paths, error)
        if route is None:
            raise error("invalid_destination", "Ce point n'est pas accessible par les chemins connus.", 409)
        party["journey"] = route
        continue_journey(party, now, random, messages)
        return
    source = transit.get("source")
    if source is None:
        road = transit["destination"] if transit["destination"] in world.ROAD_POINTS else party["position"]
        definition = next((r for r in world.ROUTES if r["id"] == road), None)
        source = (road if transit["destination"] != road else (definition["from"] if next(iter(party.get("journey", [])), None) == definition["to"] else definition["to"])) if definition else party["position"]
    total = transit.get("total", world.walking_seconds(source, transit["destination"]))
    elapsed = max(0, min(transit["remaining"], now - transit["started_at"]))
    remaining = max(0, transit["remaining"] - elapsed)
    travelled = total - remaining
    candidates = []
    for endpoint, duration in ((source, travelled), (transit["destination"], remaining)):
        route = proposed_path(endpoint, destination, known, paths, error)
        if route is not None:
            cost = duration
            previous = endpoint
            for point in route:
                cost += world.walking_seconds(previous, point)
                previous = point
            candidates.append((cost, endpoint, duration, route))
    if not candidates:
        raise error("invalid_destination", "Ce point n'est pas accessible par les chemins connus.", 409)
    _, endpoint, duration, route = min(candidates, key=lambda item: item[0])
    reverse = endpoint == source
    segment = min(duration, max(0, transit["ready_at"] - now))
    party["journey"] = route
    party["transit"] = {"source": transit["destination"] if reverse else source, "destination": endpoint,
                        "total": total, "remaining": duration, "started_at": now,
                        "ready_at": now + segment, "segment": segment, "hazard": transit["hazard"]}
    messages.append(f"Vous {'faites demi-tour' if reverse else 'changez d’itinéraire'} vers {world.point_name(destination)}.")
    continue_journey(party, now, random, messages)


def execute(party, player_id, action, params, now, error, random):
    migrate(party, now)
    progression.resources(party, now)
    messages = []
    if action == "enter_zone":
        if party.get("battle") or party.get("transit"):
            raise error("moving", "Rejoignez un lieu hors combat avant d’explorer à pied.", 409)
        identifier = party["position"] if party["position"] in fields.MAPS else world.zone_of(party["position"])
        if identifier not in fields.MAPS:
            raise error("wrong_location", "Ce chemin rapide n’est pas une entrée de zone.", 409)
        party["field_mode"] = True
        party.setdefault("fields", {})
        return fields.enter(party, identifier, [1, 20] if identifier == "rosee" else [1, 16] if identifier == "brume" else [1, 10], now), False
    if party.get("field_map") and action in ("talk", "craft", "upgrade"):
        return fields.execute(party, player_id, action, params, now, error, random)
    if action in ("travel", "move"):
        if party["battle"] or party["mobs"] or party["mob"]:
            raise error("in_combat", "Terminez le combat avant de vous déplacer.", 409)
        destination = params["destination"]
        known = {p["id"] for p in world.view(party, player_id)["places"]}
        paths = params.get("paths")
        sources = {party["position"]}
        if party["transit"]:
            sources.update((party["transit"]["source"], party["transit"]["destination"]))
        if "paths" in params and (not isinstance(paths, dict) or not paths or set(paths) - sources):
            raise error("invalid_path", "Origine d’itinéraire invalide.", 409)
        if party["transit"] or party["journey"]:
            redirect_journey(party, destination, known, now, random, messages, error, paths)
            return messages, party["step"] == "complete"
        path = proposed_path(party["position"], destination, known, paths, error)
        if path is None:
            raise error("invalid_destination", "Ce point n'est pas accessible par les chemins connus.", 409)
        party["journey"] = path
        continue_journey(party, now, random, messages)
        return messages, party["step"] == "complete"
    if action in ("control_units", "unit_order", "unit_skill"):
        return tactics.control(party, player_id, action, params, now, error), False
    if action in ("battle_move", "hide", "harvest", "leave_battle"):
        messages = tactics.execute(party, player_id, action, params, now, error)
        if action == "leave_battle":
            continue_journey(party, now, random, messages)
        return messages, party["step"] == "complete"
    if action in ("craft", "upgrade"):
        return forge.execute(party, player_id, action, params["recipe"], error)
    position = party["position"]
    if party["transit"] and not party["battle"]:
        raise error("moving", "Attendez votre arrivée pour interagir.", 409)
    if action == "talk" and params["npc"] == "leon":
        merchant = npc(now)
        if party["battle"] or not merchant["location"] or world.zone_of(position) not in ("rosee", "brume") or merchant["location"] not in world.PLACES[world.zone_of(position)]["name"] or position in world.ROAD_POINTS:
            raise error("invalid_npc", "Léon n'est pas présent dans votre zone.", 409)
        return ["Léon : je séjourne huit heures dans chaque village. Ma boutique n'est pas encore ouverte."], False
    if action == "craft" and party["quest"] != "completed":
        raise error("forge_locked", "Forge verrouillée : terminez la quête de Mira et rendez-la au village.", 409)
    if action == "talk" and position != "mira" or action == "craft" and position != "forge":
        raise error("wrong_location", "Rejoignez ce point avant d'y effectuer une action.", 409)
    if action == "explore":
        if party["battle"] or party["mobs"] or position not in ("clearing", "clearing_fight", "hunt", "lisiere", "training"):
            raise error("wrong_location", "Aucune exploration possible à votre position.", 409)
        spawn(party, now, random, messages, origin="explore")
        world.record(party)
        return messages, False
    return execute_one(party, player_id, action, params, now, error, random)


def advance(party, now, random):
    migrate(party, now)
    progression.resources(party, now)
    messages = fields.advance(party, now)
    messages.extend(tactics.complete_casts(party, now, random))
    messages.extend(bleeding.advance(party, now, random))
    messages.extend(tactics.advance(party, now, random))
    fields.reveal(party)
    timed_units = [*((invocation["id"], invocation) for character in party["characters"].values() for invocation in character["invocations"]), *party["characters"].items(), *((mob["combat_id"], mob) for mob in party["mobs"])]
    for key, data in timed_units:
        if data["effects"]:
            party["effect_at"].setdefault(key, now + progression.ACTION_SECONDS * progression.RATIO)
        if data["effects"] and party["effect_at"].get(key, now + 1) <= now:
            character = unpack(data)
            character._update_status()
            data.update(pack(character))
            party["effect_at"][key] = now + progression.ACTION_SECONDS * progression.RATIO
    sync_mobs(party)
    continue_journey(party, now, random, messages)
    achievements.record(party)
    return messages
