from copy import deepcopy
import math
import re


def validate_layout(value):
    if not isinstance(value, dict) or set(value) - {"position", "entry", "points"}:
        raise ValueError("Plan de carte générale invalide.")
    def position(point):
        if not isinstance(point, list) or len(point) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 10000 for n in point):
            raise ValueError("Position du plan : deux coordonnées entre 0 et 10000.")
    for key in ("position", "entry"):
        if key in value:
            position(value[key])
    points = value.get("points", {})
    if not isinstance(points, dict) or len(points) > 256:
        raise ValueError("256 points maximum sur le plan.")
    for key, item in points.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", key) or not isinstance(item, dict) or set(item) - {"position", "name"}:
            raise ValueError("Point du plan invalide.")
        if "position" in item:
            position(item["position"])
        if "name" in item and (not isinstance(item["name"], str) or not 1 <= len(item["name"].strip()) <= 100):
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
    from . import world
    from .map_building import zone_of
    places = deepcopy(world.PLACES)
    for key in list(places):
        if key not in maps:
            del places[key]
    map_ids = set(maps)
    for place in places.values():
        place["points"] = [p for p in place["points"] if p["id"] not in map_ids and p["type"] != "rue"]
    for key, data in maps.items():
        zone = zone_of(maps, key)
        if zone == key:
            places.setdefault(key, {"name": data["name"], "x": 70, "y": 300, "points": []})
            places[key]["name"] = data["name"]
        else:
            places.setdefault(zone, {"name": maps[zone]["name"], "x": 70, "y": 300, "points": []})["points"].append({"id": key, "name": data["name"], "type": "rencontre"})
    for key, place in places.items():
        streets = maps[key].get("village_streets", world.VILLAGE_STREETS.get(key, {}))
        square_id = streets.get("square")
        if square_id:
            square = next((p for p in place["points"] if p["id"] == square_id), None)
            if square is None:
                square = {"id": square_id, "name": "Place centrale", "type": "repère"}
                place["points"].append(square)
            square.update(x=170, y=110)
        for i, street in enumerate(streets.get("streets", [])):
            y = 55 + i * 110
            place["points"].append({"id": street["id"], "name": street["name"], "type": "rue", "x": 300, "y": y})
            for j, building in enumerate(street["buildings"]):
                point = next((p for p in place["points"] if p["id"] == building), None)
                if point is None:
                    point = {"id": building, "name": "Bâtiment", "type": "bâtiment"}
                    place["points"].append(point)
                point.update(x=430 + j * 130, y=y)
    return apply_layout(places, maps)


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
        selected = editor.maps[editor.selected.get()]
        from .map_building import zone_of
        self.zone.set(zone_of(editor.maps, editor.selected.get()))
        for var, values in ((self.mode, ["Carte générale", "Points du lieu"]), (self.zone, list(layout_places(editor.maps)))):
            choice = ttk.Combobox(bar, textvariable=var, values=values, state="readonly")
            choice.pack(side="left", padx=4)
            choice.bind("<<ComboboxSelected>>", lambda e: self.draw())
        ttk.Button(bar, text="Modifier le nom", command=self.rename).pack(side="left", padx=4)
        ttk.Button(bar, text="Annuler modification", command=self.undo).pack(side="left")
        ttk.Label(body, text="Glissez les cercles pour placer les zones ou les points. Les traits représentent les chemins et rues ; leur topologie se modifie dans Trajets / rues.").pack(fill="x", pady=6)
        viewport = ttk.Frame(body)
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, background="#101721")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        for orient, command, row, col, sticky in [("horizontal", self.canvas.xview, 1, 0, "ew"), ("vertical", self.canvas.yview, 0, 1, "ns")]:
            scrollbar = ttk.Scrollbar(viewport, orient=orient, command=command)
            scrollbar.grid(row=row, column=col, sticky=sticky)
            self.canvas.configure(**{("xscrollcommand" if orient == "horizontal" else "yscrollcommand"): scrollbar.set})
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
        else:
            place = self.places[self.zone.get()]
            self.nodes["__entry__"] = (*place.get("entry", [70, 110]), "Entrée")
            for i, point in enumerate(place["points"]):
                self.nodes[point["id"]] = (point.get("x", 270 if i % 2 == 0 else 450), point.get("y", 65 if i < 2 else 175), point["name"])
            layout = self.editor.maps[self.zone.get()].get("village_streets", world.VILLAGE_STREETS.get(self.zone.get()))
            chains = [["__entry__", layout["square"]], *[[layout["square"], s["id"], *s["buildings"]] for s in layout["streets"]]] if layout else []
            connected = {n for chain in chains for n in chain}
            chains.extend([["__entry__", key] for key in self.nodes if key != "__entry__" and key not in connected])
            edges = [(a, b) for chain in chains for a, b in zip(chain, chain[1:])]
        for a, b in edges:
            if a in self.nodes and b in self.nodes:
                self.canvas.create_line(*self.nodes[a][:2], *self.nodes[b][:2], fill="#657385", width=3)
        for key, (x, y, name) in self.nodes.items():
            self.canvas.create_oval(x-10, y-10, x+10, y+10, fill="#78dab3", outline="#baa4ff" if key == self.selected else "#296e58", width=3, tags=("node", key))
            self.canvas.create_text(x, y+28, text=name, fill="white", tags=("node", key))
        self.canvas.configure(scrollregion=(0, 0, max(800, max((n[0] for n in self.nodes.values()), default=0)+180), max(450, max((n[1] for n in self.nodes.values()), default=0)+100)))

    def press(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        key = min(self.nodes, key=lambda k: math.hypot(self.nodes[k][0]-x, self.nodes[k][1]-y), default=None)
        if key is None or math.hypot(self.nodes[key][0]-x, self.nodes[key][1]-y) > 35:
            return
        self.selected = key
        self.dragging = key
        self.before = deepcopy(self.editor.maps)
        self.draw()

    def drag(self, event):
        if not self.dragging:
            return
        point = [round(max(0, min(10000, self.canvas.canvasx(event.x)))), round(max(0, min(10000, self.canvas.canvasy(event.y))))]
        key = self.dragging
        if self.mode.get() == "Carte générale":
            self.editor.maps[key].setdefault("world_view", {})["position"] = point
        else:
            view = self.editor.maps[self.zone.get()].setdefault("world_view", {})
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
            self.editor.maps[self.selected]["name"] = name
        else:
            self.editor.maps[self.zone.get()].setdefault("world_view", {}).setdefault("points", {}).setdefault(self.selected, {})["name"] = name
        self.editor.refresh_choice()
        self.draw()

    def undo(self):
        self.editor.undo()
        self.draw()
