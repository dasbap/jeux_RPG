"""Place regions, sectors and landmarks explicitly in the Builder atlas."""

from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.world_topology import compile_world
from scripts.refine_forgotten_cave import NAMES, ROOMS, refine

GLOBAL = {
    "foret_eveilles": [160, 540],
    "forets_rosee": [480, 540],
    "zone_rosee": [1180, 540],
    "zone_lisiere": [1180, 100],
    "monts_rosee": [820, 260],
    "zone_brume": [1180, 800],
    "grotte_oublies": [160, 160],
}
SECTORS = {
    "clearing": [360, 240],
    "rosee": [600, 600],
    "rosee_caserne": [600, 260],
    "rosee_dortoir": [260, 260],
    "rosee_armurerie": [940, 260],
    "rosee_remparts": [600, 80],
    "rosee_marche": [1100, 600],
    "rosee_habitations": [600, 1000],
    "lisiere": [360, 240],
    "hunt": [760, 240],
    "forest": [240, 260],
    "rosee_clairiere": [240, 80],
    "rosee_ruisseau": [650, 80],
    "rosee_bois": [1060, 260],
    "rosee_verger": [650, 450],
    "rosee_prairies": [240, 450],
    "rosee_contreforts": [620, 290],
    "rosee_col": [620, 80],
    "rosee_tour": [1040, 80],
    "rosee_carriere": [1040, 500],
    "brume": [360, 300],
    "brume_marais": [1200, 300],
    "brume_ruines": [1200, 600],
    "brume_ravin": [1200, 900],
    "brume_sanctuaire": [800, 900],
}


def arrange(project):
    zones = project.maps["clearing"]["logical_zones"]
    cells = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]
    sectors = dict(SECTORS)
    for key, cell in zip(ROOMS, cells, strict=True):
        sectors[key] = [240 + cell % 4 * 390, 180 + cell // 4 * 240]
    for key, position in GLOBAL.items():
        zones[key]["world_view"] = {
            "position": position,
            "entry": [60, 100],
            "points": {},
        }
    for data in project.maps.values():
        data.pop("world_view", None)
    places, _, _, _, owners, _, _ = compile_world(project.maps)
    for zone, place in places.items():
        points = zones[zone]["world_view"]["points"]
        extras = {"clearing": 1}  # Reserve the legacy Ma?l label's automatic position.
        for point in place["points"]:
            key = point["id"]
            if key in sectors:
                points[key] = {"position": sectors[key]}
                if key in ROOMS:
                    points[key]["name"] = (
                        f"{ROOMS.index(key) + 1:02} · {NAMES[ROOMS.index(key)]}"
                    )
            elif ":" not in key:
                owner = owners.get(key)
                anchor = sectors.get(owner, [360, 240])
                n = extras.get(owner, 0)
                extras[owner] = n + 1
                points[key] = {
                    "position": [
                        max(160, anchor[0] - 200) + n % 3 * 220,
                        anchor[1] + 100 + n // 3 * 100,
                    ]
                }
        if zone == "zone_brume":
            for key, position in {
                "arrival": [360, 480],
                "brume_market": [660, 480],
                "brume_shop": [660, 650],
                "brume_inn": [900, 650],
                "elyne": [900, 480],
                "brume_habitations": [360, 750],
                "brume_house": [660, 850],
                "oriel": [160, 300],
            }.items():
                points.setdefault(key, {})["position"] = position
    for route in project.maps["clearing"]["travel_routes"]:
        if route["id"] == "link_3516d81727964944":
            route["name"] = "Descente des Oubliés"
        elif route["id"] == "link_b2f15f563af441e1":
            route["name"] = "Faille de la Lisière"
    project.validate()


if __name__ == "__main__":
    project = Project("projects/authored")
    refine(project)
    arrange(project)
    project.save()
    print("Atlas reorganized: seven regions and twelve labyrinth rooms.")
