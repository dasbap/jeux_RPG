"""Repair Lisiere returns and ensure cave entrance cannot bypass the labyrinth."""

from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.map_playability import issues


def author(project):
    maps = project.maps

    def corridor(key, cells):
        data = maps[key]
        for field in ("cover", "blocked", "water"):
            data[field] = [p for p in data.get(field, []) if p not in cells]
        data["decorations"] = [
            d for d in data.get("decorations", []) if d["position"] not in cells
        ]
        for p in cells:
            if p not in data.setdefault("paths", []):
                data["paths"].append(p)

    def gate(key, position, target, entry, name):
        value = next((g for g in maps[key]["exits"] if g["position"] == position), None)
        if value is None:
            value = {"position": position}
            maps[key]["exits"].append(value)
        value.pop("fast_destination", None)
        value.update(
            destination=target,
            entry=entry,
            name=name,
            world_exit=False,
            travel_minutes=0,
        )

    corridor("rosee_remparts", [[x, 12] for x in range(24, 48)])
    corridor("cave_1", [[11, y] for y in range(7, 16)])
    corridor(
        "lisiere", [[12, y] for y in range(0, 11)] + [[x, 10] for x in range(0, 21)]
    )
    gate("lisiere", [0, 10], "rosee_remparts", [45, 12], "Remparts de Ros\u00e9e")
    gate("rosee_remparts", [47, 12], "lisiere", [2, 10], "Lisi\u00e8re de Ros\u00e9e")
    gate(
        "lisiere",
        [12, 0],
        "cave_1",
        [11, 13],
        "Grotte des Oubli\u00e9s \u00b7 entr\u00e9e",
    )
    gate("cave_1", [11, 15], "lisiere", [12, 2], "Retour vers la Lisi\u00e8re")
    next(g for g in maps["lisiere"]["exits"] if g["destination"] == "hunt")["name"] = (
        "Campement gobelin"
    )
    routes = maps["clearing"]["travel_routes"]
    next(r for r in routes if r["id"] == "rosee_lisiere").update(
        **{"from": "rosee_remparts"}
    )
    next(r for r in routes if r["id"] == "link_b2f15f563af441e1").update(
        bidirectional=False, name="Sortie du Tr\u00f4ne vers la Lisi\u00e8re"
    )
    if not any(r["id"] == "lisiere_cave_entrance" for r in routes):
        routes.append(
            {
                "id": "lisiere_cave_entrance",
                "name": "Entr\u00e9e des Oubli\u00e9s",
                "from": "lisiere",
                "to": "cave_1",
                "distance_km": 0.1,
                "bidirectional": True,
            }
        )
    project.validate()
    errors = issues(maps)
    if errors:
        raise ValueError("\n".join(errors))


if __name__ == "__main__":
    project = Project("projects/authored")
    author(project)
    project.save()
