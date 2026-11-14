"""Tk pixel editor sharing the Builder project's validation, save and undo history."""

from collections import Counter
from copy import deepcopy

from .sprite_catalog import (
    DIGITS,
    PixelDocument,
    blank,
    catalog,
    original,
    targets,
    validate,
)


class SpriteMaker:
    def __init__(self, parent, project, on_change, visible=True):
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.ttk = tk, ttk
        self.project, self.on_change = project, on_change
        self.window = tk.Toplevel(parent)
        self.previous_grab = parent.grab_current()
        self.window.withdraw()
        self.window.title("Sprite Maker — pixels et associations")
        self.window.geometry("1080x820")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.columnconfigure(1, weight=1)
        self.window.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(self.window, padding=10)
        sidebar.grid(row=0, column=0, sticky="ns")
        ttk.Label(sidebar, text="Sprites du projet").pack(anchor="w")
        self.listbox = tk.Listbox(sidebar, width=24, exportselection=False)
        self.listbox.pack(fill="both", expand=True, pady=8)
        self.listbox.bind("<<ListboxSelect>>", self.select_sprite)
        for label, callback in (
            ("Nouveau", self.new_sprite),
            ("Modèle original", self.new_original),
            ("Gabarit arme 24 × 24", self.new_weapon),
            ("Dupliquer", self.duplicate),
            ("Recharger le dessin", self.reload),
            ("Supprimer et désassocier", self.delete_sprite),
        ):
            ttk.Button(sidebar, text=label, command=callback).pack(fill="x", pady=2)
        main = ttk.Frame(self.window, padding=10)
        main.grid(row=0, column=1, sticky="nsew")
        self.identifier = tk.StringVar(value="nouveau_sprite")
        self.name = tk.StringVar(value="Nouveau sprite")
        self.size = tk.StringVar(value="16")
        self.layer = tk.StringVar(value="Corps")
        self.tool = tk.StringVar(value="Crayon")
        self.frame_choice = tk.StringVar(value="1")
        self.frame_ms = tk.StringVar(value="180")
        self.status = tk.StringVar(
            value="Dessinez, appliquez au projet, puis enregistrez le projet dans le Builder."
        )
        details = ttk.Frame(main)
        details.pack(fill="x")
        for label, variable, width in (
            ("Identifiant", self.identifier, 22),
            ("Nom", self.name, 25),
        ):
            ttk.Label(details, text=label).pack(side="left")
            ttk.Entry(details, textvariable=variable, width=width).pack(
                side="left", padx=5
            )
        ttk.Label(details, text="Calque").pack(side="left")
        ttk.Combobox(
            details,
            textvariable=self.layer,
            values=["Corps", "Arme"],
            state="readonly",
            width=7,
        ).pack(side="left")
        tools = ttk.Frame(main)
        tools.pack(fill="x", pady=8)
        ttk.Combobox(
            tools,
            textvariable=self.tool,
            values=["Crayon", "Gomme", "Remplir", "Pipette"],
            state="readonly",
            width=12,
        ).pack(side="left")
        ttk.Label(tools, text="Taille du nouveau sprite").pack(side="left", padx=8)
        ttk.Combobox(
            tools,
            textvariable=self.size,
            values=[8, 16, 24, 32],
            state="readonly",
            width=4,
        ).pack(side="left")
        for label, action in (
            ("Annuler trait", lambda: self.undo()),
            ("Rétablir", lambda: self.undo(True)),
            ("Miroir", self.mirror),
        ):
            ttk.Button(tools, text=label, command=action).pack(side="left", padx=3)
        workspace = ttk.Frame(main)
        workspace.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            workspace, width=384, height=384, background="#202738", highlightthickness=0
        )
        self.canvas.pack(side="left", anchor="nw")
        self.canvas.bind("<Button-1>", self.start_stroke)
        self.canvas.bind("<B1-Motion>", self.draw_stroke)
        self.canvas.bind(
            "<Button-3>", lambda event: self.start_stroke(event, erase=True)
        )
        self.canvas.bind(
            "<B3-Motion>", lambda event: self.draw_stroke(event, erase=True)
        )
        preview = ttk.Frame(workspace, padding=10)
        preview.pack(side="left", fill="y")
        ttk.Label(preview, text="Aperçu animé").pack()
        self.preview = tk.Label(preview, background="#384457", width=128, height=128)
        self.preview.pack(pady=8)
        self.colors = ttk.Frame(preview)
        self.colors.pack(fill="x")
        ttk.Button(preview, text="Changer la couleur…", command=self.choose_color).pack(
            pady=8
        )
        ttk.Button(
            preview,
            text="Ajouter une couleur…",
            command=lambda: self.choose_color(True),
        ).pack()
        frames = ttk.Frame(main)
        frames.pack(fill="x", pady=8)
        self.frame_select = ttk.Combobox(
            frames,
            textvariable=self.frame_choice,
            values=[1],
            state="readonly",
            width=4,
        )
        self.frame_select.pack(side="left")
        self.frame_select.bind(
            "<<ComboboxSelected>>", lambda event: self.select_frame()
        )
        ttk.Button(
            frames, text="Dupliquer l'image", command=lambda: self.frame_action(True)
        ).pack(side="left", padx=5)
        ttk.Button(
            frames, text="Supprimer l'image", command=lambda: self.frame_action(False)
        ).pack(side="left")
        ttk.Label(frames, text="Durée / image (ms)").pack(side="left", padx=8)
        ttk.Spinbox(
            frames, textvariable=self.frame_ms, from_=80, to=2000, width=6
        ).pack(side="left")
        actions = ttk.Frame(main)
        actions.pack(fill="x")
        for label, callback in (
            ("Importer PNG…", self.import_png),
            ("Exporter l'image PNG…", self.export_png),
            ("Appliquer le sprite au projet", self.apply),
        ):
            ttk.Button(actions, text=label, command=callback).pack(side="left", padx=3)
        binding = ttk.LabelFrame(
            main, text="Associer un sprite à une entité", padding=8
        )
        binding.pack(fill="x", pady=10)
        self.target = tk.StringVar()
        self.asset = tk.StringVar()
        self.weapon = tk.StringVar(value="(Aucune)")
        self.tint = tk.StringVar()
        self.target_select = ttk.Combobox(
            binding, textvariable=self.target, state="readonly", width=50
        )
        self.target_select.pack(fill="x")
        self.target_select.bind(
            "<<ComboboxSelected>>", lambda event: self.selected_binding()
        )
        self.asset_select = ttk.Combobox(
            binding, textvariable=self.asset, state="readonly", width=30
        )
        self.asset_select.pack(side="left", pady=6)
        self.asset_select.bind(
            "<<ComboboxSelected>>", lambda event: self.available_weapons()
        )
        self.weapon_select = ttk.Combobox(
            binding, textvariable=self.weapon, state="readonly", width=25
        )
        self.weapon_select.pack(side="left", padx=6)
        ttk.Label(binding, text="Corps + arme").pack(side="left")
        tint_bar = ttk.Frame(main)
        tint_bar.pack(fill="x")
        ttk.Label(tint_bar, text="Teinte du corps (facultative)").pack(side="left")
        ttk.Entry(tint_bar, textvariable=self.tint, width=10).pack(side="left", padx=6)
        ttk.Button(tint_bar, text="Choisir…", command=self.choose_tint).pack(
            side="left"
        )
        ttk.Button(
            tint_bar, text="Teinte d'origine", command=lambda: self.tint.set("")
        ).pack(side="left", padx=6)
        ttk.Button(
            binding, text="Appliquer l'association", command=self.bind_sprite
        ).pack(side="left", padx=8)
        ttk.Label(main, textvariable=self.status, wraplength=700).pack(fill="x")
        self.document = PixelDocument(blank())
        self.active_id = None
        self.color = 3
        self.preview_frame = 0
        self.refresh_lists()
        self.load(next(iter(catalog(project.content)["assets"]), None))
        self.timer = self.window.after(180, self.animate)
        if visible:
            self.window.deiconify()
            if self.previous_grab is not None:
                self.window.grab_set()

    def error(self, error):
        self.status.set(str(error))

    def discard(self):
        from tkinter import messagebox

        saved = catalog(self.project.content)["assets"].get(self.active_id)
        dirty = (
            self.document.sprite != saved if saved else self.document.sprite != blank()
        )
        dirty = dirty or (
            saved is not None
            and (
                self.identifier.get() != self.active_id
                or self.name.get() != saved["name"]
                or self.frame_ms.get() != str(saved["frame_ms"])
            )
        )
        dirty = dirty or self.layer.get() != (
            "Arme" if self.document.sprite.get("layer") == "weapon" else "Corps"
        )
        return not dirty or messagebox.askyesno(
            "Dessin non appliqué",
            "Abandonner les modifications de ce dessin ?",
            parent=self.window,
        )

    def refresh_lists(self):
        data = catalog(self.project.content)
        self.ids = sorted(data["assets"])
        self.listbox.delete(0, "end")
        for key in self.ids:
            self.listbox.insert("end", f"{key} · {data['assets'][key]['name']}")
        self.target_labels = {
            f"{label} [{key}]": key
            for key, label in sorted(
                targets(
                    self.project.content, self.project.mobs, self.project.maps
                ).items()
            )
        }
        self.target_select.configure(values=list(self.target_labels))
        if self.target.get() not in self.target_labels:
            self.target.set(next(iter(self.target_labels), ""))
        self.asset_select.configure(
            values=[
                "(Aucun)",
                *(
                    key
                    for key in self.ids
                    if data["assets"][key].get("layer", "body") == "body"
                ),
            ]
        )
        self.selected_binding()

    def selected_binding(self):
        self.asset.set(
            catalog(self.project.content)["bindings"].get(
                self.target_labels.get(self.target.get()), "(Aucun)"
            )
        )
        data = catalog(self.project.content)
        target = self.target_labels.get(self.target.get())
        self.weapon.set(data.get("equipment", {}).get(target, "(Aucune)"))
        self.tint.set(data.get("colors", {}).get(target, ""))
        self.available_weapons()

    def available_weapons(self):
        assets = catalog(self.project.content)["assets"]
        body = assets.get(self.asset.get())
        choices = ["(Aucune)"] + [
            key
            for key, value in assets.items()
            if value.get("layer") == "weapon"
            and body
            and all(
                value[dimension] == body[dimension] for dimension in ("width", "height")
            )
        ]
        self.weapon_select.configure(values=choices)
        if self.weapon.get() not in choices:
            self.weapon.set("(Aucune)")

    def choose_tint(self):
        from tkinter.colorchooser import askcolor

        _, color = askcolor(self.tint.get() or "#638d62", parent=self.window)
        if color:
            self.tint.set(color)

    def load(self, identifier, sprite=None):
        self.active_id = identifier
        value = (
            sprite or catalog(self.project.content)["assets"].get(identifier) or blank()
        )
        self.document = PixelDocument(value)
        self.identifier.set(identifier or "nouveau_sprite")
        self.name.set(value["name"])
        self.layer.set("Arme" if value.get("layer") == "weapon" else "Corps")
        self.frame_ms.set(str(value["frame_ms"]))
        self.color = min(self.color, len(value["palette"]) - 1)
        self.redraw()

    def select_sprite(self, event=None):
        selected = self.listbox.curselection()
        if selected and self.ids[selected[0]] != self.active_id and self.discard():
            self.load(self.ids[selected[0]])

    def new_sprite(self):
        if self.discard():
            self.load(None, blank(size=int(self.size.get())))

    def new_weapon(self):
        if self.discard():
            sprite = blank("Nouvelle arme", 24)
            sprite["layer"] = "weapon"
            self.load(None, sprite)
            self.identifier.set("arme_nouvelle")
            self.status.set(
                "Calque transparent 24 × 24. Le repère jaune indique la main, près de (18, 14). Choisissez un corps dans les associations pour l'aperçu."
            )

    def new_original(self):
        from tkinter import messagebox

        if self.discard():
            creature = messagebox.askyesno(
                "Modèle original",
                "Créer une créature ?\nNon : voyageur en armure.",
                parent=self.window,
            )
            self.load(None, original(creature=creature))

    def duplicate(self):
        self.active_id = None
        self.identifier.set(self.identifier.get()[:42] + "_copie")
        self.status.set("Copie en cours : choisissez un identifiant puis appliquez.")

    def reload(self):
        if self.discard():
            self.refresh_lists()
            self.load(self.active_id if self.active_id in self.ids else None)

    def start_stroke(self, event, erase=False):
        if self.tool.get() != "Pipette":
            self.document.checkpoint()
        self.draw_stroke(event, erase)

    def draw_stroke(self, event, erase=False):
        x, y = int(event.x // self.cell), int(event.y // self.cell)
        sprite = self.document.sprite
        if not (0 <= x < sprite["width"] and 0 <= y < sprite["height"]):
            return
        if self.tool.get() == "Pipette" and not erase:
            self.color = DIGITS.index(sprite["frames"][self.document.frame][y][x])
        else:
            self.document.paint(
                x,
                y,
                0 if erase or self.tool.get() == "Gomme" else self.color,
                self.tool.get() == "Remplir",
            )
        self.redraw()

    def redraw(self):
        sprite = self.document.sprite
        self.cell = min(28, 384 // max(sprite["width"], sprite["height"]))
        self.canvas.delete("all")
        for y, row in enumerate(sprite["frames"][self.document.frame]):
            for x, digit in enumerate(row):
                color = sprite["palette"][DIGITS.index(digit)] or (
                    "#647080" if (x + y) % 2 else "#8793a0"
                )
                self.canvas.create_rectangle(
                    x * self.cell,
                    y * self.cell,
                    (x + 1) * self.cell,
                    (y + 1) * self.cell,
                    fill=color,
                    outline="#384457",
                )
        if (
            self.layer.get() == "Arme"
            and sprite["width"] == 24
            and sprite["height"] == 24
        ):
            self.canvas.create_rectangle(
                17 * self.cell,
                0,
                24 * self.cell,
                24 * self.cell,
                outline="#edc865",
                dash=(4, 4),
                width=2,
            )
            self.canvas.create_oval(
                18 * self.cell,
                14 * self.cell,
                19 * self.cell,
                15 * self.cell,
                outline="#edc865",
                width=2,
            )
        for child in self.colors.winfo_children():
            child.destroy()
        for index, color in enumerate(sprite["palette"]):
            self.tk.Button(
                self.colors,
                text="∅" if not index else "●" if index == self.color else "",
                background=color or "#8793a0",
                width=2,
                command=lambda i=index: self.set_color(i),
            ).grid(row=index // 4, column=index % 4)
        self.frame_select.configure(values=list(range(1, len(sprite["frames"]) + 1)))
        self.frame_choice.set(str(self.document.frame + 1))

    def set_color(self, index):
        self.color = index
        self.redraw()

    def choose_color(self, add=False):
        from tkinter.colorchooser import askcolor

        if add and len(self.document.sprite["palette"]) >= 16:
            self.error("Maximum : 15 couleurs et transparence.")
            return
        if not self.color and not add:
            self.error("La couleur 0 reste transparente. Choisissez une autre case.")
            return
        _, color = askcolor(
            self.document.sprite["palette"][self.color] or "#ffffff", parent=self.window
        )
        if color:
            self.document.checkpoint()
            if add:
                self.document.sprite["palette"].append(color)
                self.color = len(self.document.sprite["palette"]) - 1
            else:
                self.document.sprite["palette"][self.color] = color
            self.redraw()

    def undo(self, redo=False):
        self.document.undo(redo)
        self.redraw()

    def mirror(self):
        self.document.checkpoint()
        frame = self.document.frame
        self.document.sprite["frames"][frame] = [
            row[::-1] for row in self.document.sprite["frames"][frame]
        ]
        self.redraw()

    def select_frame(self):
        self.document.frame = int(self.frame_choice.get()) - 1
        self.redraw()

    def frame_action(self, add):
        try:
            self.document.add_frame() if add else self.document.remove_frame()
            self.redraw()
        except ValueError as error:
            self.error(error)

    def image(self, frame, sprite=None, tint=None):
        sprite = sprite or self.document.sprite
        palette = list(sprite["palette"])
        if tint and len(tint) == 7 and tint.startswith("#") and len(palette) >= 5:
            try:
                palette[4] = "#" + "".join(
                    f"{round(int(tint[index : index + 2], 16) * 0.7 + 255 * 0.3):02x}"
                    for index in (1, 3, 5)
                )
                palette[3] = tint
            except ValueError:
                pass
        photo = self.tk.PhotoImage(
            master=self.window, width=sprite["width"], height=sprite["height"]
        )
        for y, row in enumerate(sprite["frames"][frame % len(sprite["frames"])]):
            for x, digit in enumerate(row):
                if digit != "0":
                    photo.put(palette[DIGITS.index(digit)], (x, y))
        return photo

    def animate(self):
        self.preview_frame %= len(self.document.sprite["frames"])
        photo = self.image(
            self.preview_frame,
            tint=self.tint.get() if self.layer.get() == "Corps" else None,
        )
        assets = catalog(self.project.content)["assets"]
        other = assets.get(
            self.asset.get() if self.layer.get() == "Arme" else self.weapon.get()
        )
        if other and all(
            other[key] == self.document.sprite[key] for key in ("width", "height")
        ):
            if self.layer.get() == "Arme":
                weapon_photo = photo
                photo = self.image(self.preview_frame, other, tint=self.tint.get())
            else:
                weapon_photo = self.image(self.preview_frame, other)
            photo.tk.call(
                str(photo), "copy", str(weapon_photo), "-compositingrule", "overlay"
            )
        self.preview_image = photo.zoom(4, 4)
        self.preview.configure(image=self.preview_image)
        self.preview_frame += 1
        try:
            delay = max(80, min(2000, int(self.frame_ms.get())))
        except ValueError:
            delay = 180
        self.timer = self.window.after(delay, self.animate)

    def mutate(self, callback):
        before = self.project.state()
        try:
            data = deepcopy(catalog(self.project.content))
            callback(data)
            validate(data)
            self.project.content["sprites"] = data
            self.on_change(before)
            self.refresh_lists()
            self.status.set(
                "Appliqué au projet. Cliquez sur Enregistrer le projet dans le Builder pour conserver sur disque."
            )
            return True
        except (ValueError, KeyError, TypeError) as error:
            self.project.restore(before)
            self.error(error)
            return False

    def apply(self):
        identifier = self.identifier.get().strip()
        value = deepcopy(self.document.sprite)
        try:
            value.update(
                name=self.name.get().strip(), frame_ms=int(self.frame_ms.get())
            )
            if self.layer.get() == "Arme" or "layer" in value:
                value["layer"] = "weapon" if self.layer.get() == "Arme" else "body"
            if (
                identifier != self.active_id
                and identifier in catalog(self.project.content)["assets"]
            ):
                raise ValueError(
                    "Cet identifiant existe déjà : choisissez un autre identifiant."
                )
        except ValueError as error:
            self.error(error)
            return False

        def update(data):
            data["assets"][identifier] = value
            if self.active_id and self.active_id != identifier:
                del data["assets"][self.active_id]
                data["bindings"] = {
                    key: identifier if sprite == self.active_id else sprite
                    for key, sprite in data["bindings"].items()
                }
                data["equipment"] = {
                    key: identifier if sprite == self.active_id else sprite
                    for key, sprite in data.get("equipment", {}).items()
                }

        if self.mutate(update):
            self.load(identifier)
            return True
        return False

    def bind_sprite(self):
        def update(data):
            target = self.target_labels[self.target.get()]
            if self.asset.get() == "(Aucun)":
                data["bindings"].pop(target, None)
                data.setdefault("equipment", {}).pop(target, None)
                data.setdefault("colors", {}).pop(target, None)
            else:
                data["bindings"][target] = self.asset.get()
                if self.weapon.get() == "(Aucune)":
                    data.setdefault("equipment", {}).pop(target, None)
                else:
                    data.setdefault("equipment", {})[target] = self.weapon.get()
                if self.tint.get().strip():
                    data.setdefault("colors", {})[target] = self.tint.get().strip()
                else:
                    data.setdefault("colors", {}).pop(target, None)

        self.mutate(update)

    def delete_sprite(self):
        from tkinter import messagebox

        identifier = self.active_id
        if identifier and messagebox.askyesno(
            "Supprimer le sprite",
            "Supprimer ce sprite et toutes ses associations ?",
            parent=self.window,
        ):

            def update(data):
                del data["assets"][identifier]
                data["bindings"] = {
                    key: value
                    for key, value in data["bindings"].items()
                    if value != identifier
                }
                data["equipment"] = {
                    key: value
                    for key, value in data.get("equipment", {}).items()
                    if value != identifier and key in data["bindings"]
                }
                data["colors"] = {
                    key: value
                    for key, value in data.get("colors", {}).items()
                    if key in data["bindings"]
                }

            if self.mutate(update):
                self.load(None)

    def import_png(self, path=None):
        from tkinter import filedialog

        path = path or filedialog.askopenfilename(
            parent=self.window, filetypes=[("Sprite PNG", "*.png")]
        )
        if not path or not self.discard():
            return
        try:
            image = self.tk.PhotoImage(master=self.window, file=path)
            width, height = image.width(), image.height()
            if not 1 <= width <= 32 or not 1 <= height <= 32:
                raise ValueError("Importez une image PNG d'au plus 32 × 32 pixels.")
            colors = Counter(
                image.get(x, y)
                for y in range(height)
                for x in range(width)
                if not image.transparency_get(x, y)
            )
            chosen = [color for color, _ in colors.most_common(15)] or [(0, 0, 0)]
            palette = [
                None,
                *(f"#{red:02x}{green:02x}{blue:02x}" for red, green, blue in chosen),
            ]

            def digit(x, y):
                if image.transparency_get(x, y):
                    return "0"
                color = image.get(x, y)
                nearest = min(
                    range(len(chosen)),
                    key=lambda index: sum(
                        (a - b) ** 2 for a, b in zip(color, chosen[index], strict=True)
                    ),
                )
                return DIGITS[nearest + 1]

            sprite = {
                "name": "Import PNG",
                "width": width,
                "height": height,
                "palette": palette,
                "frames": [
                    ["".join(digit(x, y) for x in range(width)) for y in range(height)]
                ],
                "frame_ms": 180,
            }
            self.load(None, sprite)
            self.status.set(
                "PNG importé ; palette limitée aux 15 couleurs dominantes. Vérifiez les couleurs puis appliquez."
            )
        except (ValueError, self.tk.TclError) as error:
            self.error(error)

    def export_png(self, path=None):
        from tkinter import filedialog

        path = path or filedialog.asksaveasfilename(
            parent=self.window,
            defaultextension=".png",
            filetypes=[("Sprite PNG", "*.png")],
        )
        if path:
            try:
                self.image(self.document.frame).write(path, format="png")
                self.status.set("Image courante exportée avec transparence.")
            except (OSError, self.tk.TclError) as error:
                self.error(error)

    def close(self):
        if self.discard():
            self.window.after_cancel(self.timer)
            self.window.destroy()
            if self.previous_grab is not None and self.previous_grab.winfo_exists():
                self.previous_grab.grab_set()
