import math
import re
from copy import deepcopy


def add_travel_door(maps, map_id, point, name="Porte de voyage"):
    from . import tactics

    data = maps.get(map_id)
    if data is None or not isinstance(point, list) or len(point) != 2 or any(type(n) is not int for n in point):
        raise ValueError("Carte ou coordonnées de porte invalides.")
    if not tactics.walkable(data, point) or point in data.get("water", []) and point not in data.get("bridges", []):
        raise ValueError("Choisissez une case praticable pour la porte.")
    existing = next((g for g in data["exits"] if g["position"] == point), None)
    if existing:
        if existing.get("destination"):
            raise ValueError("Cette case contient déjà un passage vers une autre carte.")
        return
    if any(item["position"] == point for item in data.get("sites", [])):
        raise ValueError("Cette case contient déjà un PNJ.")
    data["exits"].append({"position": point[:], "destination": None, "entry": None, "name": name})


def world_metadata(maps, streets, routes):
    streets, routes = deepcopy(streets), deepcopy(routes)
    for key, data in maps.items():
        if "village_streets" in data:
            layout = data["village_streets"]
            if (
                not isinstance(layout, dict)
                or not isinstance(layout.get("square"), str)
                or not re.fullmatch(r"[a-z0-9_]{1,64}", layout["square"])
                or not isinstance(layout.get("streets"), list)
                or len(layout["streets"]) > 64
            ):
                raise ValueError(f"{key} : plan de rues invalide.")
            seen = {layout["square"]}
            for street in layout["streets"]:
                if (
                    not isinstance(street, dict)
                    or not isinstance(street.get("id"), str)
                    or not re.fullmatch(r"[a-z0-9_]{1,64}", street["id"])
                    or street["id"] in seen
                    or not isinstance(street.get("name"), str)
                    or not 1 <= len(street["name"]) <= 100
                    or not isinstance(street.get("buildings"), list)
                    or len(street["buildings"]) > 64
                ):
                    raise ValueError(f"{key} : rue invalide ou dupliquée.")
                seen.add(street["id"])
                for point in street["buildings"]:
                    if (
                        not isinstance(point, str)
                        or not re.fullmatch(r"[a-z0-9_]{1,64}", point)
                        or point in seen
                    ):
                        raise ValueError(f"{key} : bâtiment invalide ou dupliqué.")
                    seen.add(point)
            streets[key] = deepcopy(layout)
    if "travel_routes" in maps["clearing"]:
        routes = deepcopy(maps["clearing"]["travel_routes"])
    if not isinstance(routes, list) or not 0 <= len(routes) <= 100:
        raise ValueError("De 0 à 100 chemins rapides autorisés.")
    seen = set()
    for route in routes:
        if (
            not isinstance(route, dict)
            or not isinstance(route.get("id"), str)
            or not re.fullmatch(r"[a-z0-9_]{1,64}", route["id"])
            or route["id"] in seen
            or route.get("from") not in maps
            or route.get("to") not in maps
            or route["from"] == route["to"]
            or not isinstance(route.get("name"), str)
            or not 1 <= len(route["name"]) <= 100
        ):
            raise ValueError("Chemin rapide invalide ou dupliqué.")
        if "bidirectional" in route and type(route["bidirectional"]) is not bool:
            raise ValueError("Sens de chemin invalide.")
        distance = route.get("distance_km")
        if (
            type(distance) not in (int, float)
            or not math.isfinite(distance)
            or not 0.0001 <= distance <= 1000
        ):
            raise ValueError("Distance de chemin comprise entre 0.0001 et 1000 km.")
        for endpoint in ("from", "to"):
            point = route.get(endpoint + "_entry")
            if point is not None:
                data = maps[route[endpoint]]
                if (
                    not isinstance(point, list) or len(point) != 2
                    or any(type(n) is not int for n in point)
                    or not 0 <= point[0] < data["width"]
                    or not 0 <= point[1] < data["height"]
                    or point in data.get("cover", []) + data.get("blocked", [])
                    or point in data.get("water", []) and point not in data.get("bridges", [])
                    or not any(g["position"] == point and not g.get("destination") for g in data["exits"])
                ):
                    raise ValueError("Choisissez une porte de sortie praticable sur chaque carte.")
        if route.get("combat_map") and route["combat_map"] not in maps:
            raise ValueError("Carte de combat inconnue.")
        seen.add(route["id"])
    return streets, routes


class WorldEditor:
    def __init__(self, editor):
        import tkinter as tk
        from tkinter import ttk

        from . import world

        self.editor, self.tk, self.messagebox = editor, tk, editor.messages
        from .content import gameplay

        self.rules = getattr(editor, "gameplay", gameplay())["rules"]
        from .editor_ui import EditorPanel

        self.panel = EditorPanel(editor.root)
        self.window = self.panel.content
        self.panel.title("Trajets et rues")
        self.panel.geometry("850x580")
        self.pending_doors = []
        self.streets, self.routes = world_metadata(
            editor.maps, world.VILLAGE_STREETS, world.ROUTES
        )
        self.zone = tk.StringVar(value=editor.selected.get())
        ttk.Label(
            self.window,
            text="Les durées utilisent la vitesse et le ratio du projet courant. Les rues définissent la topologie de la carte générale ; le décor se peint séparément.",
        ).pack(fill="x", padx=8, pady=8)
        self.roads = tk.Listbox(self.window, height=6)
        self.roads.pack(fill="x", padx=8)
        bar = ttk.Frame(self.window)
        bar.pack(fill="x")
        for label, command in (
            ("Ajouter un chemin", lambda: self.road(True)),
            ("Modifier le chemin", self.road),
            ("Supprimer le chemin", self.delete_road),
        ):
            ttk.Button(bar, text=label, command=command).pack(side="left")
        choice = ttk.Combobox(
            self.window,
            textvariable=self.zone,
            values=list(editor.maps),
            state="readonly",
        )
        choice.pack(fill="x", padx=8, pady=8)
        choice.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.list = tk.Listbox(self.window, height=8)
        self.list.pack(fill="both", expand=True, padx=8)
        bar = ttk.Frame(self.window)
        bar.pack(fill="x")
        for label, command in (
            ("Ajouter une rue", lambda: self.street(True)),
            ("Modifier la rue", self.street),
            ("Supprimer la rue", self.delete),
            ("↑", lambda: self.reorder(-1)),
            ("↓", lambda: self.reorder(1)),
            ("Place centrale", self.square),
            ("Appliquer", self.apply),
        ):
            ttk.Button(bar, text=label, command=command).pack(side="left")
        self.refresh()

    def refresh(self):
        self.roads.delete(0, "end")
        for route in self.routes:
            seconds = (
                route["distance_km"] / self.rules["movement"]["walking_kmh"] * 3600
            )
            self.roads.insert(
                "end",
                f"{route['name']} [{route['id']}] : {route['from']} → {route['to']} · {route['distance_km']:g} km · {seconds / 60:g} min jeu / {seconds / self.rules['time']['game_ratio']:g} s réelles",
            )
        self.list.delete(0, "end")
        for street in self.streets.get(self.zone.get(), {}).get("streets", []):
            self.list.insert(
                "end",
                f"{street['name']} [{street['id']}] : {', '.join(street['buildings'])}",
            )

    def road(self, new=False):
        selection = self.roads.curselection()
        if not new and not selection:
            return
        index = selection[0] if selection else None
        old = {} if new else self.routes[index]
        minutes = (
            old.get("distance_km", 0.1) / self.rules["movement"]["walking_kmh"] * 60
        )
        values = self.editor.form(
            "Chemin rapide",
            {
                "route_id": old.get("id", ""),
                "name": old.get("name", "Chemin"),
                "from_map": old.get("from", "clearing"),
                "from_entry": old.get("from_entry", ""),
                "to_map": old.get("to", "rosee"),
                "to_entry": old.get("to_entry", ""),
                "combat_map": old.get("combat_map", ""),
                "distance_km": old.get("distance_km", 0.1),
                "travel_minutes": minutes,
            },
        )
        if not values:
            return
        try:
            distance = float(values["distance_km"])
            if float(values["travel_minutes"]) != minutes:
                distance = (
                    float(values["travel_minutes"])
                    / 60
                    * self.rules["movement"]["walking_kmh"]
                )
            item = {
                **old,
                "id": values["route_id"],
                "name": values["name"],
                "from": values["from_map"],
                "to": values["to_map"],
                "combat_map": values["combat_map"].strip(),
                "distance_km": distance,
            }
            for endpoint in ("from", "to"):
                raw = values[endpoint + "_entry"].strip()
                if raw:
                    item[endpoint + "_entry"] = [int(n.strip()) for n in raw.split(",")]
                else:
                    item.pop(endpoint + "_entry", None)
            routes = deepcopy(self.routes)
            if new:
                routes.append(item)
            else:
                routes[index] = item
            candidate = deepcopy(self.editor.maps)
            candidate["clearing"]["travel_routes"] = routes
            created = [(item[endpoint], item[endpoint + "_entry"][:])
                       for endpoint in ("from", "to") if values.get(endpoint + "_create_door")]
            for map_id, point in [*self.pending_doors, *created]:
                add_travel_door(candidate, map_id, point)
            world_metadata(candidate, self.streets, routes)
            self.pending_doors.extend(created)
            self.routes = routes
            self.refresh()
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror("Trajet", str(exc), parent=self.window)

    def delete_road(self):
        selection = self.roads.curselection()
        if not selection:
            return
        routes = deepcopy(self.routes)
        routes.pop(selection[0])
        candidate = deepcopy(self.editor.maps)
        candidate["clearing"]["travel_routes"] = routes
        try:
            for map_id, point in self.pending_doors:
                add_travel_door(candidate, map_id, point)
            world_metadata(candidate, self.streets, routes)
            self.routes = routes
            self.refresh()
        except ValueError as exc:
            self.messagebox.showerror("Trajet", str(exc), parent=self.window)

    def layout(self):
        return self.streets.setdefault(
            self.zone.get(), {"square": self.zone.get() + "_square", "streets": []}
        )

    def street(self, new=False):
        selection = self.list.curselection()
        if not new and not selection:
            return
        layout = self.layout()
        index = selection[0] if selection else None
        old = {} if new else layout["streets"][index]
        values = self.editor.form(
            "Rue et ordre des bâtiments",
            {
                "street_id": old.get("id", ""),
                "name": old.get("name", "Rue"),
                "buildings": ",".join(old.get("buildings", [])),
            },
        )
        if values:
            item = {
                "id": values["street_id"].strip(),
                "name": values["name"].strip(),
                "buildings": [
                    v.strip() for v in values["buildings"].split(",") if v.strip()
                ],
            }
            if new:
                layout["streets"].append(item)
            else:
                layout["streets"][index] = item
            self.refresh()

    def delete(self):
        selection = self.list.curselection()
        if selection:
            self.layout()["streets"].pop(selection[0])
            self.refresh()

    def reorder(self, delta):
        selected = self.list.curselection()
        if not selected:
            return
        items = self.layout()["streets"]
        i, j = selected[0], selected[0] + delta
        if 0 <= j < len(items):
            items[i], items[j] = items[j], items[i]
            self.refresh()
            self.list.selection_set(j)

    def square(self):
        layout = self.layout()
        values = self.editor.form("Place centrale", {"square": layout["square"]})
        if values:
            layout["square"] = values["square"].strip()

    def apply(self):
        from .map_assets import validate

        candidate = deepcopy(self.editor.maps)
        candidate["clearing"]["travel_routes"] = deepcopy(self.routes)
        for key, layout in self.streets.items():
            if key in candidate:
                candidate[key]["village_streets"] = deepcopy(layout)
        try:
            for map_id, point in self.pending_doors:
                add_travel_door(candidate, map_id, point)
            world_metadata(candidate, self.streets, self.routes)
            candidate = validate(candidate)
            self.editor.remember()
            self.editor.maps = candidate
            self.editor.draw()
            self.editor.status.set(
                "Trajets et rues appliqués. Enregistrez et redémarrez le serveur."
            )
            self.panel.destroy()
        except ValueError as exc:
            self.messagebox.showerror("Plan", str(exc), parent=self.window)
