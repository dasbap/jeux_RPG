from copy import deepcopy

from jeuxRPG._class.res.character.table_stat_subclass import goblin_table
from .forge import RARE_DROPS


PLACES = {
    "clearing": {"name": "Clairière des Éveillés", "type": "zone", "x": 70, "y": 160,
                 "description": "Votre point de départ, entouré de bois. Le sentier mène à Rosée.",
                 "points": [{"id": "clearing_fight", "name": "Sous-bois", "type": "rencontre", "description": "Le lieu du premier combat."}]},
    "rosee": {"name": "Village de Rosée", "type": "village", "x": 290, "y": 160,
              "description": "Un village forestier avec une place, une forge et un terrain d'entraînement. Il relie la clairière, la lisière et la route de Brume.",
              "points": [{"id": "mira", "name": "Place du village · Mira", "type": "pnj", "description": "Mira propose une quête pour protéger la lisière."},
                         {"id": "forge", "name": "Forge", "type": "atelier", "description": "La forge fabrique six pièces d’armure et les améliore jusqu’à +10 avec des matériaux communs et rares."},
                         {"id": "training", "name": "Terrain d'entraînement", "type": "rencontre", "description": "Essayez vos nouvelles compétences sans récompense supplémentaire."}]},
    "lisiere": {"name": "Lisière de Rosée", "type": "zone", "x": 290, "y": 45,
                "description": "Une zone de chasse proche de Rosée, fréquentée par des gobelins.",
                "points": [{"id": "hunt", "name": "Campement des gobelins", "type": "rencontre", "description": "Les gobelins demandés dans la quête de Mira se trouvent ici."}]},
    "brume": {"name": "Village de Brume", "type": "village", "x": 520, "y": 160,
              "description": "Le second village du parcours, au bout de la route venant de Rosée. Votre arrivée marque la fin du tutoriel.",
              "points": [{"id": "arrival", "name": "Porte du village", "type": "repère", "description": "Point d'arrivée du tutoriel."}]},
}


VILLAGE_STREETS = {
    "rosee": {"square": "mira", "streets": [
        {"id": "rosee_artisans", "name": "Rue des artisans", "buildings": ["forge", "training"]},
        {"id": "rosee_habitations", "name": "Rue des habitations", "buildings": ["rosee_house", "rosee_inn"]},
    ]},
    "brume": {"square": "arrival", "streets": [
        {"id": "brume_market", "name": "Rue du marché", "buildings": ["brume_shop", "brume_inn"]},
        {"id": "brume_habitations", "name": "Rue des habitations", "buildings": ["brume_house"]},
    ]},
}

for village, layout in VILLAGE_STREETS.items():
    points = PLACES[village]["points"]
    square = next(point for point in points if point["id"] == layout["square"])
    square.update(x=170, y=110)
    if village == "brume":
        square.update(name="Place du village", description="La place centrale relie l’entrée et toutes les rues de Brume.")
    for index, street in enumerate(layout["streets"]):
        y = 55 + index * 110
        points.append({"id": street["id"], "name": street["name"], "type": "rue", "description": "Les bâtiments se suivent le long de cette rue.", "x": 300, "y": y})
        for order, building in enumerate(street["buildings"]):
            point = next((point for point in points if point["id"] == building), None)
            if point is None:
                name = "Auberge" if building.endswith("inn") else "Boutique" if building.endswith("shop") else "Maison"
                point = {"id": building, "name": name, "type": "bâtiment", "description": "Bâtiment du village, sans interaction disponible pour le moment."}
                points.append(point)
            point.update(x=430 + order * 130, y=y)



PLACES["lisiere"]["points"].extend([
    {"id": "forest", "name": "Forêt de Rosée", "type": "rencontre", "description": "Une forêt à explorer à pied ; sa sortie rejoint les chemins rapides."},
    *[{"id": f"cave_{index}", "name": f"Grotte · salle {index}", "type": "rencontre", "description": "Une grotte de trois salles : la dernière est une impasse."} for index in (1, 2, 3)],
])

ROUTES = [
    {"id": "clearing_rosee", "from": "clearing", "to": "rosee", "name": "Sentier de Rosée", "distance_km": 0.3},
    {"id": "rosee_lisiere", "from": "rosee", "to": "lisiere", "name": "Chemin de la lisière", "distance_km": 0.2},
    {"id": "rosee_brume", "from": "rosee", "to": "brume", "name": "Route des Deux Villages", "distance_km": 1.0},
]

CURRENT = {"clearing": "clearing", "first_fight": "clearing", "road": "clearing",
           "village": "rosee", "hunt": "lisiere", "craft": "rosee", "travel": "rosee", "complete": "brume"}
GOBLIN = {"hp_first": 18, "hp_hunt": 24, "xp_first": 50, "xp_hunt": 50, "loot": {"peau": 1, "croc": 1}}


def discovery(party):
    step = party["step"]
    visited = {"clearing"}
    if "position" in party:
        visited.update(party.get("visited", []))
        mobs = set(party.get("seen_mobs", []))
        if party["mob"]:
            mobs.add("goblin")
        return visited, mobs
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
    fighting = bool(party.get("battle") or party["mob"] or party.get("mobs"))
    moving = bool(party.get("transit") or party.get("journey"))
    places = []
    for key, definition in PLACES.items():
        if key not in known:
            continue
        place = {"id": key, "name": definition["name"], "type": definition["type"],
                 "x": definition["x"], "y": definition["y"], "visited": key in visited,
                 "description": definition["description"] if key in visited else "Lieu connu, encore non visité. Ses détails seront révélés à votre arrivée.",
                 "points": deepcopy(definition["points"]) if key in visited else []}
        if traveller and key in visited and key in ("rosee", "brume") and traveller["location"] and traveller["location"] in definition["name"]:
            place["points"].append({"id": "leon", "name": traveller["name"], "type": "pnj",
                                    "x": 170, "y": 175, "description": "Marchand itinérant actuellement présent sur la place du village. Son passage suit l'horloge du monde."})
        for point in place["points"]:
            point["action"] = None
            point["locked_reason"] = None
            point["local"] = key == zone_of(party.get("position", CURRENT[step])) and party.get("position") not in ROAD_POINTS
            point["can_interact"] = point["local"] and not fighting and not moving
            if point["id"] == "forge" and party["quest"] != "completed":
                point["locked_reason"] = "Forge verrouillée : terminez la quête de Mira et rendez-la sur la place du village."
            elif point["id"] == "mira" and step == "hunt" and party["kills"] < 3:
                point["locked_reason"] = f"Mira attend encore {3 - party['kills']} gobelin(s) vaincu(s)."
            if not fighting and not moving and party.get("position", CURRENT[step]) == point["id"]:
                if point["id"] == "mira" and (step == "village" or step == "hunt" and party["kills"] == 3):
                    point["action"] = "dialogue"
                elif point["id"] == "forge" and party["quest"] == "completed":
                    point["action"] = "forge"
                elif point["id"] == "clearing_fight" and step == "clearing" or point["id"] == "hunt" and step == "hunt" and party["kills"] < 3 or point["id"] == "training" and step in ("craft", "travel"):
                    point["action"] = "explore"
        places.append(place)
    routes = []
    for definition in ROUTES:
        if definition["from"] in known and definition["to"] in known:
            route = {**definition, "destination": None}
            if not fighting and not moving and step == "road" and route["id"] == "clearing_rosee":
                route["destination"] = "rosee"
            elif not fighting and not moving and step == "travel" and route["id"] == "rosee_brume":
                route["destination"] = "brume"
            routes.append(route)
    bestiary = []
    if "goblin" in mobs:
        advantages = goblin_table["advantage"]
        bestiary.append({"id": "goblin", "rank": "D", "name": "Gobelin des bois", "description": "Un adversaire simple rencontré dans la clairière et la lisière.",
                         "hp": {"first_encounter": GOBLIN["hp_first"], "hunt": GOBLIN["hp_hunt"]},
                         "stats": {key: goblin_table["base_stats"][key] for key in ("force", "endurance", "intelligence", "sagesse")},
                         "weaknesses": [value.name for value in advantages["weakness"]],
                         "resistances": [value.name for value in advantages["resilience"]],
                         "loot": [{"item": key, "quantity": quantity} for key, quantity in GOBLIN["loot"].items()],
                         "rare_loot": [{"item": key, "chance": value} for key, value in RARE_DROPS.items()],
                         "spawn_maps": [{"id": key, "name": point_name(key)} for key in party.get("seen_spawnpoints", ["clearing"]) if zone_of(key) in visited],
                         "xp": {"first_encounter": GOBLIN["xp_first"], "hunt": GOBLIN["xp_hunt"], "training": 0},
                         "locations": [PLACES[key]["name"] for key in ("clearing", "lisiere") if key in visited],
                         "materials_usage": "Deux peaux et trois crocs permettent de fabriquer une veste à Rosée. L'entraînement ne donne aucun butin."})
    current_zone = zone_of(party.get("position", CURRENT[step]))
    if current_zone not in {p["id"] for p in places}:
        definition = PLACES[current_zone]
        places.append({"id": current_zone, **deepcopy(definition), "visited": True})
    return {"current": zone_of(party.get("position", CURRENT[step])), "position": party.get("position", CURRENT[step]), "places": places, "routes": routes, "graph": graph(known), "bestiary": bestiary, "objectives": [{"zone": "rosee", "point": "mira", "x": PLACES["rosee"]["x"], "y": PLACES["rosee"]["y"]}, {"zone": "lisiere", "point": "hunt", "x": PLACES["lisiere"]["x"], "y": PLACES["lisiere"]["y"]}]}


ROAD_POINTS = {r["id"]: {"zone": "lisiere" if r["id"] == "rosee_lisiere" else "clearing" if r["id"] == "clearing_rosee" else "rosee", "name": r["name"]} for r in ROUTES}

LEVELS = {"clearing": 1, "rosee": 1, "lisiere": 2, "brume": 4}


def zone_of(point):
    if point in ROAD_POINTS:
        return ROAD_POINTS[point]["zone"]
    if point in PLACES:
        return point
    for zone, place in PLACES.items():
        if any(p["id"] == point for p in place["points"]):
            return zone
    return None


def point_name(point):
    if point in ROAD_POINTS:
        return ROAD_POINTS[point]["name"]
    zone = zone_of(point)
    if point == zone:
        return PLACES[zone]["name"]
    return next(p["name"] for p in PLACES[zone]["points"] if p["id"] == point)


def hazard(point):
    return point in ROAD_POINTS or point in ("clearing", "clearing_fight", "lisiere", "hunt")


def graph(known):
    graph = {zone: [] for zone in known}
    for zone in known:
        for point in PLACES[zone]["points"]:
            graph[point["id"]] = []
        layout = VILLAGE_STREETS.get(zone)
        chains = [[zone, layout["square"]]] + [[layout["square"], street["id"], *street["buildings"]] for street in layout["streets"]] if layout else [[zone, point["id"]] for point in PLACES[zone]["points"]]
        for chain in chains:
            for source, destination in zip(chain, chain[1:]):
                graph[source].append(destination)
                graph[destination].append(source)
    for route in ROUTES:
        if route["from"] in known and route["to"] in known:
            middle = route["id"]
            graph[middle] = [route["from"], route["to"]]
            graph[route["from"]].append(middle)
            graph[route["to"]].append(middle)
    return graph


def validate_path(start, destination, known, proposed):
    if not isinstance(destination, str) or zone_of(destination) not in known or not isinstance(proposed, list):
        return False
    nodes = graph(known)
    if len(proposed) > len(nodes) or not all(isinstance(point, str) for point in proposed):
        return False
    if len(set(proposed)) != len(proposed) or start in proposed:
        return False
    previous = start
    for point in proposed:
        if point not in nodes.get(previous, []):
            return False
        previous = point
    return previous == destination


def path(start, destination, known):
    if not isinstance(destination, str) or zone_of(destination) not in known:
        return None
    nodes = graph(known)
    queue = [(start, [])]
    visited = set()
    for node, route in queue:
        if node == destination:
            return route
        if node in visited:
            continue
        visited.add(node)
        queue.extend((neighbor, route + [neighbor]) for neighbor in nodes.get(node, []) if neighbor not in visited)
    return None


def distance_km(source, destination):
    road = source if source in ROAD_POINTS else destination if destination in ROAD_POINTS else None
    if road:
        return next(r["distance_km"] for r in ROUTES if r["id"] == road) / 2
    return 0.01


def walking_seconds(source, destination):
    return distance_km(source, destination) / 6 * 3600
