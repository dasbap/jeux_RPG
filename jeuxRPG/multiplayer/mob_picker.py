"""Spawner catalogue filters, derived from authored species and actual abilities."""

import unicodedata

from .mob_rules import resolve


def spawner_hostility(value):
    if value == "Espèce (par défaut)":
        return None
    if type(value) is bool:
        return value
    if value not in ("Hostile", "Neutre"):
        raise ValueError("Comportement de spawner invalide.")
    return value == "Hostile"


def search_text(value):
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def race_of(mobs, identifier):
    definition = resolve(mobs, identifier)
    if definition.get("race"):
        return definition["race"]
    while mobs[identifier].get("parent"):
        identifier = mobs[identifier]["parent"]
    return mobs[identifier]["class_name"]


def profiles(mobs, data):
    from .skill_catalog import library, mob_ability

    available = library(data, mobs)
    melee_range = data["gameplay"]["rules"]["ai"]["melee_range"]
    result = []
    for identifier in mobs:
        definition = resolve(mobs, identifier)
        roles = {"melee"}  # Every mob can use the engine's basic melee attack.
        abilities = []
        for assignment in definition.get("abilities", []):
            ability = (
                mob_ability(available[assignment["skill_id"]], assignment)
                if "skill_id" in assignment
                else assignment
            )
            kind = ability.get("skill_data", {}).get("type", ability["type"])
            if (
                kind in ("damage", "stun", "DAMAGE", "DEBUFF")
                and ability["range"] > melee_range
            ):
                roles.add("ranged")
            if kind == "INVOCATION":
                roles.add("summon")
            if kind == "BUFF":
                roles.add("buff")
            if kind in ("heal", "HEAL"):
                roles.add("heal")
            abilities.append(f"{ability['name']} (niv. {ability['level']})")
        result.append(
            {
                "id": identifier,
                "name": definition["name"],
                "race": race_of(mobs, identifier),
                "roles": roles,
                "hostile": definition.get("hostile", True),
                "abilities": abilities,
                "rank": definition["rank"],
            }
        )
    return sorted(result, key=lambda row: (search_text(row["name"]), row["id"]))


def filter_profiles(rows, query="", race="", combat="", roles=(), hostility=""):
    words = search_text(query).split()
    return [
        row
        for row in rows
        if all(word in search_text(row["name"] + " " + row["id"]) for word in words)
        and (not race or row["race"] == race)
        and (not combat or combat in row["roles"])
        and set(roles) <= row["roles"]
        and (not hostility or row["hostile"] == (hostility == "hostile"))
    ]


class MobPicker:
    """A read-only, searchable species table embedded in the spawner form."""

    def __init__(self, parent, mobs, data, selected=""):
        import tkinter as tk
        from tkinter import ttk

        self.rows = profiles(mobs, data)
        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(1, weight=1)
        self.query, self.race, self.combat, self.hostility = (
            tk.StringVar(master=self.frame) for _ in range(4)
        )
        self.combat.set("Tous")
        self.hostility.set("Tous")
        self.race.set("Toutes")
        self.roles = {
            key: tk.BooleanVar(master=self.frame) for key in ("summon", "buff", "heal")
        }
        self.details = tk.StringVar(master=self.frame)
        self.count = tk.StringVar(master=self.frame)
        ttk.Label(self.frame, text="Nom ou identifiant").grid(
            row=0, column=0, sticky="w"
        )
        self.search = ttk.Entry(self.frame, textvariable=self.query)
        self.search.grid(row=0, column=1, columnspan=3, sticky="ew", padx=4, pady=3)
        ttk.Label(self.frame, text="Race").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            self.frame,
            textvariable=self.race,
            values=["Toutes", *sorted({row["race"] for row in self.rows})],
            state="readonly",
            width=20,
        ).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(self.frame, text="Attaques").grid(row=1, column=2)
        ttk.Combobox(
            self.frame,
            textvariable=self.combat,
            values=["Tous", "Corps à corps", "À distance"],
            state="readonly",
            width=17,
        ).grid(row=1, column=3)
        options = ttk.Frame(self.frame)
        options.grid(row=2, column=0, columnspan=4, sticky="w", pady=4)
        for key, label in (
            ("summon", "Invocation"),
            ("buff", "Buffs"),
            ("heal", "Soins"),
        ):
            ttk.Checkbutton(options, text=label, variable=self.roles[key]).pack(
                side="left", padx=3
            )
        ttk.Label(options, text="Comportement").pack(side="left", padx=4)
        ttk.Combobox(
            options,
            textvariable=self.hostility,
            values=["Tous", "Hostiles", "Neutres"],
            state="readonly",
            width=10,
        ).pack(side="left")
        ttk.Button(
            self.frame, text="Réinitialiser les filtres", command=self.reset
        ).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(self.frame, textvariable=self.count).grid(
            row=3, column=2, columnspan=2
        )
        table_frame = ttk.Frame(self.frame)
        table_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=4)
        self.table = ttk.Treeview(
            table_frame,
            columns=("race", "roles", "hostile"),
            selectmode="browse",
            height=7,
        )
        for key, label, size in (
            ("#0", "Nom", 180),
            ("race", "Race", 105),
            ("roles", "Capacités", 180),
            ("hostile", "Par défaut", 80),
        ):
            self.table.heading(key, text=label)
            self.table.column(key, width=size, minwidth=65, stretch=True)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Label(
            self.frame, textvariable=self.details, wraplength=560, justify="left"
        ).grid(row=5, column=0, columnspan=4, sticky="w")
        ttk.Label(
            self.frame,
            text="Capacités attribuées, tous niveaux. Les filtres se combinent.",
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=3)
        self.table.bind("<<TreeviewSelect>>", lambda event: self.describe())
        for variable in (
            self.query,
            self.race,
            self.combat,
            self.hostility,
            *self.roles.values(),
        ):
            variable.trace_add("write", lambda *args: self.refresh())
        self.refresh(selected)

    def get(self):
        selection = self.table.selection()
        return selection[0] if selection else ""

    def reset(self):
        self.query.set("")
        self.race.set("Toutes")
        self.combat.set("Tous")
        self.hostility.set("Tous")
        for variable in self.roles.values():
            variable.set(False)

    def refresh(self, selected=None):
        selected = selected or self.get()
        rows = filter_profiles(
            self.rows,
            self.query.get(),
            "" if self.race.get() == "Toutes" else self.race.get(),
            {"Corps à corps": "melee", "À distance": "ranged"}.get(
                self.combat.get(), ""
            ),
            [key for key, value in self.roles.items() if value.get()],
            {"Hostiles": "hostile", "Neutres": "neutral"}.get(self.hostility.get(), ""),
        )
        self.table.delete(*self.table.get_children())
        labels = {
            "melee": "CaC",
            "ranged": "Distance",
            "summon": "Invocation",
            "buff": "Buffs",
            "heal": "Soins",
        }
        for row in rows:
            self.table.insert(
                "",
                "end",
                iid=row["id"],
                text=row["name"],
                values=(
                    row["race"],
                    ", ".join(
                        label for key, label in labels.items() if key in row["roles"]
                    ),
                    "Hostile" if row["hostile"] else "Neutre",
                ),
            )
        if rows:
            selected = (
                selected if selected and self.table.exists(selected) else rows[0]["id"]
            )
            self.table.selection_set(selected)
            self.table.see(selected)
        self.count.set(f"{len(rows)} / {len(self.rows)} mobs")
        self.describe()

    def describe(self):
        row = next((row for row in self.rows if row["id"] == self.get()), None)
        self.details.set(
            f"{row['id']} · rang {row['rank']}\n"
            + (", ".join(row["abilities"]) or "Attaque de base au corps à corps")
            if row
            else "Aucun résultat. Élargissez ou réinitialisez les filtres."
        )
