_panel_type = None


class EditorPanel:
    def __new__(cls, *args, **kwargs):
        global _panel_type, tk, ttk
        if cls is EditorPanel:
            import tkinter as tk
            from tkinter import ttk
            if _panel_type is None:
                _panel_type = type("TkEditorPanel", (EditorPanel, ttk.Frame), {})
            return object.__new__(_panel_type)
        return object.__new__(cls)
    def __init__(self, parent, title=""):
        self.host = parent
        self.previous = [(child, child.pack_info()) for child in parent.pack_slaves()]
        for child, options in self.previous:
            child.pack_forget()
        super().__init__(parent, padding=8)
        self.pack(fill="both", expand=True)
        self.heading = ttk.Frame(self)
        self.heading.pack(fill="x", pady=(0, 8))
        ttk.Button(self.heading, text="← Retour", command=self.destroy).pack(side="left")
        self.caption = ttk.Label(self.heading, text=title, font=("Arial", 12, "bold"))
        self.caption.pack(side="left", padx=12)
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.closed = False
        self.top = parent.winfo_toplevel()
        self.previous_close = self.top.protocol("WM_DELETE_WINDOW")
        self.top.protocol("WM_DELETE_WINDOW", self.destroy)

    def title(self, text):
        self.caption.configure(text=text)

    def geometry(self, value):
        pass

    def transient(self, parent):
        pass

    def grab_set(self):
        pass

    def protocol(self, name, callback):
        if name == "WM_DELETE_WINDOW":
            self.heading.winfo_children()[0].configure(command=callback)
            self.top.protocol(name, callback)

    def destroy(self):
        if self.closed:
            return
        self.closed = True
        if self.top.winfo_exists():
            self.top.protocol("WM_DELETE_WINDOW", self.previous_close)
        super().destroy()
        for child, options in self.previous:
            if child.winfo_exists():
                child.pack(**options)


class InlineMessages:
    def __init__(self, parent):
        self.parent = parent

    def prompt(self, title, message, choices):
        panel = EditorPanel(self.parent, title)
        ttk.Label(panel.content, text=message, wraplength=760, justify="left").pack(fill="x", pady=16)
        answer = [None]
        def choose(value):
            answer[0] = value
            panel.destroy()
        bar = ttk.Frame(panel.content)
        bar.pack(fill="x")
        for label, value in choices:
            ttk.Button(bar, text=label, command=lambda v=value: choose(v)).pack(side="left", padx=4)
        self.parent.wait_window(panel)
        return answer[0]

    def showerror(self, title, message, **kwargs):
        return self.prompt(title, message, [("Fermer", None)])

    def showinfo(self, title, message, **kwargs):
        return self.showerror(title, message)

    def askyesno(self, title, message, **kwargs):
        return bool(self.prompt(title, message, [("Oui", True), ("Non", False)]))

    def askyesnocancel(self, title, message, **kwargs):
        return self.prompt(title, message, [("Garder", True), ("Abandonner", False), ("Annuler", None)])


def fold(parent, title, opened=False):
    from tkinter import ttk
    outer = ttk.Frame(parent)
    outer.pack(fill="x", pady=2)
    body = ttk.Frame(outer, padding=(12, 3))
    button = ttk.Button(outer)
    button.pack(fill="x")
    active = [opened]
    def refresh():
        button.configure(text=("▾ " if active[0] else "▸ ") + title)
        if active[0]:
            body.pack(fill="x")
        else:
            body.pack_forget()
    def toggle():
        active[0] = not active[0]
        refresh()
    button.configure(command=toggle)
    refresh()
    return body
