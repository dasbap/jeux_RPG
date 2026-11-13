"""Quest importance stays independent of its activity category and recurrence."""

from copy import deepcopy

import pytest
from test_controller import project

from jeuxRPG.multiplayer import content, controller, narrative, tutorial


@pytest.mark.parametrize(
    ("quest", "expected"),
    [
        ({"category": "hunt"}, "side"),
        ({"category": "main"}, "main"),
        ({"category": "tutorial"}, "tutorial"),
        ({"category": "hunt", "quest_type": "main"}, "main"),
        ({"category": "main", "quest_type": "side"}, "side"),
        ({"category": "crafting", "quest_type": "side", "repeatable": True}, "side"),
    ],
)
def test_type_fallback_and_independent_category(quest, expected):
    assert content.quest_type(quest) == expected


def test_builder_edits_and_persists_type_and_recurrence(tmp_path):
    selected = project(tmp_path)
    quest = selected.content["quests"][0]
    ui = controller.Controller.__new__(controller.Controller)
    ui.project = selected

    def form(title, values, choices):
        assert choices["quest_type"] == list(content.QUEST_TYPES)
        assert "category" in choices
        return {**values, "quest_type": "main", "repeatable": True}

    ui.form = form
    ui.edit_requirements = lambda requirements: requirements
    assert ui._edit_quest_or_achievement(quest["id"], False, "quests")
    selected.validate()
    selected.save()
    loaded = controller.Project(selected.directory).content["quests"][0]
    assert loaded["quest_type"] == "main"
    assert loaded["category"] == quest["category"]
    assert loaded["repeatable"] is True


def test_builder_rejects_invalid_quest_type(tmp_path):
    selected = project(tmp_path)
    selected.content["quests"][0]["quest_type"] = "unknown"
    with pytest.raises(ValueError):
        selected.validate()


def test_journal_transmits_type_without_turning_main_quests_mandatory(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    quest = data["quests"][0]
    quest["quest_type"] = "main"
    monkeypatch.setattr(content, "DATA", data)
    monkeypatch.setattr(narrative, "enabled", lambda: False)
    party = tutorial.new_party([{"id": "p", "name": "Test", "class_name": "Knight"}])
    party["custom_quests"] = {quest["id"]: {"status": "active", "progress": 0}}
    journal = content.quest_journal(party, "p")
    assert journal[0]["quest_type"] == "main"
    assert journal[0]["category"] == quest["category"]
    assert not journal[0].get("mandatory", False)


def test_builder_real_widgets_save_french_type_and_repeatability(tmp_path):
    import tkinter as tk
    from tkinter import ttk

    from jeuxRPG.multiplayer.controller_tools import catalog_rows

    selected = project(tmp_path)
    identifier = selected.content["quests"][0]["id"]
    root = tk.Tk()
    root.withdraw()
    try:
        ui = controller.Controller(root, selected)
        ui.edit_requirements = lambda requirements: requirements
        observed = {}

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def apply():
            dialog = next(
                child
                for child in root.winfo_children()
                if isinstance(child, tk.Toplevel)
            )
            dialog.withdraw()
            widgets = list(descendants(dialog))
            for label, value in (("Type de quête", "Secondaire"), ("Répétable", "Oui")):
                title = next(
                    widget
                    for widget in widgets
                    if isinstance(widget, ttk.Label) and widget.cget("text") == label
                )
                field = title.master.grid_slaves(
                    row=title.grid_info()["row"], column=1
                )[0]
                observed[label] = tuple(field.cget("values"))
                field.set(value)
            next(
                widget
                for widget in widgets
                if isinstance(widget, ttk.Button) and widget.cget("text") == "Appliquer"
            ).invoke()

        root.after(50, apply)
        root.after(
            5000,
            lambda: [
                child.destroy()
                for child in root.winfo_children()
                if isinstance(child, tk.Toplevel)
            ],
        )
        assert ui._edit_quest_or_achievement(identifier, False, "quests")
        assert observed["Type de quête"] == ("Principale", "Secondaire", "Découverte")
        assert observed["Répétable"] == ("Oui", "Non")
        selected.save()
        loaded = controller.Project(selected.directory)
        quest = next(
            item for item in loaded.content["quests"] if item["id"] == identifier
        )
        assert quest["quest_type"] == "side"
        assert quest["repeatable"] is True
        row = next(
            item for item in catalog_rows(loaded, "quests") if item[0] == identifier
        )
        assert "Secondaire" in row[2] and "Répétable" in row[2]
    finally:
        root.destroy()
