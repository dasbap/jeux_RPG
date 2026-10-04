from jeuxRPG.multiplayer.map_playability import issues


def map_data():
    return {'width': 5, 'height': 5, 'cover': [], 'exits': [{'name': 'Sortie', 'position': [4, 2]}], 'spawns': [[1, 2]], 'sites': [{'id': 'forge', 'name': 'Forge', 'position': [0, 1]}]}


def test_open_map_is_playable():
    assert issues({'zone': map_data()}) == []


def test_river_without_bridge_blocks_access():
    data = map_data()
    data['water'] = [[2, y] for y in range(5)]
    errors = issues({'zone': data})
    assert any('Forge inaccessible' in error for error in errors)
    assert any('spawner' in error for error in errors)
    data['bridges'] = [[2, 2]]
    assert issues({'zone': data}) == []


def test_checks_every_teleport_arrival():
    source, target = map_data(), map_data()
    source['exits'][0].update(destination='target', entry=[0, 2])
    target['blocked'] = [[2, y] for y in range(5)]
    assert any('Sortie' in error and 'depuis source' in error for error in issues({'source': source, 'target': target}))


def test_builder_refuses_broken_maps_before_controller_save(monkeypatch):
    from types import SimpleNamespace
    from jeuxRPG.multiplayer import map_editor, map_assets
    editor = map_editor.MapEditor.__new__(map_editor.MapEditor)
    data = map_data()
    data['water'] = [[2, y] for y in range(5)]
    editor.maps = {'zone': data}
    saved, errors = [], []
    editor.on_save = lambda choose: saved.append(choose)
    monkeypatch.setattr(map_assets, 'validate', lambda maps: maps)
    monkeypatch.setattr(map_editor, 'messagebox', SimpleNamespace(showerror=lambda title, text: errors.append(text)), raising=False)
    editor.save()
    assert saved == []
    assert errors and 'inaccessible' in errors[0]


def test_initial_spawn_cannot_be_stranded_on_separate_island():
    data = map_data()
    data['blocked'] = [[2, y] for y in range(5)]
    errors = issues({'clearing': data})
    assert any('Sortie' in error and 'apparition initiale' in error for error in errors)
