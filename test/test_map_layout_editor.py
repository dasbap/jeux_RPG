from copy import deepcopy
import math

import pytest

from jeuxRPG.multiplayer import fields, map_assets, world
from jeuxRPG.multiplayer.map_layout_editor import apply_layout, layout_places, validate_layout


def test_layout_is_persisted_and_applied_without_changing_topology(tmp_path):
    data = deepcopy(fields.MAPS)
    data['rosee']['village_streets'] = deepcopy(world.VILLAGE_STREETS['rosee'])
    data['rosee']['world_view'] = {'position': [250, 310], 'entry': [40, 80], 'points': {'mira': {'position': [210, 180], 'name': 'Place des voyageurs'}, 'forest': {'position': [470, 280]}}}
    before = deepcopy(data['rosee']['village_streets'])
    path = tmp_path / 'world.json'
    map_assets.save(path, data)
    loaded = map_assets.load(path)
    places = apply_layout(deepcopy(world.PLACES), loaded)
    assert (places['rosee']['x'], places['rosee']['y']) == (250, 310)
    assert places['rosee']['entry'] == [40, 80]
    mira = next(p for p in places['rosee']['points'] if p['id'] == 'mira')
    assert (mira['x'], mira['y'], mira['name']) == (210, 180, 'Place des voyageurs')
    assert loaded['rosee']['village_streets'] == before


def test_builder_plan_uses_current_names_and_rattachement():
    data = deepcopy(fields.MAPS)
    data['rosee']['name'] = 'Rosée modifiée'
    data['forest']['zone_id'] = 'rosee'
    data['rosee']['world_view'] = {'points': {'forest': {'position': [550, 290], 'name': 'Forêt proche'}}}
    before = deepcopy(data)
    places = layout_places(data)
    assert places['rosee']['name'] == 'Rosée modifiée'
    point = next(p for p in places['rosee']['points'] if p['id'] == 'forest')
    assert (point['x'], point['y'], point['name']) == (550, 290, 'Forêt proche')
    assert not any(p['id'] == 'forest' for p in places['lisiere']['points'])
    assert data == before


@pytest.mark.parametrize('value', [None, {'position': [-1, 20]}, {'entry': [True, 4]}, {'position': [math.inf, 5]}, {'points': {'mira': {'name': ''}}}, {'points': {'bad id': {'position': [1, 2]}}}, {'points': []}])
def test_invalid_layout_rejected(value):
    with pytest.raises(ValueError):
        validate_layout(value)


def test_tk_builder_panels_keep_one_window_and_restore_previous_view(monkeypatch):
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox, simpledialog
        root = tk.Tk()
    except (ImportError, RuntimeError) as exc:
        pytest.skip(str(exc))
    except Exception as exc:
        if type(exc).__name__ == 'TclError':
            pytest.skip(str(exc))
        raise
    from jeuxRPG.multiplayer import map_editor
    from jeuxRPG.multiplayer.editor_ui import EditorPanel
    from jeuxRPG.multiplayer.map_world_editor import WorldEditor
    from jeuxRPG.multiplayer.map_assembly import AssemblyWindow
    try:
        root.withdraw()
        for key, value in [('tk', tk), ('ttk', ttk), ('filedialog', filedialog), ('messagebox', messagebox), ('simpledialog', simpledialog)]:
            monkeypatch.setattr(map_editor, key, value, raising=False)
        editor = map_editor.MapEditor(root)
        previous = list(root.pack_slaves())
        roads = WorldEditor(editor)
        def accept_form():
            panels = [p for p in root.pack_slaves() if isinstance(p, EditorPanel)]
            assert len(panels) == 1
            for child in panels[0].content.winfo_children():
                if isinstance(child, ttk.Button) and child.cget('text') == 'Valider':
                    child.invoke()
                    return
            raise AssertionError('Missing validation')
        root.after(50, accept_form)
        assert editor.form('Nom', {'name': 'Rosée'}) == {'name': 'Rosée'}
        assert root.pack_slaves() == [roads.panel]
        roads.panel.destroy()
        assert root.pack_slaves() == previous
        assembly = AssemblyWindow(editor)
        assert not any(isinstance(w, tk.Toplevel) for w in root.winfo_children())
        assembly.panel.destroy()
        assert root.pack_slaves() == previous
    finally:
        root.destroy()
