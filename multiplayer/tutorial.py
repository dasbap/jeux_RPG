from copy import deepcopy

from jeuxRPG._class.character import Character
from jeuxRPG._class.res.classType import SkillType
from jeuxRPG._class.res.character.stats import basic_stat
from jeuxRPG._class.res.character.alteration import alteration
from jeuxRPG._class.sub_character.invocations.invocation import Invocation
from . import world, encounters


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
    return Character.create(player["class_name"], player["id"], player["name"])


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


def unpack(data, master=None):
    if master is None:
        character = Character.create(data["class_name"], data["id"], data["name"])
        if data["level"] > 1:
            character.gain_exp(sum(level * 100 for level in range(1, data["level"])))
    else:
        character = Character.create(data["class_name"], master=master, name=data["name"])
        Invocation.all_invocation.remove(character)
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
        stat = getattr(basic_stat, value["stat"]) if value["stat"] else None
        effect = alteration.Alteration(value["name"], character, value["value"], value["duration"],
                                       character, stat, alteration.AlterationType[value["type"]])
        character.status["alteration"][value["group"]].append(effect)
        if value["group"] in ("buff", "debuff"):
            getattr(character.get_stat(stat.__name__), "buffs" if value["group"] == "buff" else "debuffs").append(effect)
    for value in data["invocations"]:
        character.invocations.add_invocation(unpack(value, character))
    return character


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
            "ready": {p["id"]: 0 for p in players}, "visited": ["clearing"], "seen_mobs": [], "position": "clearing", "journey": [], "mobs": [], "combat_step": "clearing"}


def npc(now):
    return {"name": "Léon, marchand itinérant", "location": "Rosée" if now % 600 < 300 else "Brume"}


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


def view(party, me, now):
    party = deepcopy(party)
    migrate(party, now)
    result = deepcopy(party)
    result["location"], result["objective"] = STEPS[party["step"]]
    result["location"] = world.point_name(party.get("position", world.CURRENT[party["step"]]))
    result["traveller"] = npc(now)
    result["world"] = world.view(party, me, result["traveller"])
    result["players"] = []
    characters = {key: unpack(value) for key, value in party["characters"].items()}
    enemies = {m["combat_id"]: unpack(m) for m in party.get("mobs", [])}
    if not enemies and party["mob"]:
        enemies = {"mob": unpack(party["mob"])}
    mob = next(iter(enemies.values()), None)
    targets = {**characters, **enemies}
    for player_id, data in party["characters"].items():
        character = characters[player_id]
        actionable = bool(mob and character.is_alive() and not character.is_stunned() and party["ready"][player_id] <= now)
        result["players"].append({"id": player_id, "name": character.name, "class_name": character.char_class,
                                  "level": character.level, "exp": character.exp, "next_level_exp": character.level * 100,
                                  "hp": character.hp.current_value, "max_hp": character.hp.value,
                                  "stats": {key: getattr(character, key).current_value for key in ("force", "endurance", "intelligence", "sagesse")},
                                  "stunned": character.is_stunned(), "invocation_limit": character.invocations.get_limit(),
                                  "can_attack": actionable,
                                  "energies": data["energies"], "inventory": party["inventory"][player_id],
                                  "equipment": party["equipment"].get(player_id),
                                  "cooldown_real_seconds": max(0, party["ready"][player_id] - now) / 20,
                                  "skills": [{"name": s.name, "description": s.description, "type": s.skill_type.name,
                                              "cost": s.energie_cost, "energy": s.energie_target.__name__,
                                              "cooldown": s.current_cooldown,
                                              "can_target_others": s.can_target_others,
                                              "targets": [key for key, target in targets.items() if actionable and can_target(character, s, target, target if key in enemies else mob)],
                                              "available": s.is_ready() and s.can_afford(character)}
                                             for s in character.skills.values()],
                                  "upcoming_skills": [{"level": int(level.split()[1]), "name": s.name}
                                                      for level, skills in character.class_skills_dict.items()
                                                      if level.startswith("level ") and int(level.split()[1]) > character.level
                                                      for s in skills.values()],
                                  "invocations": [{"name": i.name, "hp": i.hp.current_value} for i in character.invocations.get_all()]})
    for key in ("characters", "ready"):
        del result[key]
    result["me"] = me
    return result


def execute_one(party, player_id, action, params, now, error):
    characters = {key: unpack(value) for key, value in party["characters"].items()}
    actor = characters[player_id]
    actor.drop_xp = lambda killer: ""
    step = party["step"]
    messages = []
    finished = False
    if action in ("strike", "skill", "rest"):
        if not actor.is_alive():
            raise error("defeated", "Votre personnage est à terre. Un allié peut terminer le combat.", 409)
        if party["ready"][player_id] > now:
            raise error("cooldown", "Votre prochaine action n'est pas encore disponible.", 409)
        mob = unpack(party["mob"]) if party["mob"] else None
        if action != "rest" and mob is None:
            raise error("not_fighting", "Commencez un combat avant d'utiliser une attaque ou une compétence.", 409)
        if mob:
            mob.drop_xp = lambda killer: ""
        for character in characters.values():
            for invocation in character.invocations.get_all():
                invocation.drop_xp = lambda killer: ""
        if actor.is_stunned() and action != "rest":
            raise error("stunned", "Votre personnage est étourdi.", 409)
        if action == "strike":
            if params["target"] != "mob" or not mob.is_alive():
                raise error("invalid_target", "L'attaque simple doit viser un ennemi vivant de ce combat.")
            mob.lose_hp(actor, max(4, actor.force.current_value + 3))
            messages.append(f"{actor.name} porte une attaque simple.")
        elif action == "skill":
            skill = actor.skills.get(params["skill_name"]) if isinstance(params["skill_name"], str) else None
            if skill is None:
                raise error("unknown_skill", "Cette compétence n'est pas acquise par votre classe et votre niveau.")
            target_id = params["target"]
            if not isinstance(target_id, str):
                raise error("invalid_target", "Cible invalide.")
            if skill.skill_type in (SkillType.DAMAGE, SkillType.DEBUFF):
                target = mob if target_id == "mob" else None
            elif skill.skill_type == SkillType.INVOCATION:
                target = actor if target_id == player_id else None
            else:
                target = characters.get(target_id)
            if target is None:
                raise error("invalid_target", "Cette compétence ne peut pas viser cette cible.")
            if not skill.is_ready() or not skill.can_afford(actor):
                raise error("skill_unavailable", "Compétence indisponible : énergie ou délai insuffisant.", 409)
            if not can_target(actor, skill, target, mob):
                raise error("invalid_target", "Aucune action utile de cette compétence n'est possible sur cette cible.")
            try:
                success, message = actor.use_skill(skill.name, target)
            finally:
                for invocation in list(Invocation.all_invocation):
                    if invocation.master is actor:
                        Invocation.all_invocation.remove(invocation)
            if not success:
                raise error("skill_unavailable", "Compétence indisponible : vérifiez l'énergie, le délai et la cible.", 409)
            messages.append(f"{actor.name} utilise {skill.name}.")
        else:
            if mob:
                actor.rest()
                messages.append(f"{actor.name} récupère de l'énergie.")
            else:
                recover(actor)
                messages.append(f"{actor.name} se repose et récupère ses points de vie et son énergie.")
        if mob:
            for invocation in actor.invocations.get_all():
                if invocation.is_alive() and mob.is_alive():
                    invocation.attack(mob)
            if mob.is_alive():
                mob._update_status()
                party["mob"] = pack(mob)
            else:
                party["mob"] = None
                reward = 0 if party.get("training") else world.GOBLIN["xp_first"] if step == "first_fight" else world.GOBLIN["xp_hunt"]
                for key, character in characters.items():
                    if reward:
                        character.gain_exp(reward)
                        inventory = party["inventory"][key]
                        for item, quantity in world.GOBLIN["loot"].items():
                            inventory[item] = inventory.get(item, 0) + quantity
                    if len(party.get("mobs", [])) <= 1:
                        recover(character)
                if step == "first_fight":
                    party["step"] = "road"
                elif not party.get("training") and party["quest"] == "active" and world.zone_of(party.get("position", "lisiere")) == "lisiere":
                    party["kills"] = min(3, party["kills"] + 1)
                messages.append(f"Gobelin vaincu : chaque aventurier reçoit {reward} XP, une peau et un croc." if reward else "Entraînement terminé : vous avez essayé vos compétences sans récompense supplémentaire.")
            if action != "rest":
                actor.rest()
                if action == "skill" and party["mob"]:
                    skill.current_cooldown = skill.cooldown
            actor._update_status()
            if not any(c.is_alive() for c in characters.values()):
                party["mob"] = None
                if step == "first_fight":
                    party["step"] = "clearing"
                for character in characters.values():
                    recover(character)
                messages.append("Le groupe est secouru. Reprenez le combat sans perdre votre progression.")
        party["ready"][player_id] = now + 60 if mob else now
    elif action == "talk":
        if params["npc"] != "mira" or party["mob"]:
            raise error("invalid_npc", "Ce PNJ n'est pas accessible ici.", 409)
        if step == "village":
            party["step"] = "hunt"
            party["quest"] = "active"
            messages.append("Mira : battez trois gobelins de la lisière. Gardez leurs peaux et leurs crocs pour la forge.")
        elif step == "hunt" and party["kills"] == 3:
            party["step"] = "craft"
            party["quest"] = "completed"
            for character in characters.values():
                character.gain_exp(300)
                recover(character)
            messages.append("Mira : merci ! Chaque aventurier reçoit 300 XP. Rendez-vous à la forge pour fabriquer votre veste.")
        else:
            raise error("quest_incomplete", "Mira attend la défaite de trois gobelins.", 409)
    elif action == "craft":
        if step != "craft" or params["recipe"] != "veste" or party["mob"]:
            raise error("invalid_recipe", "Cette recette n'est pas disponible ici.", 409)
        inventory = party["inventory"][player_id]
        if player_id in party["equipment"]:
            raise error("already_crafted", "Votre veste est déjà fabriquée.", 409)
        if inventory.get("peau", 0) < 2 or inventory.get("croc", 0) < 3:
            raise error("missing_materials", "Il faut deux peaux et trois crocs.", 409)
        inventory["peau"] -= 2
        inventory["croc"] -= 3
        party["equipment"][player_id] = "Veste de la lisière · +10 PV, +3 endurance"
        actor.hp.value += 10
        actor.endurance.value += 3
        actor.endurance.current_value += 3
        recover(actor)
        messages.append(f"{actor.name} fabrique et équipe sa veste de la lisière.")
        if len(party["equipment"]) == len(characters):
            party["step"] = "travel"
    else:
        raise error("invalid_command", "Action de tutoriel inconnue.")
    party["characters"] = {key: pack(character) for key, character in characters.items()}
    world.record(party)
    return messages, finished


def migrate(party, now):
    if "position" not in party:
        world.record(party)
    party.setdefault("combat_step", party["step"])
    party.setdefault("position", world.CURRENT[party["step"]])
    party.setdefault("journey", [])
    if "mobs" not in party:
        party["mobs"] = [{**party["mob"], "combat_id": "mob", "next_attack": now + 40}] if party["mob"] else []


def sync_mobs(party):
    party["mob"] = party["mobs"][0] if party["mobs"] else None


def spawn(party, now, random, messages):
    zone = world.zone_of(party["position"])
    level = min(c["level"] for c in party["characters"].values())
    count = encounters.group_size("D", level, (4 if party["position"] == "rosee_brume" else world.LEVELS[zone]), random)
    if not count:
        messages.append("Vous ne croisez aucun gobelin.")
        return
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
                              "rank": "D", "next_attack": now + random() * 40})
    sync_mobs(party)
    messages.append(f"Vous rencontrez {count} gobelin(s) de rang D.")


def continue_journey(party, now, random, messages):
    while party["journey"] and not party["mobs"]:
        destination = party["journey"].pop(0)
        party["position"] = destination
        zone = world.zone_of(destination)
        party["visited"] = sorted(set(party["visited"]) | {zone})
        messages.append(f"Vous arrivez à {world.point_name(destination)}.")
        if zone == "rosee" and party["step"] == "road":
            party["step"] = "village"
        if destination in ("brume", "arrival") and party["step"] == "travel":
            party["step"] = "complete"
            party["journey"] = []
        if world.hazard(destination):
            spawn(party, now, random, messages)
    world.record(party)


def execute(party, player_id, action, params, now, error, random):
    migrate(party, now)
    messages = []
    if action in ("travel", "move"):
        if party["mobs"]:
            raise error("in_combat", "Terminez le combat avant de vous déplacer.", 409)
        destination = params["destination"]
        known = {p["id"] for p in world.view(party, player_id)["places"]}
        path = world.path(party["position"], destination, known)
        if path is None:
            raise error("invalid_destination", "Ce point n'est pas accessible par les chemins connus.", 409)
        party["journey"] = path
        continue_journey(party, now, random, messages)
        return messages, party["step"] == "complete"
    position = party["position"]
    if action == "talk" and position != "mira" or action == "craft" and position != "forge":
        raise error("wrong_location", "Rejoignez ce point avant d'y effectuer une action.", 409)
    if action == "explore":
        if party["mobs"] or party["step"] == "complete" or position not in ("clearing", "clearing_fight", "hunt", "lisiere", "training"):
            raise error("wrong_location", "Aucune exploration possible à votre position.", 409)
        spawn(party, now, random, messages)
        world.record(party)
        return messages, False
    if action in ("strike", "skill", "rest") and party["mobs"]:
        target_id = params.get("target", "mob")
        if not isinstance(target_id, str):
            raise error("invalid_target", "Cible invalide.")
        index = next((i for i, m in enumerate(party["mobs"]) if m["combat_id"] == target_id), 0)
        if action == "strike" or action == "skill" and target_id not in party["characters"]:
            if not any(m["combat_id"] == target_id for m in party["mobs"]):
                raise error("invalid_target", "Cet ennemi n'est pas vivant dans ce combat.")
        selected = party["mobs"][index]
        party["mob"] = selected
        mapped = {**params, "target": "mob" if target_id == selected["combat_id"] else target_id}
        combat_step = party["combat_step"]
        old_step = party["step"]
        party["step"] = combat_step
        messages, _ = execute_one(party, player_id, action, mapped, now, error)
        if party["mob"]:
            party["mobs"][index] = {**party["mob"], "combat_id": selected["combat_id"], "rank": "D", "next_attack": selected["next_attack"]}
        else:
            party["mobs"].pop(index)
        if party["mobs"]:
            party["step"] = old_step
        sync_mobs(party)
        if not party["mobs"]:
            continue_journey(party, now, random, messages)
        return messages, party["step"] == "complete"
    return execute_one(party, player_id, action, params, now, error)


def advance(party, now, random):
    migrate(party, now)
    messages = []
    characters = {key: unpack(value) for key, value in party["characters"].items()}
    for data in party["mobs"]:
        if data["next_attack"] > now:
            continue
        mob = unpack(data)
        alive = [c for c in characters.values() if c.is_alive()]
        if not alive:
            break
        target = alive[min(len(alive) - 1, int(random() * len(alive)))]
        target.drop_xp = lambda killer: ""
        if not mob.is_stunned():
            target.lose_hp(mob, 3)
            messages.append(f"{mob.name} attaque {target.name}.")
        mob._update_status()
        data.update(pack(mob))
        data["next_attack"] = now + 60 + random() * 40
    if party["mobs"] and not any(c.is_alive() for c in characters.values()):
        party["mobs"] = []
        party["journey"] = []
        if party["step"] == "first_fight":
            party["step"] = "clearing"
        party["position"] = "clearing" if party["step"] == "clearing" else "rosee"
        for character in characters.values():
            recover(character)
        messages.append("Le groupe est secouru. Le déplacement est interrompu.")
    party["characters"] = {key: pack(value) for key, value in characters.items()}
    sync_mobs(party)
    return messages
