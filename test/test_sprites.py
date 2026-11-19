import io
import json
import zipfile
from types import SimpleNamespace

import pytest
from test_living_world import no_network  # noqa: F401

from jeuxRPG.multiplayer.browser_solo_assets import engine_archive
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.sprite_catalog import PixelDocument, blank, original, validate
from jeuxRPG.multiplayer.state_bundles import encode


def data():
    return {"assets": {"hero": original()}, "bindings": {"class:Knight": "hero"}}


def test_legacy_project_and_sprite_roundtrip(tmp_path):
    project = Project(tmp_path / "project")
    before = project.state()
    project.content["sprites"] = data()
    project.save()
    loaded = Project(project.directory)
    assert loaded.content["sprites"] == data()
    loaded.restore(before)
    assert loaded.content.get("sprites", {"assets": {}, "bindings": {}}) != data()


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["assets"]["hero"].update(width=33),
        lambda d: d["assets"]["hero"].update(width=True),
        lambda d: d["assets"]["hero"].update(frame_ms=1),
        lambda d: d["assets"]["hero"]["palette"].__setitem__(1, "url(https://invalid)"),
        lambda d: d["assets"]["hero"]["palette"].__setitem__(0, "#ffffff"),
        lambda d: d["assets"]["hero"]["frames"][0].__setitem__(0, "x" * 16),
        lambda d: d["assets"]["hero"].update(frames=[]),
        lambda d: d["assets"]["hero"].update(frames=[blank()["frames"][0]] * 9),
        lambda d: d["bindings"].update({"class:Knight": "absent"}),
        lambda d: d["bindings"].update({"class:Knight": []}),
        lambda d: d["bindings"].update({"image:https://invalid": "hero"}),
    ],
)
def test_invalid_or_remote_sprite_data_is_rejected(change):
    document = data()
    change(document)
    with pytest.raises(ValueError):
        validate(document)


def test_pixel_budget_and_stable_undo_redo():
    document = PixelDocument(blank(size=8))
    document.checkpoint()
    document.paint(2, 2, 3, fill=True)
    assert document.sprite["frames"][0] == ["3" * 8] * 8
    document.undo()
    assert document.sprite == blank(size=8)
    document.undo(redo=True)
    document.add_frame()
    document.paint(2, 2, 0)
    assert document.sprite["frames"][0][2][2] == "3"
    assert document.sprite["frames"][1][2][2] == "0"
    oversized = {
        "assets": {f"sprite_{i}": blank(size=32) for i in range(64)},
        "bindings": {},
    }
    oversized["assets"]["sprite_0"]["frames"] *= 2
    for sprite in oversized["assets"].values():
        sprite["frames"] = sprite["frames"] * (8 // len(sprite["frames"]))
    with pytest.raises(ValueError, match="budget"):
        validate(oversized)


def test_unknown_entity_prevents_a_project_save(tmp_path):
    project = Project(tmp_path / "project")
    project.content["sprites"] = data()
    project.content["sprites"]["bindings"]["mob:missing_mob"] = "hero"
    with pytest.raises(ValueError, match="entité absente"):
        project.validate()


def test_sprite_data_survives_delta_and_is_packaged_without_external_images():
    state = {"session": {"tutorial": {"sprites": data()}}}
    first = encode(state)
    assert first["bundles"]["session/tutorial/sprites"] == data()
    state["session"]["tutorial"]["sprites"]["bindings"] = {}
    assert (
        "session/tutorial/sprites"
        in encode(state, json.dumps(first["hashes"]))["bundles"]
    )
    with zipfile.ZipFile(io.BytesIO(engine_archive())) as archive:
        assert "jeuxRPG/multiplayer/sprite_catalog.py" in archive.namelist()


def test_tk_editor_paint_frames_png_association_rename_and_reopen(tmp_path):
    tk = pytest.importorskip("tkinter")
    from jeuxRPG.multiplayer.sprite_maker import SpriteMaker

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk nécessite un affichage local")
    root.withdraw()
    project = Project(tmp_path / "project")
    history = []

    def changed(before):
        project.validate()
        history.append(before)

    maker = None
    try:
        maker = SpriteMaker(root, project, changed, visible=False)
        maker.identifier.set("pixel_test")
        maker.name.set("Personnage original")
        maker.start_stroke(SimpleNamespace(x=maker.cell * 2 + 1, y=maker.cell * 3 + 1))
        assert maker.document.sprite["frames"][0][3][2] == "3"
        maker.frame_action(True)
        maker.document.paint(3, 3, 4)
        assert maker.apply()
        target = next(
            label for label, key in maker.target_labels.items() if key == "class:Knight"
        )
        maker.target.set(target)
        maker.asset.set("pixel_test")
        maker.weapon.set("(Aucune)")
        maker.tint.set("")
        maker.bind_sprite()
        assert project.content["sprites"]["bindings"]["class:Knight"] == "pixel_test"
        maker.identifier.set("renamed_test")
        assert maker.apply()
        assert "pixel_test" not in project.content["sprites"]["assets"]
        assert project.content["sprites"]["bindings"]["class:Knight"] == "renamed_test"
        path = tmp_path / "sprite.png"
        maker.export_png(str(path))
        assert path.is_file()
        maker.import_png(str(path))
        imported = maker.document.sprite
        assert imported["frames"][0][0][0] == "0"
        assert imported["frames"][0][3][2] != "0"
        project.save()
        restored = Project(project.directory)
        assert restored.content["sprites"] == project.content["sprites"]
        project.restore(history[-1])
        assert project.content["sprites"]["bindings"]["class:Knight"] == "pixel_test"
    finally:
        if maker is not None:
            maker.window.after_cancel(maker.timer)
            maker.window.destroy()
        root.destroy()


def test_controller_sprite_tab_and_global_undo_redo(tmp_path):
    tk = pytest.importorskip("tkinter")
    from tkinter import ttk

    from jeuxRPG.multiplayer.controller import Controller
    from jeuxRPG.multiplayer.sprite_maker import SpriteMaker

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk nécessite un affichage local")
    root.withdraw()
    maker = None
    try:
        project = Project(tmp_path / "controller-project")
        screen = Controller(root, project)
        notebook = next(
            child for child in root.winfo_children() if isinstance(child, ttk.Notebook)
        )
        assert "Sprites / Sprite Maker" in [
            notebook.tab(tab, "text") for tab in notebook.tabs()
        ]
        maker = SpriteMaker(root, project, screen.finish_change, visible=False)
        maker.identifier.set("undo_test")
        assert maker.apply()
        assert "undo_test" in project.content["sprites"]["assets"]
        screen.undo()
        assert (
            "undo_test" not in project.content.get("sprites", {"assets": {}})["assets"]
        )
        screen.redo()
        assert "undo_test" in project.content["sprites"]["assets"]
    finally:
        if maker is not None:
            maker.window.after_cancel(maker.timer)
            maker.window.destroy()
        root.destroy()
