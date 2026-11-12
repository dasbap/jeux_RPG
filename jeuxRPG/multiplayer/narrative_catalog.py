"""Validation of Builder-authored conversations, clues and story objectives."""

import re


def validate(data, maps=None):
    story = data.get("narrative")
    if story is None:
        if any(quest["kind"] == "story" for quest in data["quests"]):
            raise ValueError("Les quêtes narratives demandent un catalogue d’histoire.")
        return

    def text(value, maximum=4000):
        return isinstance(value, str) and 0 < len(value.strip()) <= maximum

    def identifier(value):
        return isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_:-]{1,100}", value)

    if (
        not isinstance(story, dict)
        or set(story) != {"title", "facts", "npcs"}
        or not text(story["title"], 100)
        or not isinstance(story["facts"], dict)
        or len(story["facts"]) > 300
        or not isinstance(story["npcs"], dict)
        or len(story["npcs"]) > 200
    ):
        raise ValueError("Histoire : titre, indices et conversations requis.")
    quests = {quest["id"] for quest in data["quests"]}
    facts = set(story["facts"])
    sites = {
        site["id"]
        for definition in (maps or {}).values()
        for site in definition.get("sites", [])
    }

    def references(value):
        for field, known in (
            ("requires", quests),
            ("excludes", quests),
            ("requires_facts", facts),
            ("facts", facts),
        ):
            keys = value.get(field, [])
            if (
                not isinstance(keys, list)
                or len(keys) > 50
                or any(not isinstance(key, str) or key not in known for key in keys)
            ):
                raise ValueError(f"Histoire : références {field} invalides.")

    for key, fact in story["facts"].items():
        if (
            not identifier(key)
            or not isinstance(fact, dict)
            or set(fact) != {"name", "description", "map", "npc"}
            or not text(fact["name"], 150)
            or not text(fact["description"])
            or not identifier(fact["map"])
            or not identifier(fact["npc"])
        ):
            raise ValueError("Histoire : indice invalide.")
        if maps is not None and (
            fact["map"] not in maps
            or fact["npc"] not in sites
            or not any(
                site["id"] == fact["npc"] for site in maps[fact["map"]].get("sites", [])
            )
        ):
            raise ValueError("Histoire : emplacement d’un indice introuvable.")
    _validate_npcs(story, sites, maps, text, identifier, references)
    if any(quest["npc"] not in story["npcs"] for quest in data["quests"]):
        raise ValueError(
            "Histoire : chaque donneur de quête doit avoir une conversation pour proposer ses contrats explicitement."
        )
    _validate_quests(data, facts, text, identifier)
    _validate_reachability(data)


def _validate_reachability(data):
    """Reject prerequisite loops that also pass through a conversation or clue."""
    sources = []
    for npc, definition in data["narrative"]["npcs"].items():
        for topic in definition["topics"]:
            sources.append(
                (
                    npc,
                    set(topic.get("requires", [])),
                    set(topic.get("requires_facts", [])),
                    set(topic.get("facts", [])),
                )
            )
            for answer in topic.get("choices", []):
                sources.append(
                    (
                        npc,
                        set(topic.get("requires", []))
                        | set(answer.get("requires", [])),
                        set(topic.get("requires_facts", []))
                        | set(answer.get("requires_facts", [])),
                        set(answer.get("facts", [])),
                    )
                )
    for quest in data["quests"]:
        for key in quest.get("objectives", []) if quest["kind"] == "story" else []:
            expected = data["narrative"]["facts"][key]["npc"]
            if not any(
                npc == expected and key in emitted for npc, _, _, emitted in sources
            ):
                raise ValueError(
                    quest["name"]
                    + " : un indice ne peut pas être recueilli au lieu indiqué."
                )
    completed, learned = set(), set()
    while True:
        before = (len(completed), len(learned))
        for _, quests, facts, emitted in sources:
            if quests <= completed and facts <= learned:
                learned.update(emitted)
        for quest in data["quests"]:
            if set(quest.get("requirements", {}).get("quests", [])) <= completed and (
                quest["kind"] != "story" or set(quest["objectives"]) <= learned
            ):
                completed.add(quest["id"])
        if before == (len(completed), len(learned)):
            break
    if any(quest["id"] not in completed for quest in data["quests"]):
        raise ValueError(
            "Histoire : une boucle entre quêtes, dialogues et indices rend une suite impossible."
        )


def _validate_npcs(story, sites, maps, text, identifier, references):
    for npc, definition in story["npcs"].items():
        if (
            not identifier(npc)
            or not isinstance(definition, dict)
            or set(definition) - {"greetings", "service"} != {"greeting", "topics"}
            or not text(definition["greeting"])
            or definition.get("service", "") not in ("", "forge")
            or not isinstance(definition["topics"], list)
            or len(definition["topics"]) > 50
        ):
            raise ValueError("Histoire : conversation invalide.")
        if maps is not None and npc not in sites:
            raise ValueError("Histoire : personnage introuvable " + npc)
        greetings = definition.get("greetings", [])
        if not isinstance(greetings, list) or len(greetings) > 30:
            raise ValueError("Histoire : salutations invalides.")
        for greeting in greetings:
            if not isinstance(greeting, dict) or not text(greeting.get("text")):
                raise ValueError("Histoire : salutation invalide.")
            references(greeting)
        ids = set()
        for topic in definition["topics"]:
            if (
                not isinstance(topic, dict)
                or not identifier(topic.get("id"))
                or topic["id"] in ids
                or not text(topic.get("label"), 150)
                or not text(topic.get("text"))
            ):
                raise ValueError("Histoire : sujet invalide ou dupliqué.")
            ids.add(topic["id"])
            references(topic)
            choices = topic.get("choices", [])
            if not isinstance(choices, list) or len(choices) > 12:
                raise ValueError("Histoire : réponses invalides.")
            answers = set()
            for answer in choices:
                if (
                    not isinstance(answer, dict)
                    or not identifier(answer.get("id"))
                    or answer["id"] in answers
                    or not text(answer.get("label"), 150)
                    or not text(answer.get("text"))
                    or not isinstance(answer.get("description", ""), str)
                    or len(answer.get("description", "")) > 4000
                    or "ending" in answer
                    and not identifier(answer["ending"])
                ):
                    raise ValueError("Histoire : réponse invalide ou dupliquée.")
                answers.add(answer["id"])
                references(answer)


def _validate_quests(data, facts, text, identifier):
    for quest in data["quests"]:
        if quest["kind"] == "story":
            objectives = quest.get("objectives")
            if (
                not isinstance(objectives, list)
                or not 1 <= len(objectives) <= 12
                or any(
                    not isinstance(key, str) or key not in facts for key in objectives
                )
                or len(set(objectives)) != len(objectives)
                or quest["count"] != len(objectives)
                or quest["target"] not in objectives
            ):
                raise ValueError(quest["name"] + " : objectifs narratifs invalides.")
        for field in ("remember", "repeatable"):
            if type(quest.get(field, False)) is not bool:
                raise ValueError(quest["name"] + " : option narrative invalide.")
        if "recommended_level" in quest and (
            type(quest["recommended_level"]) is not int
            or not 1 <= quest["recommended_level"] <= 100
        ):
            raise ValueError(quest["name"] + " : niveau conseillé invalide.")
        if "reward_title" in quest and not text(quest["reward_title"], 100):
            raise ValueError("Titre narratif invalide.")
        if "previous_contract" in quest and not identifier(quest["previous_contract"]):
            raise ValueError("Ancien contrat narratif invalide.")
        dialogue = quest.get("dialogue", {})
        if (
            not isinstance(dialogue, dict)
            or set(dialogue) - {"accept", "active", "complete"}
            or any(not text(value) for value in dialogue.values())
        ):
            raise ValueError(quest["name"] + " : dialogues de quête invalides.")
