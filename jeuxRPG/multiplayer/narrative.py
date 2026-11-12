"""Personal conversations and quests, authored entirely in the content catalogue."""

from copy import deepcopy


def catalogue():
    from . import content

    return content.DATA.get("narrative", {})


def enabled():
    return bool(catalogue())


def combat_messages(party):
    """Deliver authored enemy speech once, without interrupting the fight."""
    from . import fields

    if not enabled() or not party.get("field_map"):
        return []
    messages = []
    configurations = fields.MAPS[party["field_map"]].get("spawners", [])
    for mob in party.get("mobs", []):
        if not mob.get("alerted") or mob.get("battlecry_spoken"):
            continue
        speech = next(
            (
                config["battlecry"]
                for config in configurations
                if config.get("mob_id") == mob.get("mob_id") and config.get("battlecry")
            ),
            "",
        )
        if speech:
            mob.update(battlecry=speech, battlecry_spoken=True)
            messages.append(f"{mob['name']} : {speech}")
    return messages


def state(party, player):
    from . import content

    players = party.setdefault("narrative_state", {})
    if player not in players:
        # Old shared quests become personal once, preserving earned rewards.
        old = content.quest_states(party)
        players[player] = {
            "quests": deepcopy(old),
            "facts": [],
            "choices": {},
            "titles": [],
            "history": deepcopy(
                party.get("achievements", {}).get("counters", {}).get("kills", {})
            ),
            "conversation": None,
            "revision": 0,
        }
        for quest in content.DATA["quests"]:
            contract = party.get("endgame", {}).get(quest.get("previous_contract"), {})
            if contract and quest["id"] not in players[player]["quests"]:
                players[player]["quests"][quest["id"]] = {
                    "status": "active",
                    "progress": min(quest["count"], contract.get("progress", 0)),
                    "completions": contract.get("completions", 0),
                }
    personal = players[player]
    personal.setdefault(
        "equipment_history",
        {
            piece["recipe"]: {"count": 1, "level": piece.get("level", 0)}
            for piece in party.get("equipment", {}).get(player, {}).values()
        },
    )
    for quest in content.DATA["quests"]:
        for alias in quest.get("previous_ids", []):
            if alias == quest["id"]:
                continue
            old = personal["quests"].pop(alias, None)
            if old:
                current = personal["quests"].setdefault(quest["id"], deepcopy(old))
                current["progress"] = max(
                    current.get("progress", 0), old.get("progress", 0)
                )
                if old.get("status") == "completed":
                    current["status"] = "completed"
    return personal


def completed(party, player, identifier):
    return (
        state(party, player)["quests"].get(identifier, {}).get("status") == "completed"
    )


def requirements(party, player, definition):
    from . import achievements, content

    definitions = {quest["id"]: quest for quest in content.DATA["quests"]}
    required = definition.get("requirements", {})
    missing = [
        "À rendre : " + definitions[key]["name"]
        for key in definition.get("requirements", {}).get("quests", [])
        if not completed(party, player, key)
    ]
    if party["characters"][player]["level"] < required.get("level", 1):
        missing.append(f"Niveau {required['level']} requis")
    titles = {item["id"]: item for item in content.DATA["achievements"]}
    missing.extend(
        "Succès requis : " + titles[key]["name"]
        for key in required.get("achievements", [])
        if not achievements.unlocked(party, titles[key])
    )
    return missing


def eligible(party, player, definition):
    personal = state(party, player)
    return (
        all(completed(party, player, key) for key in definition.get("requires", []))
        and not any(
            completed(party, player, key) for key in definition.get("excludes", [])
        )
        and all(
            key in personal["facts"] for key in definition.get("requires_facts", [])
        )
    )


def progress(party, player, quest, saved):
    personal = state(party, player)
    if quest["kind"] == "story":
        return sum(key in personal["facts"] for key in quest["objectives"])
    if quest["kind"] in ("craft", "upgrade"):
        history = personal["equipment_history"].get(quest["target"], {})
        owned = [
            piece
            for piece in party.get("equipment", {}).get(player, {}).values()
            if piece.get("recipe") == quest["target"]
        ]
        value = (
            max(history.get("count", 0), len(owned))
            if quest["kind"] == "craft"
            else int(
                max(
                    [
                        history.get("level", -1),
                        *(piece.get("level", 0) for piece in owned),
                    ]
                )
                >= quest.get("upgrade_level", 1)
            )
        )
        return min(quest["count"], max(saved.get("progress", 0), value))
    if quest.get("remember"):
        history = personal["history"].get(quest["target"], {})
        return min(
            quest["count"],
            sum(
                count
                for zone, maps in history.items()
                for map_id, count in maps.items()
                if (not quest.get("zone") or quest["zone"] in (zone, map_id))
                and (not quest.get("map") or quest["map"] == map_id)
            ),
        )
    return min(quest["count"], saved.get("progress", 0))


def event(party, kind, target, zone=None, level=None, player=None):
    from . import content

    if not enabled() or party.get("training"):
        return
    map_id = party.get("field_map") or party["position"]
    for identifier in [player] if player else list(party["characters"]):
        personal = state(party, identifier)
        if kind == "kill":
            maps = personal["history"].setdefault(target, {}).setdefault(zone, {})
            maps[map_id] = maps.get(map_id, 0) + 1
        elif kind in ("craft", "upgrade"):
            history = personal["equipment_history"].setdefault(
                target, {"count": 0, "level": 0}
            )
            history["count"] = (
                history["count"] + 1 if kind == "craft" else max(1, history["count"])
            )
            history["level"] = max(history["level"], level or 0)
        for quest in content.DATA["quests"]:
            saved = personal["quests"].get(quest["id"])
            if (
                not saved
                or saved["status"] != "active"
                or requirements(party, identifier, quest)
            ):
                continue
            if (
                quest["kind"] == kind
                and quest["target"] == target
                and (
                    not quest.get("zone")
                    or quest["zone"] in (zone, map_id, party["position"])
                )
                and (not quest.get("map") or quest["map"] == map_id)
                and (
                    kind != "upgrade"
                    or level is not None
                    and level >= quest.get("upgrade_level", 1)
                )
            ):
                saved["progress"] = min(quest["count"], saved.get("progress", 0) + 1)


def accessible(party, player, npc):
    from . import fields, tactics

    if (
        player not in party["characters"]
        or party["characters"][player]["stats"]["hp"]["current"] <= 0
    ):
        return False
    if party.get("field_map") and party.get("battle"):
        unit = party["battle"]["players"][player]
        return npc in {
            site["id"] for site in fields.interactions(party, player)
        } and not any(
            tactics.sees(fields.MAPS[party["field_map"]], mob, unit)
            for mob in party["mobs"]
        )
    return (
        not party.get("battle")
        and not party.get("transit")
        and party["position"] == npc
    )


def quest_view(party, player, quest):
    personal = state(party, player)
    saved = personal["quests"].get(quest["id"], {"status": "available", "progress": 0})
    missing = requirements(party, player, quest)
    value = (
        quest["count"]
        if saved["status"] == "completed"
        else progress(party, player, quest, saved)
    )
    result = {
        **deepcopy(quest),
        **deepcopy(saved),
        "progress": value,
        "missing_requirements": missing,
    }
    if missing and saved["status"] != "completed":
        result["status"] = "locked"
    elif saved["status"] == "active" and value >= quest["count"]:
        result["status"] = "ready"
    if quest["kind"] == "story":
        result["steps"] = [
            {**catalogue()["facts"][key], "done": key in personal["facts"]}
            for key in quest["objectives"]
        ]
    return result


def journal(party, player):
    from . import content

    personal = state(party, player)
    return [
        quest_view(party, player, quest)
        for quest in content.DATA["quests"]
        if quest["id"] in personal["quests"]
    ]


def topics(party, player, npc):
    return [
        topic
        for topic in catalogue()["npcs"][npc].get("topics", [])
        if eligible(party, player, topic)
    ]


def greeting(party, player, npc):
    definition = catalogue()["npcs"][npc]
    result = definition["greeting"]
    for variant in definition.get("greetings", []):
        if eligible(party, player, variant):
            result = variant["text"]
    return result


def view(party, player):
    from . import content, fields

    personal = state(party, player)
    current = personal.get("conversation")
    conversation = None
    if (
        current
        and current["npc"] in catalogue()["npcs"]
        and accessible(party, player, current["npc"])
    ):
        npc = current["npc"]
        site = next(
            site
            for definition in fields.MAPS.values()
            for site in definition["sites"]
            if site["id"] == npc
        )
        definition = catalogue()["npcs"][npc]
        conversation = {
            **deepcopy(current),
            "revision": personal["revision"],
            "name": site["name"],
            "text": current.get("text") or greeting(party, player, npc),
            "service": definition.get("service", ""),
            "topics": [
                {"id": topic["id"], "label": topic["label"]}
                for topic in topics(party, player, npc)
            ],
            "quests": [
                quest_view(party, player, quest)
                for quest in content.DATA["quests"]
                if quest["npc"] == npc
            ],
        }
        topic = next(
            (
                topic
                for topic in topics(party, player, npc)
                if topic["id"] == current.get("topic")
            ),
            None,
        )
        conversation["choices"] = [
            {
                "id": choice["id"],
                "label": choice["label"],
                "description": choice.get("description", ""),
            }
            for choice in (topic or {}).get("choices", [])
            if eligible(party, player, choice)
            and (not choice.get("ending") or not personal.get("ending"))
        ]
    nearby = (
        [site["id"] for site in fields.interactions(party, player)]
        if party.get("field_map") and party.get("battle")
        else [party.get("position")]
    )
    return {
        "title": catalogue()["title"],
        "greetings": {
            npc: greeting(party, player, npc)
            for npc in nearby
            if npc in catalogue()["npcs"]
        },
        "conversation": conversation,
        "notes": [
            {"id": key, **catalogue()["facts"][key]}
            for key in personal["facts"]
            if key in catalogue()["facts"]
        ],
        "ending": personal.get("ending"),
        "titles": personal["titles"],
    }


def interact(party, player, npc, choice, error):
    from . import content

    if not isinstance(npc, str) or not isinstance(choice, str) or len(choice) > 160:
        raise error("invalid_dialogue", "Choix de dialogue invalide.")
    personal = state(party, player)
    if choice == "close":
        personal["conversation"] = None
        return []
    if npc not in catalogue()["npcs"] or not accessible(party, player, npc):
        raise error(
            "wrong_location",
            "Approchez-vous de ce personnage, hors de portée des ennemis.",
            409,
        )
    if choice != "open" and (
        not personal.get("conversation") or personal["conversation"]["npc"] != npc
    ):
        raise error("dialogue_closed", "Ouvrez d’abord cette conversation.", 409)
    response = {"npc": npc}
    messages = []
    if choice.startswith(("accept:", "claim:")):
        action, identifier = choice.split(":", 1)
        quest = next(
            (
                quest
                for quest in content.DATA["quests"]
                if quest["id"] == identifier and quest["npc"] == npc
            ),
            None,
        )
        if quest is None:
            raise error(
                "unknown_quest", "Ce personnage ne propose pas cette quête.", 404
            )
        missing = requirements(party, player, quest)
        if missing:
            raise error("quest_locked", " ; ".join(missing), 409)
        saved = personal["quests"].get(identifier)
        if action == "accept":
            if saved and not (
                saved["status"] == "completed" and quest.get("repeatable")
            ):
                raise error("quest_accepted", "Cette quête a déjà été acceptée.", 409)
            saved = personal["quests"][identifier] = {
                "status": "active",
                "progress": 0,
                "completions": (saved or {}).get("completions", 0),
            }
            saved["progress"] = progress(party, player, quest, saved)
            response["text"] = quest.get("dialogue", {}).get(
                "accept", quest["description"]
            )
            messages.append("Quête acceptée : " + quest["name"])
        else:
            if (
                not saved
                or saved["status"] != "active"
                or progress(party, player, quest, saved) < quest["count"]
            ):
                raise error(
                    "quest_incomplete",
                    "Cette quête n’est pas prête à être rendue.",
                    409,
                )
            from .tutorial import pack, unpack

            actor = unpack(party["characters"][player])
            if quest["reward_xp"]:
                actor.gain_exp(quest["reward_xp"])
            party["characters"][player] = pack(actor)
            saved.update(
                status="completed",
                progress=quest["count"],
                completions=saved.get("completions", 0) + 1,
            )
            title = quest.get("reward_title")
            if title and title not in personal["titles"]:
                personal["titles"].append(title)
            # Kept for old achievements; never used to accept another player's quest.
            from . import achievements

            achievements.event(party, "quests", identifier)
            response["text"] = quest.get("dialogue", {}).get(
                "complete", "Merci pour votre aide."
            )
            messages.append(
                f"Quête terminée : {quest['name']} · {quest['reward_xp']} XP."
            )
    elif choice.startswith("topic:"):
        identifier = choice.split(":", 1)[1]
        topic = next(
            (
                topic
                for topic in topics(party, player, npc)
                if topic["id"] == identifier
            ),
            None,
        )
        if topic is None:
            raise error("topic_locked", "Ce sujet n’est pas disponible.", 409)
        response.update(text=topic["text"], topic=identifier)
        personal["facts"] = sorted(set(personal["facts"]) | set(topic.get("facts", [])))
    elif choice.startswith("answer:"):
        identifier = choice.split(":", 1)[1]
        topic = next(
            (
                topic
                for topic in topics(party, player, npc)
                if topic["id"] == personal["conversation"].get("topic")
            ),
            None,
        )
        answer = next(
            (
                answer
                for answer in (topic or {}).get("choices", [])
                if answer["id"] == identifier and eligible(party, player, answer)
            ),
            None,
        )
        if answer is None:
            raise error("answer_locked", "Cette réponse n’est pas disponible.", 409)
        if answer.get("ending") and personal.get("ending"):
            raise error("ending_chosen", "Vous avez déjà choisi votre conclusion.", 409)
        response.update(text=answer["text"], topic=topic["id"])
        personal["choices"][topic["id"]] = identifier
        personal["facts"] = sorted(
            set(personal["facts"]) | set(answer.get("facts", []))
        )
        if answer.get("ending"):
            personal["ending"] = {
                "id": answer["ending"],
                "name": answer["label"],
                "text": answer["text"],
            }
    elif choice != "open":
        raise error("invalid_dialogue", "Choix de dialogue inconnu.")
    personal["conversation"] = response
    personal["revision"] += 1
    return messages
