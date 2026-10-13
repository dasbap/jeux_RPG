import argparse
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from .content import CONDITIONS
from .controller_editors import ControllerEditorsMixin
from .controller_fields import RANKS
from .controller_fields import parse_field as parse_field
from .controller_gameplay import FIXED as GAMEPLAY_FIXED
from .controller_gameplay import SECTIONS as GAMEPLAY_SECTIONS
from .controller_gameplay import ControllerGameplayMixin
from .controller_project import Project
from .map_building import zone_of
from .mob_rules import drop_rules, resolve
from .mob_rules import validate_mobs as validate_mobs


class Controller(ControllerGameplayMixin, ControllerEditorsMixin):
    def __init__(self, root, project):
        import tkinter as tk
        from tkinter import messagebox, simpledialog, ttk

        self.tk, self.ttk, self.messagebox, self.simpledialog = (
            tk,
            ttk,
            messagebox,
            simpledialog,
        )
        self.root, self.project = root, project
        self.history = []
        self.future = []
        self.filters = {}
        root.title("RPG — Contrôleur du projet")
        root.geometry("1120x780")
        root.protocol("WM_DELETE_WINDOW", self.close)
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        for name, action in [
            ("Builder", self.builder),
            ("Projet complet (JSON)", self.edit_project_document),
            ("Valider", self.validate),
            ("Enregistrer le projet", self.save),
            ("Annuler modification", self.undo),
            ("Rétablir", self.redo),
        ]:
            ttk.Button(bar, text=name, command=action).pack(side="left", padx=4)
        self.status = tk.StringVar(
            value=f"{project.directory} · Modifiez puis enregistrez. Redémarrez le serveur pour appliquer."
        )
        ttk.Label(root, textvariable=self.status, wraplength=1080).pack(
            fill="x", padx=8
        )
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self.tables = {}
        for section, title in [
            ("maps", "Cartes / zones"),
            ("quests", "Quêtes"),
            ("mobs", "Mobs"),
            ("achievements", "Succès et titres"),
            ("endgame", "Contrats"),
            ("economy", "Économie"),
            ("npcs", "PNJ"),
            ("world", "Monde"),
            ("classes", "Classes / modèles"),
            ("skills", "Compétences simples"),
            ("skill_models", "Compétences moteur"),
        ] + GAMEPLAY_SECTIONS:
            page = ttk.Frame(notebook, padding=8)
            notebook.add(page, text=title)
            search = ttk.Frame(page)
            search.pack(fill="x", pady=(0, 8))
            ttk.Label(search, text="Rechercher").pack(side="left")
            self.filters[section] = tk.StringVar()
            ttk.Entry(search, textvariable=self.filters[section]).pack(
                side="left", fill="x", expand=True, padx=8
            )
            self.filters[section].trace_add(
                "write", lambda *args, s=section: self.refresh(s)
            )
            table_frame = ttk.Frame(page)
            table_frame.pack(fill="both", expand=True)
            table = ttk.Treeview(
                table_frame,
                columns=("name", "details"),
                show="tree headings",
                selectmode="browse",
            )
            table.heading("#0", text="Identifiant")
            table.heading("name", text="Nom")
            table.heading("details", text="Détails")
            table.column("#0", width=190)
            table.column("name", width=240)
            table.column("details", width=540)
            table.pack(side="left", fill="both", expand=True)
            scrollbar = ttk.Scrollbar(
                table_frame, orient="vertical", command=table.yview
            )
            scrollbar.pack(side="left", fill="y")
            table.configure(yscrollcommand=scrollbar.set)
            table.bind("<Double-1>", lambda e, s=section: self.edit(s))
            self.tables[section] = table
            actions = ttk.Frame(page)
            actions.pack(fill="x", pady=8)
            for label, action in [("Modifier", lambda s=section: self.edit(s))] + (
                []
                if section in {"world", *GAMEPLAY_FIXED}
                else [
                    ("Ajouter", lambda s=section: self.edit(s, True)),
                    ("Supprimer", lambda s=section: self.delete(s)),
                ]
            ):
                ttk.Button(actions, text=label, command=action).pack(
                    side="left", padx=4
                )
            ttk.Button(
                actions,
                text="Aperçu / références",
                command=lambda s=section: self.inspect(s),
            ).pack(side="left", padx=4)
            if (
                section not in ("world", "maps", "npcs", "economy")
                and section not in GAMEPLAY_FIXED
            ):
                ttk.Button(
                    actions,
                    text="Dupliquer",
                    command=lambda s=section: self.duplicate(s),
                ).pack(side="left", padx=4)
            if section not in ("world", "economy") and section not in dict(
                GAMEPLAY_SECTIONS
            ):
                ttk.Button(
                    actions,
                    text="Renommer identifiant",
                    command=lambda s=section: self.rename(s),
                ).pack(side="left", padx=4)
            if section == "mobs":
                ttk.Button(
                    actions, text="Créer une sous-espèce", command=self.subspecies
                ).pack(side="left", padx=4)
            if section == "maps":
                ttk.Button(
                    actions,
                    text="Éditer la carte dans le builder",
                    command=self.builder,
                ).pack(side="left")
            if section == "world":
                ttk.Label(
                    page,
                    text="Trajets, rues, raccords et placements : bouton Builder → Assemblage / Trajets et rues.\nLe temps, les déplacements et la régénération se règlent dans Règles du jeu.",
                ).pack(anchor="w")
        navigation = ttk.Frame(root, padding=8)
        navigation.pack(fill="x", before=notebook)
        ttk.Label(navigation, text="Catalogue").pack(side="left")
        titles = [notebook.tab(tab, "text") for tab in notebook.tabs()]
        chooser = ttk.Combobox(navigation, values=titles, state="readonly", width=48)
        chooser.pack(side="left", padx=8)
        chooser.current(0)
        chooser.bind(
            "<<ComboboxSelected>>", lambda event: notebook.select(chooser.current())
        )
        notebook.bind(
            "<<NotebookTabChanged>>",
            lambda event: chooser.current(notebook.index(notebook.select())),
        )
        self.refresh()

    def remember(self, state=None):
        self.future = []
        self.history.append(self.project.state() if state is None else state)
        self.history = self.history[-30:]

    def undo(self):
        if self.history:
            self.future.append(self.project.state())
            (
                self.project.maps,
                self.project.mobs,
                self.project.content,
                self.project.encounters,
            ) = self.history.pop()
            self.refresh()

    def redo(self):
        if self.future:
            self.history.append(self.project.state())
            (
                self.project.maps,
                self.project.mobs,
                self.project.content,
                self.project.encounters,
            ) = self.future.pop()
            self.refresh()

    def inspect(self, section):
        if section in dict(GAMEPLAY_SECTIONS):
            self.inspect_gameplay(section)
            return
        from .controller_tools import preview, references

        selected = self.tables[section].selection()
        if not selected:
            return
        level = player_level = 1
        if section in ("mobs", "classes"):
            level = self.simpledialog.askinteger(
                "Aperçu",
                "Niveau à simuler (1–100)",
                initialvalue=1,
                minvalue=1,
                maxvalue=100,
                parent=self.root,
            )
            if level is None:
                return
        if section == "mobs":
            player_level = self.simpledialog.askinteger(
                "Récompense XP",
                "Niveau du joueur (1–100)",
                initialvalue=level,
                minvalue=1,
                maxvalue=100,
                parent=self.root,
            )
            if player_level is None:
                return
        try:
            self.show_report(
                "Aperçu et références",
                {
                    "aperçu": preview(
                        self.project, section, selected[0], level, player_level
                    ),
                    "utilisé_par": references(self.project, section, selected[0]),
                },
            )
        except (ValueError, KeyError, TypeError) as exc:
            self.messagebox.showerror("Aperçu", str(exc), parent=self.root)

    def show_report(self, title, value):
        from .controller_tools import text

        window = self.tk.Toplevel(self.root)
        window.title(title)
        window.geometry("900x650")
        frame = self.ttk.Frame(window)
        frame.pack(fill="both", expand=True)
        area = self.tk.Text(frame, wrap="word")
        scrollbar = self.ttk.Scrollbar(frame, orient="vertical", command=area.yview)
        area.configure(yscrollcommand=scrollbar.set)
        area.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        area.insert("1.0", text(value))
        area.configure(state="disabled")
        self.ttk.Button(window, text="Fermer", command=window.destroy).pack(pady=8)
        window.transient(self.root)

    def edit_project_document(self):
        window = self.tk.Toplevel(self.root)
        window.title("Projet complet — JSON")
        window.geometry("1100x760")
        frame = self.ttk.Frame(window, padding=8)
        frame.pack(fill="both", expand=True)
        area = self.tk.Text(frame, wrap="none", undo=True)
        yscroll = self.ttk.Scrollbar(frame, orient="vertical", command=area.yview)
        xscroll = self.ttk.Scrollbar(frame, orient="horizontal", command=area.xview)
        area.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        area.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        area.insert(
            "1.0", json.dumps(self.project.document(), ensure_ascii=False, indent=2)
        )
        actions = self.ttk.Frame(window, padding=8)
        actions.pack(fill="x")

        def apply():
            before = self.project.state()
            try:
                value = json.loads(area.get("1.0", "end-1c"))
                self.project.replace_document(value)
                self.remember(before)
                self.refresh()
                self.status.set(
                    "Projet complet validé en mémoire. Enregistrez pour le conserver."
                )
                window.destroy()
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self.messagebox.showerror("Projet complet", str(exc), parent=window)

        self.ttk.Button(actions, text="Appliquer et valider", command=apply).pack(
            side="left", padx=4
        )
        self.ttk.Button(actions, text="Annuler", command=window.destroy).pack(
            side="left", padx=4
        )
        window.transient(self.root)

    def duplicate(self, section):
        if section in dict(GAMEPLAY_SECTIONS):
            self.duplicate_gameplay(section)
            return
        selected = self.tables[section].selection()
        if not selected:
            return
        identifier = self.simpledialog.askstring(
            "Dupliquer", "Identifiant de la copie", parent=self.root
        )
        if not identifier:
            return
        before = self.project.state()
        try:
            self.project.duplicate(section, selected[0], identifier)
            self.remember(before)
            self.filters[section].set("")
            self.refresh()
            self.tables[section].selection_set(
                "ability:" + identifier if section == "skill_models" else identifier
            )
            self.status.set("Copie indépendante créée. Enregistrez pour la conserver.")
        except (ValueError, KeyError, TypeError) as exc:
            self.messagebox.showerror("Duplication", str(exc), parent=self.root)

    def refresh(self, only=None):
        p = self.project
        from .controller_tools import catalog_rows, filter_rows

        for section, table in self.tables.items():
            if only is not None and section != only:
                continue
            selected = table.selection()
            query = self.filters[section].get() if hasattr(self, "filters") else ""
            table.delete(*table.get_children())
            for key, name, details in filter_rows(catalog_rows(p, section), query):
                table.insert("", "end", iid=key, text=key, values=(name, details))
            for key in selected:
                if table.exists(key):
                    table.selection_set(key)

    def label(self, key):
        from .controller_gameplay import FIELD_LABELS

        if key in FIELD_LABELS:
            return FIELD_LABELS[key]
        if key.endswith("_base"):
            return key[:-5] + " · valeur au niveau 1"
        if key.endswith("_growth") and key != "damage_growth":
            return key[:-7] + " · croissance par niveau"
        return {
            "id": "Identifiant",
            "name": "Nom",
            "category": "Type de quête (main / side / tutorial)",
            "npc": "PNJ donneur",
            "kind": "Type d’objectif",
            "target": "Espèce / recette cible",
            "zone": "Zone requise (vide = toutes)",
            "count": "Nombre requis",
            "reward_xp": "Récompense XP par joueur",
            "description": "Description",
            "condition": "Condition",
            "threshold": "Seuil",
            "title": "Titre obtenu",
            "class_name": "Classe de base",
            "rank": "Rang",
            "damage": "Dégâts",
            "dialogue": "Dialogue",
            "owner": "Joueur lié (vide = fixe)",
            "map_id": "Carte",
            "width": "Largeur",
            "height": "Hauteur",
            "zone_level": "Niveau de zone",
            "biome": "Ambiance",
            "repop_seconds": "Repop après absence (secondes en jeu)",
            "mob_xp": "XP par mob",
            "xp_base": "Base XP nécessaire",
            "xp_exponent": "Exposant de progression XP",
            "merchant_stay_hours": "Séjour du marchand (heures en jeu)",
            "player_vision": "Vision joueur (cases)",
            "guild_max_members": "Capacité maximale d’une guilde",
            "starting_gold": "Or initial",
            "trade_max_quantity": "Quantité max par échange",
            "trade_max_gold": "Or max par échange",
            "xp_class": "Classe de récompense XP",
            "xp_multiplier": "Multiplicateur XP",
            "damage_growth": "Dégâts ajoutés par niveau",
            "parent": "Espèce parente",
            "item": "Matériau",
            "chance": "Probabilité (0–1)",
            "attempts": "Nombre de tirages indépendants",
            "min": "Quantité minimale par réussite",
            "max": "Quantité maximale par réussite",
            "rare": "Matériau rare",
            "power": "Puissance de base",
            "growth": "Puissance par niveau",
            "cooldown": "Cooldown (secondes réelles)",
            "cast": "Incantation (secondes réelles)",
            "range": "Portée (cases)",
            "duration": "Durée du stun (secondes réelles)",
            "hp_multiplier": "Multiplicateur PV de phase",
            "damage_multiplier": "Multiplicateur dégâts de phase",
            "level": "Niveau de déblocage",
            "concentration": "Interrompue par les dégâts",
            "type": "Effet",
            "base_class": "Modèle de classe humaine",
            "energy_capacity": "Capacité des énergies ajoutées",
            "skill_id": "Compétence existante",
            "cost": "Coût d’énergie",
            "buy": "Prix d’achat au marchand",
            "sell": "Prix de vente au marchand",
            "merchant": "Marchand",
            "min_level": "Niveau minimum",
            "repeatable": "Répétable",
            "pvp_enabled": "Activer le PvP optionnel",
        }.get(key, key)

    def form(self, title, values, choices=None):
        dialog = self.tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry(
            f"{min(850, dialog.winfo_screenwidth() - 80)}x{min(650, dialog.winfo_screenheight() - 100)}"
        )
        frame = self.ttk.Frame(dialog)
        frame.pack(fill="both", expand=True)
        canvas = self.tk.Canvas(frame, highlightthickness=0)
        scrollbar = self.ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        window = self.ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=window, anchor="nw")
        window.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(content_window, width=event.width),
        )
        dialog.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )
        fields = {}
        labels = {}
        choices = choices or {}
        for row, (key, value) in enumerate(values.items()):
            labels[key] = self.ttk.Label(
                window,
                text=(
                    self.label(key) + " (−1 : automatique)"
                    if title in ("Compétences universelles", "Compétence moteur")
                    and key in ("range", "cost")
                    else self.label(key)
                ),
            )
            labels[key].grid(row=row, column=0, padx=8, pady=5, sticky="w")
            if type(value) is bool:
                choices[key] = ["Oui", "Non"]
            widget = (
                self.ttk.Combobox(
                    window, values=choices[key], state="readonly", width=55
                )
                if key in choices
                else self.ttk.Entry(window, width=58)
            )
            if key in choices:
                widget.set(
                    "Oui" if value is True else "Non" if value is False else value
                )
            else:
                widget.insert(0, str(value))
            widget.grid(row=row, column=1, padx=8, pady=5)
            fields[key] = widget

        def condition_changed(event=None):
            condition = fields["condition"].get()
            if "target" in fields:
                RECIPES = self.project.content["gameplay"]["recipes"]
                targets = [""] + (
                    list(RECIPES)
                    if condition == "craft"
                    else [item["id"] for item in self.project.content["quests"]]
                    if condition == "quests"
                    else list(self.project.mobs)
                )
                fields["target"].configure(values=targets)
                if fields["target"].get() not in targets or condition in (
                    "level",
                    "discover",
                ):
                    fields["target"].set("")
                for widget in (labels["target"], fields["target"]):
                    widget.grid_remove() if condition in (
                        "level",
                        "discover",
                    ) else widget.grid()
                for key in ("zone", "map"):
                    for widget in (labels[key], fields[key]):
                        widget.grid_remove() if condition == "level" else widget.grid()
                    if condition == "level":
                        fields[key].set("")
            labels["threshold"].configure(
                text="Temps maximum (secondes réelles)"
                if condition == "fast"
                else "Différence de niveau minimale"
                if condition == "higher"
                else "Niveau requis"
                if condition == "level"
                else "Nombre requis"
            )

        if "condition" in fields and "threshold" in fields:
            fields["condition"].bind("<<ComboboxSelected>>", condition_changed)
            condition_changed()

        def kind_changed(event=None):
            RECIPES = self.project.content["gameplay"]["recipes"]
            targets = (
                list(self.project.mobs)
                if fields["kind"].get() == "kill"
                else list(RECIPES)
            )
            fields["target"].configure(values=targets)
            if fields["target"].get() not in targets:
                fields["target"].set(targets[0] if targets else "")

        if "kind" in fields and "target" in fields:
            fields["kind"].bind("<<ComboboxSelected>>", kind_changed)
            kind_changed()
        result = []

        def accept():
            try:
                parsed = {
                    key: parse_field(key, widget.get(), values[key])
                    for key, widget in fields.items()
                }
                if "condition" in parsed and parsed["condition"] != "fast":
                    if parsed["threshold"] != int(parsed["threshold"]):
                        raise ValueError("Seuil entier requis.")
                    parsed["threshold"] = int(parsed["threshold"])
                result.append(parsed)
                dialog.destroy()
            except ValueError:
                self.messagebox.showerror(
                    "Valeur",
                    "Les champs numériques doivent contenir un nombre.",
                    parent=dialog,
                )

        actions = self.ttk.Frame(dialog, padding=8)
        actions.pack(fill="x")
        self.ttk.Button(actions, text="Appliquer", command=accept).pack(
            side="left", padx=4
        )
        self.ttk.Button(actions, text="Annuler", command=dialog.destroy).pack(
            side="left", padx=4
        )
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.wait_window(dialog)
        return result[0] if result else None

    def edit(self, section, new=False):
        if section in dict(GAMEPLAY_SECTIONS):
            self.edit_gameplay(section, new)
            return
        selected = self.tables[section].selection()
        if not new and not selected:
            return
        key = selected[0] if selected else None
        p = self.project
        before = p.state()
        try:
            if section == "maps":
                self.builder(new=new)
                return
            handlers = {
                "world": self._edit_world,
                "skill_models": self._edit_skill_model,
                "classes": self._edit_class_or_skill,
                "skills": self._edit_class_or_skill,
                "mobs": self._edit_mob,
                "endgame": self._edit_contract,
                "economy": self._edit_economy,
                "quests": self._edit_quest_or_achievement,
                "achievements": self._edit_quest_or_achievement,
            }
            handler = handlers.get(section, self._edit_npc)
            if section == "classes" and (
                new
                or any(item["id"] == key for item in p.content["templates"]["classes"])
            ):
                handler = self._edit_class_model
            if not handler(key, new, section):
                return
            p.validate()
            if p.state() != before:
                self.remember(before)
                self.status.set(
                    "Modification appliquée en mémoire. Enregistrez le projet pour la conserver."
                )
            self.refresh()
        except (ValueError, KeyError, TypeError) as exc:
            p.restore(before)
            self.messagebox.showerror(
                "Modification refusée", str(exc), parent=self.root
            )

    def _edit_world(self, key, new, section):
        p = self.project
        values = self.form("Paramètres du monde", p.content["world"])
        if values:
            p.content["world"] = values
        return True

    def _edit_skill_model(self, key, new, section):
        p = self.project
        values = self.edit_skill_model(key, new)
        if values is None:
            return
        identifier = values.pop("id")
        if new and identifier in p.content["templates"]["skills"]:
            raise ValueError("Identifiant déjà utilisé.")
        if not new and identifier != key:
            raise ValueError("Utilisez Renommer identifiant pour changer la référence.")
        p.content["templates"]["skills"][identifier] = values
        return True

    def _edit_class_model(self, key, new, section):
        p = self.project
        values = self.edit_template(key, new)
        if values is None:
            return
        if new and any(
            item["id"].lower() == values["id"].lower()
            for item in p.content["templates"]["classes"]
        ):
            raise ValueError("Identifiant déjà utilisé.")
        if not new and values["id"] != key:
            p.rename("classes", key, values["id"])
        p.content["templates"]["classes"] = [
            item
            for item in p.content["templates"]["classes"]
            if item["id"] not in (key, values["id"])
        ] + [values]
        return True

    def _edit_class_or_skill(self, key, new, section):
        p = self.project
        from .skill_catalog import BASE_CLASSES, library

        available = library(p.content, p.mobs)
        if section == "classes":
            old = next(
                item for item in p.content.get("classes", []) if item["id"] == key
            )
            values = self.form(
                "Classe humaine",
                {
                    k: v
                    for k, v in old.items()
                    if k not in ("stats", "skills", "previous_ids")
                },
                {"base_class": BASE_CLASSES},
            )
            if not values:
                return
            stats = self.edit_stats(
                {
                    "class_name": values["base_class"],
                    "name": values["name"],
                    "stats": old.get("stats", {}),
                }
            )
            if stats is None:
                return
            assigned = self.edit_records(
                "Compétences de classe",
                old.get("skills", []),
                {
                    "skill_id": next(iter(available)),
                    "level": 1,
                    "range": 6.0,
                    "cost": 5,
                },
                {"skill_id": list(available)},
            )
            if assigned is None:
                return
            values.update(stats=stats, skills=assigned)
        else:
            old = (
                {
                    "id": "",
                    "name": "Nouvelle compétence",
                    "type": "damage",
                    "level": 1,
                    "power": 3.0,
                    "growth": 0.5,
                    "cooldown": 5.0,
                    "cast": 0.6,
                    "range": 1.5,
                    "duration": 2.0,
                    "concentration": True,
                }
                if new
                else next(
                    item for item in p.content.get("skills", []) if item["id"] == key
                )
            )
            values = self.form(
                "Compétence réutilisable",
                old,
                {"type": ["damage", "heal", "stun"]},
            )
            if not values:
                return
        if new and any(
            item["id"].lower() == values["id"].lower()
            for item in p.content["templates"]["classes"]
        ):
            raise ValueError("Identifiant déjà utilisé.")
        if not new and values["id"] != key:
            p.rename(section, key, values["id"])
        elif new and any(
            item["id"] == values["id"] for item in p.content.get(section, [])
        ):
            raise ValueError("Identifiant déjà utilisé.")
        if section == "classes" and not new:
            current = next(
                item for item in p.content[section] if item["id"] == values["id"]
            )
            if current.get("previous_ids"):
                values["previous_ids"] = current["previous_ids"]
        p.content[section] = [
            item for item in p.content.get(section, []) if item["id"] != values["id"]
        ] + [values]
        return True

    def _edit_mob(self, key, new, section):
        p = self.project
        from .gameplay_catalog import rare_drops

        old = (
            resolve(p.mobs, key)
            if not new
            else {
                "name": "Nouvelle créature",
                "class_name": next(
                    item["id"]
                    for item in p.content["templates"]["classes"]
                    if not item["playable"] and item["class_type"] != "INVOCATION"
                ),
                "rank": "D",
                "damage": 3,
                "loot": {"peau": 1},
            }
        )
        public = {
            "id": key or "",
            "name": old["name"],
            "class_name": old["class_name"],
            "rank": old["rank"],
            "damage": old["damage"],
            "damage_growth": float(old.get("damage_growth", 0.5)),
            "xp_class": old.get("xp_class", "normal"),
            "xp_multiplier": float(old.get("xp_multiplier", 1)),
            "parent": p.mobs[key].get("parent", "") if not new else "",
        }
        values = self.form(
            "Espèce / sous-espèce",
            public,
            {
                "class_name": [
                    item["id"]
                    for item in p.content["templates"]["classes"]
                    if item["class_type"] != "INVOCATION"
                ],
                "rank": RANKS,
                "xp_class": list(p.content["gameplay"]["xp_classes"]),
                "parent": ["", *p.mobs],
            },
        )
        if not values:
            return
        stats = self.edit_stats(old)
        if stats is None:
            return
        drops = self.edit_records(
            "Drops",
            drop_rules(old, rare_drops(p.content["gameplay"])),
            {
                "item": "peau",
                "chance": 1.0,
                "attempts": 1,
                "min": 1,
                "max": 1,
                "rare": False,
            },
        )
        if drops is None:
            return
        abilities = self.edit_records(
            "Capacités",
            old.get("abilities", []),
            {
                "name": "Frappe",
                "type": "damage",
                "level": 1,
                "power": 3.0,
                "growth": 0.5,
                "cooldown": 5.0,
                "cast": 0.6,
                "range": 1.5,
                "duration": 2.0,
                "concentration": True,
            },
            {"type": ["damage", "heal", "stun"]},
        )
        if abilities is None:
            return
        phases = self.edit_records(
            "Phases de boss",
            old.get("phases", []),
            {
                "name": "Phase 2",
                "hp_multiplier": 1.0,
                "damage_multiplier": 1.25,
            },
        )
        if phases is None:
            return
        identifier = values.pop("id")
        if identifier != key and identifier in p.mobs:
            raise ValueError("Identifiant déjà utilisé.")
        if not new and identifier != key:
            p.rename("mobs", key, identifier)
        if not values["parent"]:
            values.pop("parent")
        history = p.mobs.get(identifier, {}).get("previous_ids", []) if not new else []
        p.mobs[identifier] = {
            **({"previous_ids": history} if history else {}),
            **values,
            "stats": stats,
            "drops": drops,
            "loot": {},
            "abilities": abilities,
            "phases": phases,
        }
        return True

    def _edit_contract(self, key, new, section):
        p = self.project
        default = {
            "id": "",
            "name": "Nouveau contrat",
            "kind": "kill",
            "target": "goblin",
            "zone": "",
            "count": 10,
            "min_level": 5,
            "reward_xp": 500,
            "repeatable": True,
        }
        old = (
            default
            if new
            else next(item for item in p.content["endgame"] if item["id"] == key)
        )
        RECIPES = p.content["gameplay"]["recipes"]
        old = {field: value for field, value in old.items() if field != "previous_ids"}
        choices = {
            "kind": ["kill", "craft"],
            "target": list(p.mobs),
            "zone": ["", *p.maps],
        }
        values = self.form("Contrat endgame", old, choices)
        if values:
            targets = list(p.mobs) if values["kind"] == "kill" else list(RECIPES)
            if values["target"] not in targets:
                raise ValueError("Cible endgame incompatible avec le type.")
            if not new and values["id"] != key:
                raise ValueError(
                    "Utilisez Renommer identifiant pour changer la référence."
                )
            if new and any(item["id"] == values["id"] for item in p.content["endgame"]):
                raise ValueError("Identifiant déjà utilisé.")
            metadata = (
                next(
                    (item for item in p.content["endgame"] if item["id"] == key),
                    {},
                )
                if not new
                else {}
            )
            if metadata.get("previous_ids"):
                values["previous_ids"] = metadata["previous_ids"]
            p.content["endgame"] = [
                item for item in p.content["endgame"] if item["id"] != values["id"]
            ] + [values]
        return True

    def _edit_economy(self, key, new, section):
        p = self.project
        old = (
            {"id": "", "name": "Nouveau matériau", "buy": 10, "sell": 5}
            if new
            else next(item for item in p.content["economy"] if item["id"] == key)
        )
        values = self.form("Prix économique", old)
        if not values:
            return
        if values["sell"] > values["buy"]:
            raise ValueError(
                "Le prix de vente joueur ne peut pas dépasser le prix d’achat."
            )
        if not new and values["id"] != key:
            raise ValueError(
                "Supprimez puis recréez le matériau pour changer son identifiant."
            )
        if new and any(item["id"] == values["id"] for item in p.content["economy"]):
            raise ValueError("Identifiant déjà utilisé.")
        p.content["economy"] = [
            item for item in p.content["economy"] if item["id"] != values["id"]
        ] + [values]
        return True

    def _edit_quest_or_achievement(self, key, new, section):
        p = self.project
        default = (
            {
                "id": "",
                "name": "Nouvelle quête",
                "category": "side",
                "npc": "mira",
                "kind": "kill",
                "target": "goblin",
                "zone": "",
                "map": "",
                "count": 1,
                "reward_xp": 50,
                "description": "Objectif de quête",
            }
            if section == "quests"
            else {
                "id": "",
                "name": "Nouveau succès",
                "condition": "kills",
                "threshold": 1,
                "title": "Nouveau titre",
                "target": "",
                "zone": "",
                "map": "",
            }
        )
        old = (
            default
            if new
            else next(item for item in p.content[section] if item["id"] == key)
        )
        choices = {
            "category": ["main", "side", "tutorial", "standard"],
            "npc": sorted(
                {site["id"] for data in p.maps.values() for site in data["sites"]}
            ),
            "kind": ["kill", "craft"],
            "target": list(p.mobs),
            "zone": ["", *p.maps],
            "condition": CONDITIONS,
        }
        if section == "achievements":
            old = {"target": "", "zone": "", "map": "", **old}
        else:
            old = {"category": "side", "map": "", **old}
        choices["zone"] = (
            ["", *p.maps]
            if section == "quests"
            else [
                "",
                *sorted({zone_of(p.maps, identifier) for identifier in p.maps}),
            ]
        )
        choices["map"] = ["", *p.maps]
        values = self.form(
            "Quête" if section == "quests" else "Succès et titre",
            {
                k: v
                for k, v in old.items()
                if k not in ("role", "previous_ids", "requirements")
            },
            choices,
        )
        if values:
            if section == "quests":
                requirements = self.edit_requirements(old.get("requirements", {}))
                if requirements is None:
                    return
                values["requirements"] = requirements
            if not new and values["id"] != key:
                p.rename(section, key, values["id"])
            metadata = (
                next(
                    (item for item in p.content[section] if item["id"] == values["id"]),
                    {},
                )
                if not new
                else {}
            )
            values.update(
                {k: v for k, v in metadata.items() if k in ("role", "previous_ids")}
            )
            p.content[section] = [
                item
                for item in p.content[section]
                if item["id"] != (values["id"] if not new else None)
            ] + [values]
        return True

    def _edit_npc(self, key, new, section):
        p = self.project
        map_id, index = key.rsplit(":", 1) if key else (next(iter(p.maps)), None)
        old = (
            {
                "id": "",
                "name": "Nouveau PNJ",
                "dialogue": "Bonjour !",
                "owner": "",
                "merchant": False,
            }
            if new
            else {
                k: v
                for k, v in p.maps[map_id]["sites"][int(index)].items()
                if k != "position"
            }
        )
        values = self.form("PNJ", {"map_id": map_id, **old}, {"map_id": list(p.maps)})
        if not values:
            return
        from .map_objects import pick_cell

        destination = values.pop("map_id")
        chosen = pick_cell(
            SimpleNamespace(
                root=self.root,
                maps=p.maps,
                selected=SimpleNamespace(get=lambda: destination),
            ),
            "Placer le PNJ",
            destination,
        )
        if not chosen:
            return
        if not new:
            previous_id = p.maps[map_id]["sites"][int(index)]["id"]
            if values["id"] != previous_id:
                p.rename("npcs", previous_id, values["id"])
            p.maps[map_id]["sites"].pop(int(index))
        p.maps[destination]["sites"].append({**values, "position": chosen[1]})
        return True

    def rename(self, section):
        selected = self.tables[section].selection()
        if not selected:
            return
        key = selected[0]
        if section == "npcs":
            map_id, index = key.rsplit(":", 1)
            key = self.project.maps[map_id]["sites"][int(index)]["id"]
        replacement = self.simpledialog.askstring(
            "Renommer identifiant",
            "Nouvel identifiant (ex. mira_hunt_2)",
            initialvalue=key,
            parent=self.root,
        )
        if not replacement or replacement == key:
            return
        before = self.project.state()
        try:
            self.project.rename(section, key, replacement)
            self.remember(before)
            self.refresh()
            self.status.set(
                "Identifiant renommé, références mises à jour. Enregistrez puis redémarrez le serveur."
            )
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror("Renommage refusé", str(exc), parent=self.root)

    def subspecies(self):
        selected = self.tables["mobs"].selection()
        if not selected:
            return
        parent = selected[0]
        identifier = self.simpledialog.askstring(
            "Sous-espèce", "Nouvel identifiant", parent=self.root
        )
        if not identifier:
            return
        before = self.project.state()
        try:
            if identifier in self.project.mobs:
                raise ValueError("Identifiant déjà utilisé.")
            self.project.mobs[identifier] = {
                "parent": parent,
                "name": resolve(self.project.mobs, parent)["name"] + " · sous-espèce",
            }
            self.project.validate()
            self.remember(before)
            self.refresh()
            self.tables["mobs"].selection_set(identifier)
            self.edit("mobs")
        except ValueError as exc:
            self.project.restore(before)
            self.messagebox.showerror("Sous-espèce", str(exc), parent=self.root)

    def delete(self, section):
        if section in dict(GAMEPLAY_SECTIONS):
            self.delete_gameplay(section)
            return
        selected = self.tables[section].selection()
        if not selected:
            return
        if section == "maps":
            self.builder()
            return
        key = selected[0]
        if not self.messagebox.askyesno(
            "Supprimer", "Supprimer cette définition ?", parent=self.root
        ):
            return
        before = self.project.state()
        try:
            if section == "skill_models":
                self.project.content["templates"]["skills"].pop(key)
            elif section == "classes" and any(
                item["id"] == key
                for item in self.project.content["templates"]["classes"]
            ):
                self.project.content["templates"]["classes"] = [
                    item
                    for item in self.project.content["templates"]["classes"]
                    if item["id"] != key
                ]
            elif section == "mobs":
                self.project.mobs.pop(key)
            elif section == "npcs":
                map_id, index = key.rsplit(":", 1)
                self.project.maps[map_id]["sites"].pop(int(index))
            else:
                self.project.content[section] = [
                    item for item in self.project.content[section] if item["id"] != key
                ]
            self.project.validate()
            self.remember(before)
            self.refresh()
        except (ValueError, KeyError) as exc:
            self.project.restore(before)
            self.messagebox.showerror("Suppression refusée", str(exc), parent=self.root)

    def builder(self, new=False):
        from tkinter import filedialog

        from . import map_building, map_editor

        for name, value in [
            ("tk", self.tk),
            ("ttk", self.ttk),
            ("messagebox", self.messagebox),
            ("simpledialog", self.simpledialog),
            ("filedialog", filedialog),
        ]:
            setattr(map_editor, name, value)
        from .editor_ui import EditorPanel

        window = EditorPanel(self.root, "Builder")
        window.content.pack_forget()
        previous_mobs = map_building.MOBS
        previous_editor_mobs = map_editor.MOBS
        map_building.MOBS = map_editor.MOBS = self.project.mobs
        before = self.project.state()
        try:
            editor = map_editor.MapEditor(window, self.project.directory / "world.json")
            editor.gameplay = self.project.content["gameplay"]
            editor.maps = deepcopy(self.project.maps)
            editor.saved = deepcopy(editor.maps)
            chosen = self.tables["maps"].selection()
            if chosen:
                editor.selected.set(chosen[0])
            editor.refresh_choice()
            editor.draw()

            def sync_save(choose=False):
                if choose:
                    destination = filedialog.askdirectory(
                        title="Exporter le projet complet dans un autre dossier",
                        parent=self.root,
                    )
                    if not destination:
                        return
                    if Path(destination).resolve() == self.project.directory:
                        editor.messages.showerror(
                            "Export",
                            "Choisissez un autre dossier ; Enregistrer conserve le projet courant.",
                            parent=window,
                        )
                        return
                    try:
                        exported = Project(destination)
                        exported.restore(self.project.state())
                        exported.maps = deepcopy(editor.maps)
                        exported.save()
                        editor.status.set(
                            "Copie du projet exportée. Le projet courant reste ouvert."
                        )
                    except (ValueError, OSError) as exc:
                        editor.messages.showerror("Export", str(exc), parent=window)
                    return
                old = self.project.maps
                self.project.maps = deepcopy(editor.maps)
                try:
                    self.project.save()
                    editor.saved = deepcopy(editor.maps)
                    editor.status.set(
                        "Projet enregistré. Redémarrez le serveur pour appliquer."
                    )
                except (ValueError, OSError) as exc:
                    self.project.maps = old
                    editor.messages.showerror("Projet", str(exc), parent=window)

            editor.on_save = sync_save
            window.transient(self.root)
            window.grab_set()
            if new:
                editor.new()

            def close_builder():
                if editor.maps != editor.saved:
                    answer = editor.messages.askyesnocancel(
                        "Builder",
                        "Garder les modifications dans le contrôleur ? Elles pourront être enregistrées depuis celui-ci.",
                        parent=window,
                    )
                    if answer is None:
                        return
                    if not answer:
                        editor.maps = deepcopy(editor.saved)
                window.destroy()

            window.protocol("WM_DELETE_WINDOW", close_builder)
            self.root.wait_window(window)
        finally:
            map_building.MOBS = previous_mobs
            map_editor.MOBS = previous_editor_mobs
        self.project.maps = deepcopy(editor.maps)
        if self.project.state() != before:
            self.remember(before)
        self.refresh()

    def validate(self):
        from .controller_tools import report

        try:
            result = report(self.project)
            self.show_report("Diagnostic du projet", result)
            valid = not result["erreurs"]
            self.status.set(
                "Projet valide."
                if valid
                else "Corrigez les erreurs du diagnostic avant de sauvegarder."
            )
            return valid
        except (ValueError, KeyError, TypeError) as exc:
            self.messagebox.showerror("Validation", str(exc), parent=self.root)
            return False

    def save(self):
        try:
            self.project.save()
            self.status.set(
                "Projet enregistré. Redémarrez le serveur pour appliquer. Sessions nouvelles recommandées après modification des objectifs."
            )
        except (ValueError, OSError) as exc:
            self.messagebox.showerror("Enregistrement", str(exc), parent=self.root)

    def close(self):
        if self.project.state() != self.project.snapshot:
            answer = self.messagebox.askyesnocancel(
                "Fermer",
                "Enregistrer les modifications avant de fermer ?",
                parent=self.root,
            )
            if answer is None:
                return
            if answer:
                self.save()
                if self.project.state() != self.project.snapshot:
                    return
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Contrôleur graphique du contenu RPG")
    parser.add_argument("directory", nargs="?", default="maps")
    args = parser.parse_args()
    import tkinter as tk

    root = tk.Tk()
    try:
        project = Project(args.directory)
        Controller(root, project)
    except (ValueError, OSError) as exc:
        root.destroy()
        raise SystemExit(str(exc)) from exc
    root.mainloop()


if __name__ == "__main__":
    main()
