import argparse
from copy import deepcopy
from pathlib import Path

from . import fields
from .map_assets import load, save
from . import tactics


class MapEditor:
    def __init__(self, root, path=None):
        self.root = root
        self.maps = deepcopy(fields.MAPS)
        self.path = Path(path) if path else None
        if self.path and self.path.exists():
            self.maps = load(self.path)
        self.saved = deepcopy(self.maps)
        self.history = []
        self.size = 24
        self.tool = tk.StringVar(value="Sol")
        self.selected = tk.StringVar(value=next(iter(self.maps)))
        self.status = tk.StringVar()
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
        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)
        tools = ttk.Frame(body, padding=10)
        tools.pack(side="left", fill="y")
        for label in ("Sol", "Arbre", "Rocher", "Maison", "Eau", "Pont", "Chemin", "Fleurs", "Herbe", "Cristal", "Camp", "Spawn gobelin", "Téléportation", "PNJ", "Effacer", "Inspecter"):
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
        labels = {f"{value['name']} [{key}]": key for key, value in self.maps.items()}
        self.map_labels = labels
        self.choice.configure(values=list(labels))
        if hasattr(self, "displayed_map"):
            self.displayed_map.set(next(label for label, key in labels.items() if key == self.selected.get()))

    def select_map(self, event=None):
        self.selected.set(self.map_labels[self.displayed_map.get()])
        self.draw()

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
        icons = {"tree": "♣", "rock": "◆", "house": "⌂", "flowers": "✿", "grass": "⁙", "crystal": "✦", "camp": "▲"}
        for decoration in data.get("decorations", []):
            self.label(decoration["position"], icons.get(decoration["kind"], "?"), "#e4dfb8")
        for position in data.get("spawns", []):
            self.label(position, "G", "#ff7777")
        for exit in data.get("exits", []):
            self.label(exit["position"], "↗", "#80e9ff")
        for site in data.get("sites", []):
            self.label(site["position"], "P" if site.get("owner") else "N", "#ffe080")

    def label(self, point, text, color):
        self.canvas.create_text((point[0] + .5) * self.size, (point[1] + .5) * self.size, text=text, fill=color, font=("Arial", max(10, self.size // 2), "bold"))

    def drag(self, event):
        if self.tool.get() not in ("Téléportation", "PNJ", "Inspecter", "Spawn gobelin"):
            self.click(event, record=False)

    def click(self, event, record=True):
        point = self.coordinates(event)
        data = self.maps[self.selected.get()]
        if not 0 <= point[0] < data["width"] or not 0 <= point[1] < data["height"]:
            return
        tool = self.tool.get()
        if tool == "Inspecter":
            objects = [item for field in ("sites", "exits", "decorations") for item in data.get(field, []) if item["position"] == point]
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
        elif tool == "Spawn gobelin":
            if point not in data.get("spawns", []):
                data.setdefault("spawns", []).append(point)
        else:
            for field in ("cover", "water", "bridges", "blocked", "paths"):
                data[field] = [p for p in data.get(field, []) if p != point]
            data["decorations"] = [item for item in data.get("decorations", []) if item["position"] != point]
            if tool == "Effacer":
                for field in ("sites", "exits"):
                    data[field] = [item for item in data.get(field, []) if item["position"] != point]
                data["spawns"] = [p for p in data.get("spawns", []) if p != point]
            elif tool == "Eau":
                data["water"].append(point)
                data["blocked"].append(point)
            elif tool == "Pont":
                data["water"].append(point)
                data["bridges"].append(point)
            elif tool == "Chemin":
                data["paths"].append(point)
            elif tool != "Sol":
                kinds = {"Arbre": "tree", "Rocher": "rock", "Maison": "house", "Fleurs": "flowers", "Herbe": "grass", "Cristal": "crystal", "Camp": "camp"}
                data["decorations"].append({"position": point, "kind": kinds[tool]})
                if tool in ("Arbre", "Rocher", "Maison"):
                    data["cover"].append(point)
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
            labels = {"name": "Nom affiché", "width": "Largeur (cases)", "height": "Hauteur (cases)", "biome": "Ambiance", "destination": "Carte destination (vide = sortie complète)", "entry": "Case d’arrivée x,y", "fast_destination": "Provenance du chemin rapide", "bidirectional": "Créer aussi le passage de retour", "id": "Identifiant PNJ", "dialogue": "Dialogue", "owner": "Joueur lié (leader ou ID, vide = fixe)"}
            ttk.Label(window, text=labels.get(key, key)).grid(row=row, column=0, padx=8, pady=5)
            if key == "bidirectional":
                variable = tk.BooleanVar(value=bool(value))
                ttk.Checkbutton(window, variable=variable).grid(row=row, column=1, sticky="w", padx=8)
                entries[key] = variable
                continue
            entry = ttk.Combobox(window, values=["", *self.maps], width=48) if key in ("destination", "fast_destination") else ttk.Combobox(window, values=["forest", "village", "cave"], width=48) if key == "biome" else ttk.Entry(window, width=50)
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
        self.maps[key].update(biome="forest", decorations=[], water=[], bridges=[], blocked=[], paths=[])
        self.selected.set(key)
        self.refresh_choice()
        self.draw()

    def properties(self):
        data = self.maps[self.selected.get()]
        result = self.form("Carte", {key: data.get(key, "forest") for key in ("name", "width", "height", "biome")})
        if result:
            try:
                result.update(width=int(result["width"]), height=int(result["height"]))
                if not 4 <= result["width"] <= 128 or not 4 <= result["height"] <= 128:
                    raise ValueError()
                if not result["name"].strip():
                    raise ValueError()
                self.remember()
                result["name"] = result["name"].strip()
                data.update(result)
                self.refresh_choice()
                self.draw()
            except ValueError:
                messagebox.showerror("Carte", "Dimensions : 4 à 128 cases.")

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
