import argparse
from copy import deepcopy
from pathlib import Path

from . import fields
from .map_assets import load, save
from . import tactics
from .map_building import MOBS, map_level, zone_of, sync_overlap


class MapEditor:
    def __init__(self, root, path=None):
        self.root = root
        self.maps = deepcopy(fields.MAPS)
        self.path = Path(path) if path else Path.cwd() / "maps" / "world.json" if (Path.cwd() / "maps" / "world.json").exists() else None
        if self.path and self.path.exists():
            self.maps = load(self.path)
            if self.path.is_dir():
                self.path = None
        self.saved = deepcopy(self.maps)
        self.history = []
        self.size = 24
        self.tool = tk.StringVar(value="Sol")
        self.selected = tk.StringVar(value=next(iter(self.maps)))
        self.status = tk.StringVar()
        self.search = tk.StringVar()
        self.zone_filter = tk.StringVar()
        self.min_level = tk.StringVar()
        self.max_level = tk.StringVar()
        self.brush = tk.StringVar(value="1")
        self.layers = {name: tk.BooleanVar(value=True) for name in ("Décor", "Spawns", "PNJ", "Passages")}
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("RPG — Éditeur de cartes")
        root.geometry("1200x800")
        bar = ttk.Frame(root, padding=6)
        bar.pack(fill="x")
        for label, command in (("Ouvrir", self.open), ("Enregistrer", self.save), ("Enregistrer sous", lambda: self.save(True)), ("Annuler", self.undo), ("Nouvelle carte", self.new), ("Propriétés carte", self.properties)):
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)
        self.displayed_map = tk.StringVar()
        self.choice = ttk.Combobox(bar, textvariable=self.displayed_map, state="readonly", width=32)
        self.choice.pack(side="left", padx=10)
        self.refresh_choice()
        self.choice.bind("<<ComboboxSelected>>", self.select_map)
        ttk.Button(bar, text="−", command=lambda: self.zoom(-4)).pack(side="left")
        ttk.Button(bar, text="+", command=lambda: self.zoom(4)).pack(side="left")
        options = ttk.Frame(root, padding=6)
        options.pack(fill="x")
        ttk.Label(options, text="Rechercher").pack(side="left")
        ttk.Entry(options, textvariable=self.search, width=22).pack(side="left", padx=4)
        ttk.Label(options, text="Zone").pack(side="left")
        self.zone_choice = ttk.Combobox(options, textvariable=self.zone_filter, values=["", *sorted({zone_of(self.maps, key) for key in self.maps})], width=16)
        self.zone_choice.pack(side="left", padx=4)
        ttk.Label(options, text="Niv. min / max").pack(side="left")
        ttk.Entry(options, textvariable=self.min_level, width=3).pack(side="left")
        ttk.Entry(options, textvariable=self.max_level, width=3).pack(side="left")
        self.min_level.trace_add("write", lambda *args: self.refresh_choice())
        self.max_level.trace_add("write", lambda *args: self.refresh_choice())
        self.search.trace_add("write", lambda *args: self.refresh_choice())
        self.zone_filter.trace_add("write", lambda *args: self.refresh_choice())
        ttk.Label(options, text="Pinceau").pack(side="left")
        ttk.Combobox(options, textvariable=self.brush, values=["1", "3", "5"], width=3, state="readonly").pack(side="left")
        for name, variable in self.layers.items():
            ttk.Checkbutton(options, text=name, variable=variable, command=self.draw).pack(side="left")
        advanced = ttk.Frame(root, padding=4)
        advanced.pack(fill="x")
        for label, command in (("Dupliquer", self.duplicate), ("Supprimer carte", self.delete), ("Valider", self.validate), ("Synchroniser les raccords", self.synchronize), ("Fin patrouille", self.end_patrol)):
            ttk.Button(advanced, text=label, command=command).pack(side="left", padx=3)
        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)
        tools = ttk.Frame(body, padding=10)
        tools.pack(side="left", fill="y")
        for label in ("Sol", "Arbre", "Rocher", "Maison", "Eau", "Pont", "Chemin", "Fleurs", "Herbe", "Cristal", "Camp", "Rempart X", "Mur M", "Spawn", "Patrouille", "Téléportation", "PNJ", "Effacer", "Inspecter"):
            ttk.Radiobutton(tools, text=label, variable=self.tool, value=label).pack(anchor="w", pady=3)
        ttk.Label(tools, text="Clic : placer / modifier\nGlisser : peindre\nCtrl+Z : annuler\nCtrl+S : enregistrer\n\nPNJ lié : propriétaire\nleader ou ID joueur.\nVide : PNJ fixe.", justify="left").pack(pady=20)
        viewport = ttk.Frame(body)
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, background="#15201b")
        horizontal = ttk.Scrollbar(viewport, orient="horizontal", command=self.canvas.xview)
        vertical = ttk.Scrollbar(viewport, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self.click)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<Motion>", self.hover)
        root.bind("<Control-z>", lambda event: self.undo())
        root.bind("<Control-s>", lambda event: self.save())
        ttk.Label(root, textvariable=self.status, padding=6).pack(fill="x")
        self.draw()

    def refresh_choice(self):
        query = self.search.get().casefold() if hasattr(self, "search") else ""
        zone = self.zone_filter.get() if hasattr(self, "zone_filter") else ""
        minimum = self.min_level.get() if hasattr(self, "min_level") else ""
        maximum = self.max_level.get() if hasattr(self, "max_level") else ""
        low = int(minimum) if minimum.isdigit() else 1
        high = int(maximum) if maximum.isdigit() else 100
        labels = {f"{value['name']} [{key}] · niv. {map_level(self.maps, key)}": key for key, value in self.maps.items() if query in (value["name"] + " " + key).casefold() and (not zone or zone_of(self.maps, key) == zone) and low <= map_level(self.maps, key) <= high}
        if hasattr(self, "zone_choice"):
            self.zone_choice.configure(values=["", *sorted({zone_of(self.maps, key) for key in self.maps})])
        self.map_labels = labels
        self.choice.configure(values=list(labels))
        if hasattr(self, "displayed_map"):
            self.displayed_map.set(next((label for label, key in labels.items() if key == self.selected.get()), ""))

    def select_map(self, event=None):
        if self.displayed_map.get() not in self.map_labels:
            return
        self.selected.set(self.map_labels[self.displayed_map.get()])
        self.draw()

    def visible_layer(self, name):
        return not hasattr(self, "layers") or self.layers[name].get()

    def end_patrol(self):
        self.patrol_spawn = None
        self.status.set("Patrouille terminée. Recliquer un spawner avec l’outil Patrouille pour éditer son trajet.")

    def duplicate(self):
        key = simpledialog.askstring("Dupliquer", "Nouvel identifiant unique")
        if not key or key in self.maps:
            return
        self.remember()
        source = self.selected.get()
        data = deepcopy(self.maps[source])
        data.update(id="field_" + key, name=data["name"] + " · copie")
        data.pop("world_origin", None)
        data.pop("overlap_columns", None)
        data["zone_id"] = zone_of(self.maps, source)
        self.maps[key] = data
        self.selected.set(key)
        self.refresh_choice()
        self.draw()

    def delete(self):
        key = self.selected.get()
        if key in {"clearing", "rosee", "lisiere", "hunt", "forest", "cave_1", "cave_2", "cave_3", "brume"}:
            messagebox.showerror("Suppression", "Cette carte est nécessaire au tutoriel.")
            return
        if any(item.get("destination") == key or item.get("fast_destination") == key for value in self.maps.values() for item in value["exits"]) or any(other != key and (zone_of(self.maps, other) == key or any(value.get(field) == key for field in ("zone_id", "world_zone", "fast_travel_origin"))) for other, value in self.maps.items()):
            messagebox.showerror("Suppression", "Retirez d’abord les passages et rattachements vers cette carte.")
            return
        self.remember()
        del self.maps[key]
        self.selected.set(next(iter(self.maps)))
        self.refresh_choice()
        self.draw()

    def validate(self):
        from .map_assets import validate
        try:
            validate(self.maps)
            messagebox.showinfo("Validation", "Cartes, niveaux, spawners et chemins valides.")
        except ValueError as exc:
            messagebox.showerror("Validation", str(exc))

    def synchronize(self):
        self.remember()
        count = sync_overlap(self.maps, self.selected.get())
        self.draw()
        messagebox.showinfo("Raccords", f"{count} carte(s) voisine(s) synchronisée(s). Les entités et passages sont conservés. Validez avant d’enregistrer.")

    def close(self):
        if self.maps != self.saved and not messagebox.askyesno("Modifications non enregistrées", "Fermer sans enregistrer ?"):
            return
        self.root.destroy()

    def remember(self):
        self.history.append(deepcopy(self.maps))
        self.history = self.history[-30:]

    def undo(self):
        if self.history:
            self.maps = self.history.pop()
            if self.selected.get() not in self.maps:
                self.selected.set(next(iter(self.maps)))
            self.refresh_choice()
            self.draw()

    def coordinates(self, event):
        return [int(self.canvas.canvasx(event.x) // self.size), int(self.canvas.canvasy(event.y) // self.size)]

    def hover(self, event):
        x, y = self.coordinates(event)
        self.status.set(f"{self.selected.get()} · case {x}, {y} · {self.tool.get()} · {self.path or 'non enregistré'}")

    def zoom(self, delta):
        self.size = max(12, min(64, self.size + delta))
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        data = self.maps[self.selected.get()]
        size = self.size
        self.canvas.configure(scrollregion=(0, 0, data["width"] * size, data["height"] * size))
        colors = {"water": "#348aba", "bridges": "#b99864", "paths": "#aa9b77", "cover": "#354a35"}
        base = "#3e434d" if data.get("biome") == "cave" else "#597244"
        terrain = {field: {tuple(p) for p in data.get(field, [])} for field in colors}
        for y in range(data["height"]):
            for x in range(data["width"]):
                color = base
                for field, value in colors.items():
                    if (x, y) in terrain[field]:
                        color = value
                self.canvas.create_rectangle(x * size, y * size, (x + 1) * size, (y + 1) * size, fill=color, outline="#52634f")
        icons = {"tree": "♣", "rock": "◆", "house": "⌂", "flowers": "✿", "grass": "⁙", "crystal": "✦", "camp": "▲", "barricade": "X", "wall": "M"}
        for decoration in data.get("decorations", []) if self.visible_layer("Décor") else []:
            self.label(decoration["position"], icons.get(decoration["kind"], "?"), "#e4dfb8")
        for position in data.get("spawns", []) if self.visible_layer("Spawns") else []:
            config = next((c for c in data.get("spawners", []) if c["position"] == position), {})
            self.label(position, {"goblin": "G", "orc": "O", "dragon_whelp": "D"}.get(config.get("mob_id", "goblin"), "S"), "#ff7777")
            for index, waypoint in enumerate(config.get("patrol", [])):
                self.label(waypoint, str(index + 1), "#ffa552")
        for exit in data.get("exits", []) if self.visible_layer("Passages") else []:
            self.label(exit["position"], "↗", "#80e9ff")
        for site in data.get("sites", []) if self.visible_layer("PNJ") else []:
            self.label(site["position"], "P" if site.get("owner") else "N", "#ffe080")

    def label(self, point, text, color):
        self.canvas.create_text((point[0] + .5) * self.size, (point[1] + .5) * self.size, text=text, fill=color, font=("Arial", max(10, self.size // 2), "bold"))

    def drag(self, event):
        if self.tool.get() not in ("Téléportation", "PNJ", "Inspecter", "Spawn gobelin", "Spawn", "Patrouille"):
            self.click(event, record=False)

    def click(self, event, record=True):
        point = self.coordinates(event)
        data = self.maps[self.selected.get()]
        if not 0 <= point[0] < data["width"] or not 0 <= point[1] < data["height"]:
            return
        tool = self.tool.get()
        if hasattr(self, "brush") and int(self.brush.get()) > 1 and tool not in ("Inspecter", "PNJ", "Téléportation", "Spawn", "Spawn gobelin", "Patrouille") and not getattr(self, "painting", False):
            if record:
                self.remember()
            self.painting = True
            try:
                from types import SimpleNamespace
                for dy in range(int(self.brush.get())):
                    for dx in range(int(self.brush.get())):
                        self.click(SimpleNamespace(x=event.x + dx * self.size, y=event.y + dy * self.size), record=False)
            finally:
                self.painting = False
            self.draw()
            return
        if tool == "Patrouille":
            active = getattr(self, "patrol_spawn", None)
            config = next((item for item in data.get("spawners", []) if item["position"] == point), None)
            if config is not None:
                self.patrol_spawn = (self.selected.get(), point[:])
                if messagebox.askyesno("Patrouille", "Remplacer les points actuels ?"):
                    self.remember()
                    config["patrol"] = []
                self.draw()
                return
            if not active or active[0] != self.selected.get():
                messagebox.showinfo("Patrouille", "Sélectionnez d’abord un spawner avec cet outil.")
                return
            config = next((item for item in data.get("spawners", []) if item["position"] == active[1]), None)
            if config is None or not tactics.walkable(data, point) or len(config.get("patrol", [])) >= 32:
                messagebox.showerror("Patrouille", "Point praticable requis ; 32 points maximum.")
                return
            previous = config.get("patrol", [])[-1] if config.get("patrol") else config["position"]
            if tactics.path(data, previous, point) is None:
                messagebox.showerror("Patrouille", "Point inaccessible depuis le point précédent.")
                return
            self.remember()
            config.setdefault("patrol", []).append(point)
            self.draw()
            return
        if tool == "Inspecter":
            objects = [item for field in ("sites", "exits", "decorations", "spawners") for item in data.get(field, []) if item["position"] == point]
            messagebox.showinfo("Case", str(objects or point))
            return
        if record:
            self.remember()
        if tool in ("Téléportation", "PNJ"):
            field = "exits" if tool == "Téléportation" else "sites"
            existing = next((item for item in data.get(field, []) if item["position"] == point), None)
            values = ({"name": "Passage", "destination": None, "entry": [1, 1], "fast_destination": "", **(existing or {}), "bidirectional": False} if field == "exits" else {"id": "pnj_" + str(point[0]) + "_" + str(point[1]), "name": "PNJ", "dialogue": "Bonjour !", "owner": "", **(existing or {})})
            result = self.form(tool, values)
            if result is None:
                return
            result["position"] = point
            if field == "exits":
                try:
                    self.set_gate(point, result)
                except ValueError as exc:
                    messagebox.showerror("Téléportation", str(exc))
                    return
            else:
                result["owner"] = result.get("owner") or None
                data[field] = [item for item in data.get(field, []) if item["position"] != point] + [result]
        elif tool in ("Spawn", "Spawn gobelin"):
            if not tactics.walkable(data, point):
                messagebox.showerror("Spawn", "Choisissez une case praticable.")
                return
            existing = next((item for item in data.get("spawners", []) if item["position"] == point), {})
            values = {"mob_id": "goblin", "level": "", "count": 1, "name": "", **{key: value for key, value in existing.items() if key != "patrol"}}
            result = self.form("Spawner", values)
            if result is None:
                return
            try:
                result.update(position=point, count=int(result["count"]), level=int(result["level"]) if result.get("level") else None)
                if existing.get("patrol"):
                    result["patrol"] = deepcopy(existing["patrol"])
                if result["mob_id"] not in MOBS or not 1 <= result["count"] <= 5 or result["level"] is not None and not 1 <= result["level"] <= 100:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Spawn", "Espèce valide, groupe 1–5, niveau 1–100 ou vide pour hériter.")
                return
            if point not in data.get("spawns", []):
                data.setdefault("spawns", []).append(point)
            data["spawners"] = [item for item in data.get("spawners", []) if item["position"] != point] + [result]
        else:
            for field in ("cover", "water", "bridges", "blocked", "paths"):
                data[field] = [p for p in data.get(field, []) if p != point]
            data["decorations"] = [item for item in data.get("decorations", []) if item["position"] != point]
            if tool == "Effacer":
                for field in ("sites", "exits"):
                    data[field] = [item for item in data.get(field, []) if item["position"] != point]
                data["spawns"] = [p for p in data.get("spawns", []) if p != point]
                data["spawners"] = [item for item in data.get("spawners", []) if item["position"] != point]
            elif tool == "Eau":
                data["water"].append(point)
                data["blocked"].append(point)
            elif tool == "Pont":
                data["water"].append(point)
                data["bridges"].append(point)
            elif tool == "Chemin":
                data["paths"].append(point)
            elif tool != "Sol":
                kinds = {"Arbre": "tree", "Rocher": "rock", "Maison": "house", "Fleurs": "flowers", "Herbe": "grass", "Cristal": "crystal", "Camp": "camp", "Rempart X": "barricade", "Mur M": "wall"}
                data["decorations"].append({"position": point, "kind": kinds[tool]})
                if tool in ("Arbre", "Rocher", "Maison", "Rempart X", "Mur M"):
                    data["cover"].append(point)
        if not getattr(self, "painting", False):
            self.draw()

    def set_gate(self, point, result):
        source = self.maps[self.selected.get()]
        destination = result.get("destination") or None
        if not tactics.walkable(source, point):
            raise ValueError("Le passage doit être sur une case praticable.")
        if destination is not None and destination not in self.maps:
            raise ValueError("Choisissez une carte destination existante.")
        if not result.get("name", "").strip():
            raise ValueError("Le passage doit avoir un nom.")
        entry = None
        if destination:
            try:
                entry = [int(n.strip()) for n in result.get("entry", "").split(",")]
            except (ValueError, AttributeError):
                raise ValueError("Arrivée : deux coordonnées entières x,y.")
            if not tactics.walkable(self.maps[destination], entry):
                raise ValueError("La case d’arrivée est hors carte ou sur un obstacle.")
            if entry in [gate["position"] for gate in self.maps[destination]["exits"]]:
                raise ValueError("L’arrivée doit être à côté d’un passage, pour éviter une boucle de téléportation.")
        fast_destination = result.get("fast_destination") or None
        if fast_destination and fast_destination not in self.maps:
            raise ValueError("La provenance du chemin rapide doit être une carte existante.")
        reverse = result.get("bidirectional", False) in (True, "True", "1")
        if reverse and (not destination or destination == self.selected.get()):
            raise ValueError("Le retour automatique nécessite une autre carte destination.")
        gate = {"name": result["name"].strip(), "position": point[:], "destination": destination, "entry": entry}
        if fast_destination and not destination:
            gate["fast_destination"] = fast_destination
        reverse_gate = None
        if reverse:
            target = self.maps[destination]
            occupied = [entry, *target.get("spawns", []), *[item["position"] for item in target["exits"] + target.get("sites", [])]]
            reverse_point = tactics.free_position(target, entry, occupied)
            return_entry = tactics.free_position(source, point, [point, *[item["position"] for item in source["exits"]]])
            if tactics.distance(reverse_point, entry) > 1.5 or tactics.distance(return_entry, point) > 1.5:
                raise ValueError("Il faut une case libre voisine des deux passages pour créer le retour.")
            reverse_gate = {"name": "Retour vers " + source["name"], "position": reverse_point, "destination": self.selected.get(), "entry": return_entry}
        source["exits"] = [item for item in source["exits"] if item["position"] != point] + [gate]
        if reverse_gate:
            self.maps[destination]["exits"].append(reverse_gate)

    def form(self, title, values):
        window = tk.Toplevel(self.root)
        window.title(title)
        entries = {}
        for row, (key, value) in enumerate(values.items()):
            if key == "position":
                continue
            labels = {"name": "Nom affiché", "width": "Largeur (cases)", "height": "Hauteur (cases)", "biome": "Ambiance", "destination": "Carte destination (vide = sortie complète)", "entry": "Case d’arrivée x,y", "fast_destination": "Provenance du chemin rapide", "bidirectional": "Créer aussi le passage de retour", "id": "Identifiant PNJ", "dialogue": "Dialogue", "owner": "Joueur lié (leader ou ID, vide = fixe)", "zone_id": "Zone de rattachement (ID)", "zone_level": "Niveau de zone (carte racine, 1–100)", "level": "Niveau local (vide = héritage)", "mob_id": "Espèce", "count": "Nombre de créatures (1–5)"}
            ttk.Label(window, text=labels.get(key, key)).grid(row=row, column=0, padx=8, pady=5)
            if key == "bidirectional":
                variable = tk.BooleanVar(value=bool(value))
                ttk.Checkbutton(window, variable=variable).grid(row=row, column=1, sticky="w", padx=8)
                entries[key] = variable
                continue
            choices = ["", *self.maps] if key in ("destination", "fast_destination", "zone_id") else ["forest", "village", "cave"] if key == "biome" else list(MOBS) if key == "mob_id" else None
            entry = ttk.Combobox(window, values=choices, width=48) if choices is not None else ttk.Entry(window, width=50)
            entry.insert(0, ",".join(map(str, value)) if isinstance(value, list) else str(value) if value is not None else "")
            entry.grid(row=row, column=1, padx=8, pady=5)
            entries[key] = entry
        result = []
        def accept():
            result.append({key: entry.get() for key, entry in entries.items()})
            window.destroy()
        ttk.Button(window, text="Valider", command=accept).grid(row=len(values), column=0)
        ttk.Button(window, text="Annuler", command=window.destroy).grid(row=len(values), column=1)
        window.transient(self.root)
        window.grab_set()
        self.root.wait_window(window)
        return result[0] if result else None

    def new(self):
        key = simpledialog.askstring("Nouvelle carte", "Identifiant : lettres minuscules, chiffres, underscore")
        if not key or key in self.maps:
            return
        self.remember()
        self.maps[key] = fields.terrain(key, key, 30, 20, [], [fields.gate(0, 10, None, None, "Chemins rapides")])
        self.maps[key].update(biome="forest", decorations=[], water=[], bridges=[], blocked=[], paths=[], zone_id=key, zone_level=1, spawners=[])
        self.selected.set(key)
        self.refresh_choice()
        self.draw()
        self.properties()

    def properties(self):
        data = self.maps[self.selected.get()]
        values = {key: data.get(key, "forest") for key in ("name", "width", "height", "biome")}
        values.update(zone_id=data.get("zone_id", data.get("world_zone", self.selected.get())), zone_level=data.get("zone_level", 1), level=data.get("level", ""))
        result = self.form("Carte", values)
        if result:
            try:
                result.update(width=int(result["width"]), height=int(result["height"]))
                if not 4 <= result["width"] <= 128 or not 4 <= result["height"] <= 128:
                    raise ValueError()
                if not result["name"].strip():
                    raise ValueError()
                result["zone_id"] = result.get("zone_id") or self.selected.get()
                result["zone_level"] = int(result.get("zone_level", 1))
                result["level"] = int(result["level"]) if result.get("level") else None
                candidate = deepcopy(self.maps)
                candidate[self.selected.get()].update(result)
                zone_of(candidate, self.selected.get())
                if not 1 <= result["zone_level"] <= 100 or result["level"] is not None and not 1 <= result["level"] <= 100:
                    raise ValueError()
                self.remember()
                result["name"] = result["name"].strip()
                data.update(result)
                self.refresh_choice()
                self.draw()
            except ValueError:
                messagebox.showerror("Carte", "Dimensions 4–128 ; niveaux 1–100 ; zone existante sans cycle ; nom non vide.")

    def open(self):
        path = filedialog.askopenfilename(filetypes=[("Cartes JSON", "*.json")])
        if path:
            try:
                maps = load(path)
                self.remember()
                self.maps, self.path = maps, Path(path)
                self.saved = deepcopy(maps)
                self.selected.set(next(iter(maps)))
                self.refresh_choice()
                self.draw()
            except (ValueError, OSError) as exc:
                messagebox.showerror("Ouverture", str(exc))

    def save(self, choose=False):
        path = self.path
        if choose or not path:
            value = filedialog.asksaveasfilename(defaultextension=".json", initialfile="maps.json", filetypes=[("Cartes JSON", "*.json")])
            if not value:
                return
            path = Path(value)
        try:
            save(path, self.maps)
            self.path = path
            self.saved = deepcopy(self.maps)
            self.status.set(f"Enregistré : {path}. Redémarrez le serveur avec RPG_MAPS_FILE.")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Enregistrement", str(exc))


def main():
    global tk, ttk, filedialog, messagebox, simpledialog
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox, simpledialog
    except ImportError as exc:
        raise SystemExit("Tkinter est requis pour l’éditeur. Installez Python avec Tcl/Tk sous Windows ou python3-tk sous Linux.") from exc
    parser = argparse.ArgumentParser(description="Éditeur graphique externe des cartes RPG")
    parser.add_argument("file", nargs="?")
    args = parser.parse_args()
    root = tk.Tk()
    MapEditor(root, args.file)
    root.mainloop()


if __name__ == "__main__":
    main()
