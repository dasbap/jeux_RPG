"""Author seamless exits and directed, independently boardable stagecoach stops."""

from jeuxRPG.multiplayer import tactics
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.map_playability import _reachable_cells


def author(project):
    maps = project.maps
    maps["clearing"]["seamless_transitions"] = True

    def free(map_id, anchor):
        data = maps[map_id]
        occupied = (
            {tuple(g["position"]) for g in data["exits"]}
            | {tuple(s["position"]) for s in data.get("sites", [])}
            | {tuple(p) for p in data.get("spawns", [])}
        )
        reached = _reachable_cells(
            tuple(data["exits"][0]["position"]), lambda p: tactics.walkable(data, p)
        )
        return list(
            min(
                (
                    p
                    for p in reached
                    if p not in occupied
                    and 1 < p[0] < data["width"] - 2
                    and 1 < p[1] < data["height"] - 2
                ),
                key=lambda p: (abs(p[0] - anchor[0]) + abs(p[1] - anchor[1]), p),
            )
        )

    links = {
        ("clearing", (31, 0)): ("cave_1", [2, 7]),
        ("cave_1", (0, 7)): ("clearing", [31, 2]),
        ("cave_2", (31, 15)): ("lisiere", [12, 2]),
        ("lisiere", (12, 0)): ("cave_1", [11, 13]),
        ("lisiere", (0, 10)): ("rosee_remparts", [45, 12]),
        ("brume", (0, 16)): ("rosee_habitations", [24, 28]),
    }
    for key, data in maps.items():
        for gate in data["exits"]:
            gate["world_exit"] = False
            if gate["destination"]:
                gate["travel_minutes"] = 0
            target = links.get((key, tuple(gate["position"])))
            if target:
                gate.update(
                    destination=target[0],
                    entry=free(*target),
                    travel_minutes=0,
                    name=f"Vers {maps[target[0]]['name']}",
                )
    for route in maps["clearing"].get("travel_routes", []):
        for endpoint in ("from", "to"):
            point = route.get(endpoint + "_entry")
            if point and any(
                g["position"] == point and g["destination"]
                for g in maps[route[endpoint]]["exits"]
            ):
                route.pop(endpoint + "_entry")
    definitions = {
        "coach_rosee": ("Relais de Rosée", "rosee", [42, 28], True),
        "coach_brume": ("Relais de Brume", "brume", [24, 16], True),
        "coach_foret": ("Relais des Éveillés", "clearing", [8, 10], True),
        "arret_lisiere": ("Arrêt de la Lisière", "lisiere", [5, 8], False),
        "arret_tour": ("Arrêt de la Tour des Cimes", "rosee_tour", [12, 10], False),
        "arret_prairies": ("Arrêt des Prairies", "rosee_prairies", [8, 10], False),
    }
    gameplay = project.content["gameplay"]
    stations = gameplay["coach_stations"]
    for key, (name, map_id, anchor, boarding) in definitions.items():
        maps[map_id]["sites"] = [
            s for s in maps[map_id].get("sites", []) if s["id"] != key
        ]
        position = free(map_id, anchor)
        stations[key] = {
            "name": name,
            "map": map_id,
            "position": position,
            "boarding": boarding,
        }
        maps[map_id]["sites"].append(
            {
                "id": key,
                "name": name,
                "position": position,
                "dialogue": "Choisissez votre destination auprès du cocher."
                if boarding
                else "Arrêt de dépose uniquement. Aucun embarquement ici.",
                "interaction": "talk",
                "coach_stop": True,
                "coach_boarding": boarding,
            }
        )
    routes = [
        ("rosee_brume", "coach_rosee", "coach_brume", 8),
        ("brume_rosee", "coach_brume", "coach_rosee", 8),
        ("foret_rosee", "coach_foret", "coach_rosee", 6),
        ("rosee_foret", "coach_rosee", "coach_foret", 6),
        ("rosee_lisiere", "coach_rosee", "arret_lisiere", 7),
        ("brume_tour", "coach_brume", "arret_tour", 10),
        ("rosee_prairies", "coach_rosee", "arret_prairies", 6),
    ]
    for key, source, target, duration in routes:
        gameplay["coach_routes"][key] = {
            "name": f"{stations[source]['name']} → {stations[target]['name']}",
            "from": source,
            "to": target,
            "duration_seconds": duration,
        }
    from scripts.refine_lisiere import author as refine_lisiere

    refine_lisiere(project)
    project.validate()


if __name__ == "__main__":
    project = Project("projects/authored")
    author(project)
    project.save()
    print(
        "Seamless gates, three boarding relays, three drop-off-only stops, seven directed services."
    )
