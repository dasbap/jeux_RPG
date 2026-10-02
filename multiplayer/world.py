from copy import deepcopy

from jeuxRPG._class.res.character.table_stat_subclass import goblin_table


PLACES = {
    "clearing": {"name": "Clairière des Éveillés", "type": "zone", "x": 70, "y": 160,
                 "description": "Votre point de départ, entouré de bois. Le sentier mène à Rosée.",
                 "points": [{"id": "clearing_fight", "name": "Sous-bois", "type": "rencontre", "description": "Le lieu du premier combat."}]},
    "rosee": {"name": "Village de Rosée", "type": "village", "x": 290, "y": 160,
              "description": "Un village forestier avec une place, une forge et un terrain d'entraînement. Il relie la clairière, la lisière et la route de Brume.",
              "points": [{"id": "mira", "name": "Place du village · Mira", "type": "pnj", "description": "Mira propose une quête pour protéger la lisière."},
                         {"id": "forge", "name": "Forge", "type": "atelier", "description": "La forge transforme les peaux et crocs de gobelin en veste."},
                         {"id": "training", "name": "Terrain d'entraînement", "type": "rencontre", "description": "Essayez vos nouvelles compétences sans récompense supplémentaire."}]},
    "lisiere": {"name": "Lisière de Rosée", "type": "zone", "x": 290, "y": 45,
                "description": "Une zone de chasse proche de Rosée, fréquentée par des gobelins.",
                "points": [{"id": "hunt", "name": "Campement des gobelins", "type": "rencontre", "description": "Les gobelins demandés dans la quête de Mira se trouvent ici."}]},
    "brume": {"name": "Village de Brume", "type": "village", "x": 520, "y": 160,
              "description": "Le second village du parcours, au bout de la route venant de Rosée. Votre arrivée marque la fin du tutoriel.",
              "points": [{"id": "arrival", "name": "Porte du village", "type": "repère", "description": "Point d'arrivée du tutoriel."}]},
}

ROUTES = [
    {"id": "clearing_rosee", "from": "clearing", "to": "rosee", "name": "Sentier de Rosée"},
    {"id": "rosee_lisiere", "from": "rosee", "to": "lisiere", "name": "Chemin de la lisière"},
    {"id": "rosee_brume", "from": "rosee", "to": "brume", "name": "Route des Deux Villages"},
]

CURRENT = {"clearing": "clearing", "first_fight": "clearing", "road": "clearing",
           "village": "rosee", "hunt": "lisiere", "craft": "rosee", "travel": "rosee", "complete": "brume"}
GOBLIN = {"hp_first": 18, "hp_hunt": 24, "xp_first": 100, "xp_hunt": 200, "loot": {"peau": 1, "croc": 1}}


def discovery(party):
    step = party["step"]
    visited = {"clearing"}
    if step in ("village", "hunt", "craft", "travel", "complete"):
        visited.add("rosee")
    if step in ("hunt", "craft", "travel", "complete"):
        visited.add("lisiere")
    if step == "complete":
        visited.add("brume")
    visited.update(party.get("visited", []))
    mobs = set(party.get("seen_mobs", []))
    if party["mob"] or step not in ("clearing",):
        mobs.add("goblin")
    return visited, mobs


def record(party):
    visited, mobs = discovery(party)
    party["visited"] = sorted(visited)
    party["seen_mobs"] = sorted(mobs)


def view(party, me, traveller=None):
    visited, mobs = discovery(party)
    step = party["step"]
    known = set(visited)
    if step != "clearing" and step != "first_fight":
        known.add("rosee")
    if "rosee" in visited:
        known.add("lisiere")
    if step in ("craft", "travel", "complete"):
        known.add("brume")
    fighting = bool(party["mob"])
    places = []
    for key, definition in PLACES.items():
        if key not in known:
            continue
        place = {"id": key, "name": definition["name"], "type": definition["type"],
                 "x": definition["x"], "y": definition["y"], "visited": key in visited,
                 "description": definition["description"] if key in visited else "Lieu connu, encore non visité. Ses détails seront révélés à votre arrivée.",
                 "points": deepcopy(definition["points"]) if key in visited else []}
        if traveller and key in visited and key in ("rosee", "brume") and traveller["location"] in definition["name"]:
            place["points"].append({"id": "leon", "name": traveller["name"], "type": "pnj",
                                    "description": "Marchand itinérant actuellement présent dans ce village. Son passage suit l'horloge du monde."})
        for point in place["points"]:
            point["action"] = None
            if not fighting:
                if point["id"] == "mira" and (step == "village" or step == "hunt" and party["kills"] == 3):
                    point["action"] = "dialogue"
                elif point["id"] == "forge" and step == "craft" and me not in party["equipment"]:
                    point["action"] = "forge"
                elif point["id"] == "clearing_fight" and step == "clearing" or point["id"] == "hunt" and step == "hunt" and party["kills"] < 3 or point["id"] == "training" and step in ("craft", "travel"):
                    point["action"] = "explore"
        places.append(place)
    routes = []
    for definition in ROUTES:
        if definition["from"] in known and definition["to"] in known:
            route = {**definition, "destination": None}
            if not fighting and step == "road" and route["id"] == "clearing_rosee":
                route["destination"] = "rosee"
            elif not fighting and step == "travel" and route["id"] == "rosee_brume":
                route["destination"] = "brume"
            routes.append(route)
    bestiary = []
    if "goblin" in mobs:
        advantages = goblin_table["advantage"]
        bestiary.append({"id": "goblin", "name": "Gobelin des bois", "description": "Un adversaire simple rencontré dans la clairière et la lisière.",
                         "hp": {"first_encounter": GOBLIN["hp_first"], "hunt": GOBLIN["hp_hunt"]},
                         "stats": {key: goblin_table["base_stats"][key] for key in ("force", "endurance", "intelligence", "sagesse")},
                         "weaknesses": [value.name for value in advantages["weakness"]],
                         "resistances": [value.name for value in advantages["resilience"]],
                         "loot": [{"item": key, "quantity": quantity} for key, quantity in GOBLIN["loot"].items()],
                         "xp": {"first_encounter": GOBLIN["xp_first"], "hunt": GOBLIN["xp_hunt"], "training": 0},
                         "locations": [PLACES[key]["name"] for key in ("clearing", "lisiere") if key in visited],
                         "materials_usage": "Deux peaux et trois crocs permettent de fabriquer une veste à Rosée. L'entraînement ne donne aucun butin."})
    return {"current": CURRENT[step], "places": places, "routes": routes, "bestiary": bestiary}
