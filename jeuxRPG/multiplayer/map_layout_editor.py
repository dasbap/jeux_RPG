import math
import re
from copy import deepcopy


def validate_layout(value):
    if not isinstance(value, dict) or set(value) - {"position", "entry", "points"}:
        raise ValueError("Plan de carte générale invalide.")

    def position(point):
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(
                type(n) not in (int, float)
                or not math.isfinite(n)
                or not 0 <= n <= 10000
                for n in point
            )
        ):
            raise ValueError("Position du plan : deux coordonnées entre 0 et 10000.")

    for key in ("position", "entry"):
        if key in value:
            position(value[key])
    points = value.get("points", {})
    if not isinstance(points, dict) or len(points) > 256:
        raise ValueError("256 points maximum sur le plan.")
    for key, item in points.items():
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[a-z0-9_]{1,64}", key)
            or not isinstance(item, dict)
            or set(item) - {"position", "name"}
        ):
            raise ValueError("Point du plan invalide.")
        if "position" in item:
            position(item["position"])
        if "name" in item and (
            not isinstance(item["name"], str)
            or not 1 <= len(item["name"].strip()) <= 100
        ):
            raise ValueError("Nom du point : 1 à 100 caractères.")


def apply_layout(places, maps):
    for key, place in places.items():
        view = maps.get(key, {}).get("world_view", {})
        validate_layout(view)
        if "position" in view:
            place["x"], place["y"] = view["position"]
        if "entry" in view:
            place["entry"] = deepcopy(view["entry"])
        unplaced = 0
        lower = max((point.get("y", 0) for point in place["points"]), default=0) + 110
        for point in place["points"]:
            if "x" not in point or "y" not in point:
                point.update(x=170 + unplaced % 3 * 180, y=lower + unplaced // 3 * 100)
                unplaced += 1
            item = view.get("points", {}).get(point["id"], {})
            if "position" in item:
                point["x"], point["y"] = item["position"]
            if "name" in item:
                point["name"] = item["name"]
    return places


def layout_places(maps):
    from .map_building import zone_of

    logical = maps.get("clearing", {}).get("logical_zones", {})
    places = {
        key: {"name": data["name"], "x": 70, "y": 300, "points": []}
        for key, data in logical.items()
    }
    for key, data in maps.items():
        zone = zone_of(maps, key)
        definition = logical.get(zone, maps.get(zone))
        place = places.setdefault(
            zone, {"name": definition["name"], "x": 70, "y": 300, "points": []}
        )
        place["points"].append({"id": key, "name": data["name"], "type": "carte"})
    return apply_layout(places, {**maps, **logical})


def zone_level_value(values):
    level = int(values["level"])
    if not 1 <= level <= 100 or not 1 <= len(values["name"].strip()) <= 100:
        raise ValueError("Nom ou niveau invalide.")
    return level


class LayoutEditor:
    def __init__(self, editor):
        import tkinter as tk
        from tkinter import ttk

        from .editor_ui import EditorPanel

        self.editor = editor
        self.panel = EditorPanel(editor.root, "Carte générale et points du lieu")
        body = self.panel.content
        bar = ttk.Frame(body)
        bar.pack(fill="x")
        self.mode = tk.StringVar(value="Points du lieu")
        self.zone = tk.StringVar(value=next(iter(layout_places(editor.maps))))
        editor.maps[editor.selected.get()]
        from .map_building import zone_of

        self.zone.set(zone_of(editor.maps, editor.selected.get()))
        self.zone_choice = None
        for var, values in (
            (self.mode, ["Carte générale", "Points du lieu"]),
            (self.zone, list(layout_places(editor.maps))),
        ):
            choice = ttk.Combobox(
                bar, textvariable=var, values=values, state="readonly"
            )
            choice.pack(side="left", padx=4)
            if var is self.zone:
                self.zone_choice = choice
            choice.bind("<<ComboboxSelected>>", lambda e: self.draw())
        actions = ttk.Frame(body)
        actions.pack(fill="x")
        ttk.Button(
            actions, text="Créer une carte dans la zone", command=self.create_map
        ).pack(side="left", padx=4)
        ttk.Button(
            actions, text="Ouvrir la carte sélectionnée", command=self.open_map
        ).pack(side="left", padx=4)
        ttk.Button(
            actions,
            text="Gérer les trajets et cartes de combat",
            command=editor.edit_world,
        ).pack(side="left", padx=4)
        ttk.Button(bar, text="Créer une zone", command=self.create_zone).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Relier deux zones", command=self.connect_zones).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Supprimer la zone", command=self.delete_zone).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Propriétés zone", command=self.zone_properties).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Modifier le nom", command=self.rename).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Annuler modification", command=self.undo).pack(
            side="left"
        )
        ttk.Label(
            body,
            text="Glissez les cercles pour placer les zones ou les points. Les traits montrent les passages réels. Ouvrez une carte pour placer ses PNJ, ennemis et portes ; gérez les voyages dans Trajets / rues.",
        ).pack(fill="x", pady=6)
        viewport = ttk.Frame(body)
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, background="#101721")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        for orient, command, row, col, sticky in [
            ("horizontal", self.canvas.xview, 1, 0, "ew"),
            ("vertical", self.canvas.yview, 0, 1, "ns"),
        ]:
            scrollbar = ttk.Scrollbar(viewport, orient=orient, command=command)
            scrollbar.grid(row=row, column=col, sticky=sticky)
            self.canvas.configure(
                **{
                    (
                        "xscrollcommand" if orient == "horizontal" else "yscrollcommand"
                    ): scrollbar.set
                }
            )
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)
        self.selected = None
        self.dragging = None
        self.canvas.bind("<Button-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Double-Button-1>", lambda e: self.rename())
        self.draw()

    def draw(self):
        from . import world

        self.canvas.delete("all")
        self.places = layout_places(self.editor.maps)
        self.nodes = {}
        general = self.mode.get() == "Carte générale"
        if general:
            for key, place in self.places.items():
                self.nodes[key] = (place["x"], place["y"], place["name"])
            routes = self.editor.maps["clearing"].get("travel_routes", world.ROUTES)
            edges = [(r["from"], r["to"]) for r in routes]
            edges.extend(
                (key, gate["destination"])
                for key, data in self.editor.maps.items()
                for gate in data["exits"]
                if gate.get("destination") in self.editor.maps
            )
        else:
            place = self.places[self.zone.get()]
            for point in place["points"]:
                self.nodes[point["id"]] = (point["x"], point["y"], point["name"])
            edges = [
                (key, gate["destination"])
                for key, data in self.editor.maps.items()
                for gate in data["exits"]
                if key in self.nodes and gate.get("destination") in self.nodes
            ]
        for a, b in edges:
            if general:
                from .map_building import zone_of

                a = zone_of(self.editor.maps, a) if a in self.editor.maps else a
                b = zone_of(self.editor.maps, b) if b in self.editor.maps else b
            if a in self.nodes and b in self.nodes and a != b:
                self.canvas.create_line(
                    *self.nodes[a][:2], *self.nodes[b][:2], fill="#657385", width=3
                )
        for key, (x, y, name) in self.nodes.items():
            self.canvas.create_oval(
                x - 10,
                y - 10,
                x + 10,
                y + 10,
                fill="#78dab3",
                outline="#baa4ff" if key == self.selected else "#296e58",
                width=3,
                tags=("node", key),
            )
            self.canvas.create_text(
                x, y + 28, text=name, fill="white", tags=("node", key)
            )
        self.canvas.configure(
            scrollregion=(
                0,
                0,
                max(800, max((n[0] for n in self.nodes.values()), default=0) + 180),
                max(450, max((n[1] for n in self.nodes.values()), default=0) + 100),
            )
        )

    def press(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        key = min(
            self.nodes,
            key=lambda k: math.hypot(self.nodes[k][0] - x, self.nodes[k][1] - y),
            default=None,
        )
        if (
            key is None
            or math.hypot(self.nodes[key][0] - x, self.nodes[key][1] - y) > 35
        ):
            return
        self.selected = key
        self.dragging = key
        self.before = deepcopy(self.editor.maps)
        self.draw()

    def drag(self, event):
        if not self.dragging:
            return
        point = [
            round(max(0, min(10000, self.canvas.canvasx(event.x)))),
            round(max(0, min(10000, self.canvas.canvasy(event.y)))),
        ]
        key = self.dragging
        if self.mode.get() == "Carte générale":
            zones = self.editor.maps["clearing"].get("logical_zones", {})
            data = zones[key] if key in zones else self.editor.maps[key]
            data.setdefault("world_view", {})["position"] = point
        else:
            zones = self.editor.maps["clearing"].get("logical_zones", {})
            data = (
                zones[self.zone.get()]
                if self.zone.get() in zones
                else self.editor.maps[self.zone.get()]
            )
            view = data.setdefault("world_view", {})
            if key == "__entry__":
                view["entry"] = point
            else:
                view.setdefault("points", {}).setdefault(key, {})["position"] = point
        self.draw()

    def release(self, event):
        if self.dragging and self.before != self.editor.maps:
            self.editor.history.append(self.before)
            self.editor.history = self.editor.history[-30:]
        self.dragging = None
        self.editor.status.set("Plan modifié. Enregistrez pour appliquer au jeu.")

    def rename(self):
        if not self.selected or self.selected == "__entry__":
            return
        values = self.editor.form("Nom affiché", {"name": self.nodes[self.selected][2]})
        if not values or not values["name"].strip():
            return
        name = values["name"].strip()
        if len(name) > 100:
            self.editor.messages.showerror("Nom", "100 caractères maximum.")
            return
        self.editor.remember()
        if self.mode.get() == "Carte générale":
            zones = self.editor.maps["clearing"].get("logical_zones", {})
            data = (
                zones[self.selected]
                if self.selected in zones
                else self.editor.maps[self.selected]
            )
            data["name"] = name
        else:
            zones = self.editor.maps["clearing"].get("logical_zones", {})
            data = (
                zones[self.zone.get()]
                if self.zone.get() in zones
                else self.editor.maps[self.zone.get()]
            )
            data.setdefault("world_view", {}).setdefault("points", {}).setdefault(
                self.selected, {}
            )["name"] = name
        self.editor.refresh_choice()
        self.draw()

    def open_map(self):
        if self.selected in self.editor.maps and self.mode.get() != "Carte générale":
            self.editor.show_map(self.selected)
            self.panel.destroy()

    def create_map(self):
        key = self.editor.new()
        if key in self.editor.maps:
            self.editor.remember()
            self.editor.maps[key]["zone_id"] = self.zone.get()
            self.editor.refresh_choice()
            self.draw()

    def connect_zones(self):
        import uuid

        from . import world
        from .map_building import zone_of
        from .map_world_editor import add_travel_door, world_metadata

        places = layout_places(self.editor.maps)
        logical = self.editor.maps["clearing"].get("logical_zones", {})
        available = [key for key in places if key in logical]
        if len(available) < 2:
            self.editor.messages.showerror("Liaison", "Créez au moins deux zones.")
            return
        source = self.selected if self.selected in available else available[0]
        target = next((key for key in available if key != source), available[0])
        result = self.editor.form(
            "Relier deux zones",
            {
                "name": "Nouvelle route",
                "from_zone": source,
                "to_zone": target,
                "distance_km": 0.2,
            },
        )
        if not result:
            return
        source, target = result["from_zone"].strip(), result["to_zone"].strip()
        if source not in available or target not in available or source == target:
            self.editor.messages.showerror(
                "Liaison", "Choisissez deux zones distinctes et existantes."
            )
            return
        name = result["name"].strip()
        try:
            distance = float(result["distance_km"].replace(",", "."))
            if not name or len(name) > 100 or not 0.0001 <= distance <= 1000:
                raise ValueError()
        except ValueError:
            self.editor.messages.showerror("Liaison", "Nom ou distance invalide.")
            return
        start = next(
            (
                key
                for key in self.editor.maps
                if zone_of(self.editor.maps, key) == source
            ),
            None,
        )
        end = next(
            (
                key
                for key in self.editor.maps
                if zone_of(self.editor.maps, key) == target
            ),
            None,
        )
        if not start or not end:
            self.editor.messages.showerror(
                "Liaison", "Chaque zone doit contenir au moins une carte."
            )
            return
        doors = self.editor.form(
            "Portes et combat du trajet",
            {
                "from_map": start,
                "from_entry": "",
                "to_map": end,
                "to_entry": "",
                "combat_map": "",
            },
        )
        if not doors:
            return
        start, end = doors["from_map"], doors["to_map"]
        if (
            start not in self.editor.maps
            or end not in self.editor.maps
            or zone_of(self.editor.maps, start) != source
            or zone_of(self.editor.maps, end) != target
        ):
            self.editor.messages.showerror(
                "Liaison", "Les cartes doivent appartenir aux zones choisies."
            )
            return
        try:
            entries = {
                endpoint + "_entry": [
                    int(n.strip()) for n in doors[endpoint + "_entry"].split(",")
                ]
                for endpoint in ("from", "to")
            }
        except ValueError:
            self.editor.messages.showerror(
                "Liaison", "Indiquez les coordonnées x,y de chaque porte."
            )
            return
        candidate = deepcopy(self.editor.maps)
        routes = candidate["clearing"].setdefault(
            "travel_routes", deepcopy(world.ROUTES)
        )
        routes.append(
            {
                "id": "link_" + uuid.uuid4().hex[:16],
                "name": name,
                "from": start,
                "to": end,
                "distance_km": distance,
                "bidirectional": True,
                "combat_map": doors["combat_map"].strip(),
                **entries,
            }
        )
        try:
            for endpoint in ("from", "to"):
                if doors.get(endpoint + "_create_door"):
                    add_travel_door(
                        candidate,
                        start if endpoint == "from" else end,
                        entries[endpoint + "_entry"],
                    )
            world_metadata(candidate, world.VILLAGE_STREETS, routes)
        except ValueError as exc:
            self.editor.messages.showerror("Liaison", str(exc))
            return
        self.editor.remember()
        self.editor.maps = candidate
        self.mode.set("Carte générale")
        self.draw()
        self.editor.status.set("Liaison ajoutée. Enregistrez et redémarrez le serveur.")

    def create_zone(self):
        import re

        values = self.editor.form(
            "Nouvelle zone sans carte", {"id": "", "name": "Nouvelle zone", "level": 1}
        )
        if not values:
            return
        key = values["id"].strip().lower()
        if not key:
            import unicodedata

            name = unicodedata.normalize("NFKD", values["name"])
            name = "".join(char for char in name if not unicodedata.combining(char))
            key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        zones = self.editor.maps["clearing"].setdefault("logical_zones", {})
        if not re.fullmatch(r"[a-z0-9_]{1,64}", key):
            self.editor.messages.showerror(
                "Zone",
                f"Identifiant '{key}' invalide : utilisez 1 à 64 lettres minuscules, chiffres ou underscores.",
            )
            return
        if key in zones:
            self.editor.messages.showerror("Zone", f"La zone '{key}' existe déjà.")
            return
        if key in self.editor.maps:
            self.editor.messages.showerror(
                "Zone", f"'{key}' est déjà utilisé comme identifiant de carte."
            )
            return
        try:
            level = zone_level_value(values)
        except ValueError:
            self.editor.messages.showerror("Zone", "Nom ou niveau invalide.")
            return
        self.editor.remember()
        zones[key] = {
            "name": values["name"].strip(),
            "level": level,
            "world_view": {"position": [350, 300]},
        }
        self.zone_choice["values"] = list(layout_places(self.editor.maps))
        self.zone.set(key)
        self.mode.set("Carte générale")
        self.draw()

    def zone_properties(self):
        key = self.selected if self.mode.get() == "Carte générale" else self.zone.get()
        zones = self.editor.maps["clearing"].get("logical_zones", {})
        if key not in zones:
            return
        zone = zones[key]
        values = self.editor.form(
            "Propriétés de la zone",
            {
                "name": zone["name"],
                "level": zone.get("level", 1),
                "description": zone.get("description", ""),
            },
        )
        if not values:
            return
        try:
            level = zone_level_value(values)
        except ValueError:
            self.editor.messages.showerror("Zone", "Nom ou niveau invalide.")
            return
        self.editor.remember()
        zone.update(
            name=values["name"].strip(),
            level=level,
            description=values["description"].strip(),
        )
        self.draw()

    def delete_zone(self):
        key = self.selected if self.mode.get() == "Carte générale" else self.zone.get()
        zones = self.editor.maps["clearing"].get("logical_zones", {})
        if key not in zones:
            return
        if any(data.get("zone_id") == key for data in self.editor.maps.values()):
            self.editor.messages.showerror(
                "Zone", "Détachez d'abord les cartes de cette zone."
            )
            return
        self.editor.remember()
        del zones[key]
        self.selected = None
        self.zone_choice["values"] = list(layout_places(self.editor.maps))
        self.zone.set(next(iter(layout_places(self.editor.maps))))
        self.draw()

    def undo(self):
        self.editor.undo()
        self.draw()
