"""Dedicated interface tab with a schematic preview and undoable project changes."""

from copy import deepcopy

from .interface_catalog import (
    DEFAULTS,
    GROUPS,
    LABELS,
    POSITIONS,
    RANGES,
    settings,
    validate_interface,
)


class ControllerInterfaceMixin:
    def create_interface_tab(self, notebook):
        page = self.ttk.Frame(notebook, padding=12)
        notebook.add(page, text="Interface")
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(1, weight=1)
        self.ttk.Label(
            page,
            text="Réglages de l’interface du jeu — appliquer puis enregistrer le projet.",
            wraplength=1000,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        groups = self.ttk.Notebook(page)
        groups.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        self.interface_fields = {}
        for group, values in DEFAULTS.items():
            frame = self.ttk.Frame(groups, padding=12)
            groups.add(frame, text=GROUPS[group])
            frame.columnconfigure(1, weight=1)
            for row, (key, value) in enumerate(values.items()):
                self.ttk.Label(frame, text=LABELS[key], wraplength=250).grid(
                    row=row, column=0, sticky="w", pady=8, padx=(0, 10)
                )
                variable = self.tk.StringVar()
                self.interface_fields[group, key] = variable
                control = self.interface_control(frame, key, value, variable)
                control.grid(row=row, column=1, sticky="ew", pady=8)
                variable.trace_add("write", lambda *args: self.preview_interface())
            if group == "minimap":
                self.ttk.Label(
                    frame,
                    text="Les petits écrans conservent leur disposition adaptée.",
                    wraplength=380,
                ).grid(row=len(values), column=0, columnspan=2, sticky="w", pady=12)
        preview = self.ttk.LabelFrame(page, text="Aperçu schématique", padding=8)
        preview.grid(row=1, column=1, sticky="nsew")
        self.interface_canvas = self.tk.Canvas(
            preview, background="#17251f", highlightthickness=0, width=420, height=320
        )
        self.interface_canvas.pack(fill="both", expand=True)
        self.interface_canvas.bind(
            "<Configure>", lambda event: self.preview_interface()
        )
        self.ttk.Label(
            preview,
            text="Menus, boutons, quêtes et mini-carte. Le rendu exact s’adapte à la résolution du jeu.",
            wraplength=380,
        ).pack(fill="x", pady=10)
        actions = self.ttk.Frame(page)
        actions.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        for label, callback in (
            ("Appliquer à l’interface", self.apply_interface),
            ("Valeurs par défaut", self.reset_interface),
            ("Recharger les réglages du projet", self.refresh_interface),
        ):
            self.ttk.Button(actions, text=label, command=callback).pack(
                side="left", padx=(0, 8)
            )
        self.refresh_interface()

    def interface_control(self, frame, key, value, variable):
        if key == "position" or type(value) is bool:
            return self.ttk.Combobox(
                frame,
                textvariable=variable,
                state="readonly",
                width=15,
                values=list(POSITIONS.values())
                if key == "position"
                else ["Oui", "Non"],
            )
        if key in RANGES:
            low, high = RANGES[key]
            return self.ttk.Spinbox(
                frame, textvariable=variable, from_=low, to=high, width=12
            )
        holder = self.ttk.Frame(frame)
        self.ttk.Entry(holder, textvariable=variable, width=12).pack(
            side="left", fill="x", expand=True
        )
        self.ttk.Button(
            holder,
            text="Choisir…",
            command=lambda: self.choose_interface_color(variable),
        ).pack(side="left", padx=(5, 0))
        return holder

    def choose_interface_color(self, variable):
        from tkinter.colorchooser import askcolor

        initial = variable.get()
        try:
            self.root.winfo_rgb(initial)
        except self.tk.TclError:
            initial = DEFAULTS["theme"]["accent_color"]
        _, selected = askcolor(
            color=initial, parent=self.root, title="Couleur de l’interface"
        )
        if selected:
            variable.set(selected)

    def read_interface(self):
        result = deepcopy(DEFAULTS)
        for (group, key), variable in self.interface_fields.items():
            value = variable.get()
            if key in RANGES:
                value = int(value)
            elif key == "position":
                value = next(
                    (key for key, label in POSITIONS.items() if label == value), value
                )
            elif key == "compact":
                if value not in ("Oui", "Non"):
                    raise ValueError("Fiches compactes : choisissez Oui ou Non.")
                value = value == "Oui"
            result[group][key] = value
        return validate_interface(result)

    def refresh_interface(self):
        if not hasattr(self, "interface_fields"):
            return
        for (group, key), variable in self.interface_fields.items():
            value = settings(self.project.content)[group][key]
            variable.set(
                POSITIONS[value]
                if key == "position"
                else ("Oui" if value else "Non")
                if type(value) is bool
                else str(value)
            )
        self.preview_interface()

    def apply_interface(self):
        try:
            value = self.read_interface()
            before = self.project.state()
            self.project.content["interface"] = value
            try:
                self.project.validate()
            except (ValueError, KeyError, TypeError):
                self.project.restore(before)
                raise
            if self.project.state() != before:
                self.remember(before)
            self.refresh()
            self.status.set(
                "Interface appliquée. Enregistrez le projet, puis reconstruisez Windows ou redémarrez le serveur."
            )
        except (ValueError, KeyError, TypeError) as error:
            self.messagebox.showerror("Interface", str(error), parent=self.root)

    def reset_interface(self):
        for (group, key), variable in self.interface_fields.items():
            value = DEFAULTS[group][key]
            variable.set(
                POSITIONS[value]
                if key == "position"
                else ("Oui" if value else "Non")
                if type(value) is bool
                else str(value)
            )
        self.apply_interface()

    def preview_interface(self):
        if not hasattr(self, "interface_canvas"):
            return
        canvas = self.interface_canvas
        canvas.delete("all")
        try:
            value = self.read_interface()
        except (ValueError, KeyError, TypeError):
            canvas.create_text(
                20,
                30,
                anchor="nw",
                text="Complétez une valeur valide pour actualiser l’aperçu.",
                fill="white",
                width=320,
            )
            return
        width, height = max(300, canvas.winfo_width()), max(240, canvas.winfo_height())
        menu, theme = value["menus"], value["theme"]
        panel_width, panel_height = (
            width * menu["width_percent"] / 100,
            height * menu["height_percent"] / 100,
        )
        x = (
            8
            if menu["position"] == "left"
            else width - panel_width - 8
            if menu["position"] == "right"
            else (width - panel_width) / 2
        )
        y = (height - panel_height) / 2
        mini = value["minimap"]
        canvas.create_rectangle(
            8,
            height - 8 - mini["height_px"] * 0.35,
            8 + mini["width_px"] * 0.35,
            height - 8,
            fill="#0b141d",
            outline=theme["accent_color"],
        )
        canvas.create_rectangle(
            x,
            y,
            x + panel_width,
            y + panel_height,
            fill=theme["panel_color"],
            outline="#667d8b",
        )
        canvas.create_text(
            x + 12,
            y + 12,
            text="Menu",
            anchor="nw",
            fill=theme["text_color"],
            font=("Segoe UI", max(8, round(theme["font_size_px"] * 0.75)), "bold"),
        )
        gap = value["quests"]["gap_px"] * 0.5
        padding = value["quests"]["padding_px"] * 0.5
        card_height = 46 if value["quests"]["compact"] else 70
        columns = min(
            2,
            max(
                1,
                int(
                    (panel_width - 20 + gap)
                    / (value["quests"]["card_min_width_px"] * width / 1280 + gap)
                ),
            ),
        )
        card_width = (panel_width - 20 - gap * (columns - 1)) / columns
        rows = min(3, max(1, int((panel_height - 45) / (card_height + gap))))
        for index in range(rows * columns):
            top = y + 36 + (index // columns) * (card_height + gap)
            left = x + 10 + (index % columns) * (card_width + gap)
            canvas.create_rectangle(
                left,
                top,
                left + card_width,
                top + card_height,
                fill="#1b2b3b",
                outline="#43576a",
            )
            canvas.create_text(
                left + padding,
                top + padding,
                text="Quête",
                anchor="nw",
                fill=theme["text_color"],
                font=("Segoe UI", max(7, round(theme["font_size_px"] * 0.6))),
            )
            canvas.create_rectangle(
                left + card_width - 35 - padding,
                top + padding,
                left + card_width - padding,
                top + padding + 17,
                fill=theme["accent_color"],
                outline="",
            )
