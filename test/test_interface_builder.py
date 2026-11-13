"""Builder presentation settings persist and reach the same game state on every client."""

from copy import deepcopy

import pytest
from test_controller import project

from jeuxRPG.multiplayer import content, controller, state_bundles, tutorial
from jeuxRPG.multiplayer.interface_catalog import DEFAULTS, settings, validate_interface


def test_old_projects_receive_independent_defaults():
    first = settings({})
    first["menus"]["width_percent"] = 50
    assert settings({}) == DEFAULTS
    assert (
        validate_interface({"menus": {"position": "right"}})["quests"]
        == DEFAULTS["quests"]
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        {"unknown": {}},
        {"menus": {"width_percent": 0}},
        {"menus": {"height_percent": True}},
        {"menus": {"position": "arbitrary"}},
        {"quests": {"compact": "yes"}},
        {"theme": {"accent_color": "red;display:none"}},
        {"hud": {"zone_banner_seconds": float("nan")}},
    ],
)
def test_invalid_interface_settings_are_rejected(value):
    with pytest.raises(ValueError, match="Interface"):
        validate_interface(value)


def test_interface_settings_are_sent_in_full_and_bundled_state(monkeypatch):
    data = deepcopy(content.DATA)
    data["interface"] = validate_interface(
        {"menus": {"width_percent": 60}, "hud": {"zone_banner_seconds": 1}}
    )
    monkeypatch.setattr(content, "DATA", data)
    party = tutorial.new_party([{"id": "p", "name": "Test", "class_name": "Knight"}])
    snapshot = tutorial.view(party, "p", 0)
    assert snapshot["interface"]["menus"]["width_percent"] == 60
    split = state_bundles.split({"session": {"tutorial": snapshot}})
    assert split["session/tutorial/interface"] == data["interface"]


def test_real_interface_tab_applies_undoes_saves_and_restores(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    selected = project(tmp_path)
    root = tk.Tk()
    root.withdraw()
    try:
        ui = controller.Controller(root, selected)
        notebooks = [
            child for child in root.winfo_children() if isinstance(child, ttk.Notebook)
        ]
        assert "Interface" in [
            notebooks[0].tab(tab, "text") for tab in notebooks[0].tabs()
        ]
        fields = ui.interface_fields
        fields["menus", "width_percent"].set("60")
        fields["menus", "height_percent"].set("55")
        fields["menus", "position"].set("À droite")
        fields["theme", "accent_color"].set("#55cc88")
        fields["quests", "compact"].set("Non")
        ui.apply_interface()
        assert selected.content["interface"]["menus"] == {
            "width_percent": 60,
            "height_percent": 55,
            "position": "right",
        }
        assert not selected.content["interface"]["quests"]["compact"]
        assert ui.interface_canvas.find_all()
        ui.undo()
        assert settings(selected.content) == DEFAULTS
        assert fields["menus", "width_percent"].get() == "75"
        ui.redo()
        selected.save()
        loaded = controller.Project(selected.directory)
        assert loaded.content["interface"]["menus"]["position"] == "right"
        assert loaded.content["interface"]["theme"]["accent_color"] == "#55cc88"
        before = selected.state()
        errors = []
        monkeypatch.setattr(
            ui.messagebox, "showerror", lambda *args, **kwargs: errors.append(args)
        )
        fields["menus", "width_percent"].set("0")
        ui.apply_interface()
        assert errors and selected.state() == before
        ui.reset_interface()
        assert settings(selected.content) == DEFAULTS
    finally:
        root.destroy()
