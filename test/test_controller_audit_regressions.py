from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from jeuxRPG import catalog_paths
from jeuxRPG._class.character import CharacterMeta
from jeuxRPG.multiplayer import controller, controller_gameplay, controller_tools, content, map_assets
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.map_world_editor import WorldEditor
from jeuxRPG.multiplayer.project_storage import project_lock
from test_controller import project


def test_default_runtime_loads_whole_local_project(tmp_path):
    p = project(tmp_path)
    p.maps['clearing']['name'] = 'Local map'
    p.content['quests'][0]['name'] = 'Local quest'
    p.mobs['goblin']['name'] = 'Local goblin'
    p.encounters['clearing_1']['name'] = 'Local encounter'
    p.save()
    environment = {**os.environ, 'PYTHONPATH': str(Path.cwd()) + os.pathsep + os.environ.get('PYTHONPATH', '')}
    for key in ('RPG_MAPS_FILE', 'RPG_CONTENT_FILE', 'RPG_CLASSES_FILE'):
        environment.pop(key, None)
    code = "from jeuxRPG.multiplayer import content, fields, map_building, tactics; assert content.DATA['quests'][0]['name']=='Local quest'; assert fields.MAPS['clearing']['name']=='Local map'; assert map_building.MOBS['goblin']['name']=='Local goblin'; assert tactics.PRESETS['clearing_1']['name']=='Local encounter'"
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('name', ['content.json', 'classes.json', 'world.json', 'mobs.json', 'encounters.json'])
def test_oversized_save_preserves_memory_and_all_files(tmp_path, monkeypatch, name):
    p = project(tmp_path)
    before, disk = p.state(), p.disk_state()
    monkeypatch.setattr(catalog_paths, 'catalog_limit', lambda value: 1 if value == name else 8 * 1024 * 1024)
    with pytest.raises(ValueError, match='trop volumineux'):
        p.save()
    assert p.state() == before
    assert p.disk_state() == disk
    assert not list(p.directory.glob('*.controller.tmp'))


def test_stale_project_cannot_overwrite_newer_catalogs(tmp_path):
    first = project(tmp_path)
    second = Project(first.directory)
    first.content['world']['starting_gold'] = 321
    first.save()
    disk = first.disk_state()
    second.content['world']['guild_max_members'] = 77
    with pytest.raises(ValueError, match='modifié sur disque'):
        second.save()
    assert first.disk_state() == disk
    assert Project(first.directory).content['world']['starting_gold'] == 321


def test_lock_prevents_overlapping_saves_and_is_released(tmp_path):
    p = project(tmp_path)
    with project_lock(p.directory), pytest.raises(ValueError, match='autre contrôleur'):
        p.save()
    p.save()


@pytest.mark.parametrize('class_name', ['Goblin', 'auditknight'])
def test_mob_stats_use_project_models_and_restore_registry(tmp_path, class_name):
    p = project(tmp_path)
    if class_name == 'auditknight':
        p.duplicate('classes', 'Knight', class_name)
    model = next(item for item in p.content['templates']['classes'] if item['id'] == class_name)
    model['base_stats']['hp'] = 514
    p.validate()
    screen = controller.Controller.__new__(controller.Controller)
    screen.project = p
    screen.form = lambda title, values, choices=None: values
    before = CharacterMeta._classes.copy()
    values = screen.edit_stats({'class_name': class_name, 'name': 'Audit', 'stats': {}})
    assert values['hp']['base'] == 514
    assert CharacterMeta._classes == before


def test_duplicate_npc_across_maps_is_rejected(tmp_path):
    p = project(tmp_path)
    site = deepcopy(p.maps['rosee']['sites'][0])
    site['position'] = p.maps['clearing']['exits'][0]['position'][:]
    p.maps['clearing']['sites'].append(site)
    with pytest.raises(ValueError, match='autre carte'):
        p.validate()


def test_controller_and_builder_reject_unplayable_json(tmp_path):
    p = project(tmp_path)
    definition = p.maps['clearing']
    definition['water'] = [[28, y] for y in range(definition['height'])]
    definition['bridges'] = []
    definition['bridge_rotations'] = []
    before = p.disk_state()
    with pytest.raises(ValueError, match='inaccessible'):
        p.save()
    assert p.disk_state() == before
    assert controller_tools.report(p)['erreurs']


def test_failed_validation_does_not_remove_generated_cache(tmp_path):
    p = project(tmp_path)
    p.content['templates']['skills']['skill:unused_probe'] = deepcopy(p.content['templates']['skills']['native:Knight:Sword Slash'])
    p.content['world']['repop_seconds'] = -1
    before = p.state()
    with pytest.raises(ValueError):
        p.validate()
    assert p.state() == before
    with pytest.raises(ValueError):
        p.save()
    assert p.state() == before


def test_start_map_rename_updates_rule_and_survives_reload(tmp_path):
    p = project(tmp_path)
    item = deepcopy(p.maps['clearing'])
    item.update(id='field_audit_zone', zone_id='audit_zone')
    item.pop('travel_routes', None)
    p.maps['audit_zone'] = item
    p.content['gameplay']['rules']['start']['map'] = 'audit_zone'
    p.validate()
    p.rename('maps', 'audit_zone', 'renamed_zone')
    p.save()
    assert Project(p.directory).content['gameplay']['rules']['start']['map'] == 'renamed_zone'


def test_trip_display_uses_custom_project_rules():
    class List:
        def __init__(self):
            self.values = []
        def delete(self, *args):
            self.values.clear()
        def insert(self, *args):
            self.values.append(args[-1])
    view = WorldEditor.__new__(WorldEditor)
    view.rules = {'movement': {'walking_kmh': 12}, 'time': {'game_ratio': 6}}
    view.routes = [{'id': 'route', 'name': 'Route', 'from': 'rosee', 'to': 'brume', 'distance_km': 1}]
    view.roads, view.list, view.streets = List(), List(), {}
    view.zone = SimpleNamespace(get=lambda: 'rosee')
    view.refresh()
    assert '5 min jeu / 50 s réelles' in view.roads.values[0]


def test_contracts_appear_in_recipe_references_and_report(tmp_path):
    p = project(tmp_path)
    p.content['endgame'].append({**deepcopy(content.DEFAULTS['endgame'][0]), 'id': 'craft_probe', 'kind': 'craft', 'target': 'casque'})
    p.validate()
    assert 'contrats/craft_probe' in controller_gameplay.references(p, 'recipes', 'casque')
    assert controller_tools.report(p)['catalogues']['endgame'] == len(p.content['endgame'])


def test_invalid_references_are_rejected_on_open(tmp_path):
    p = project(tmp_path)
    path = p.directory / 'content.json'
    value = json.loads(path.read_text())
    value['content']['endgame'] = [{**content.DEFAULTS['endgame'][0], 'target': 'missing_mob'}]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='espèce endgame'):
        Project(p.directory)


def test_class_duplication_accepts_same_identifier_format_as_rename(tmp_path):
    p = project(tmp_path)
    p.duplicate('classes', 'Knight', 'AuditKnight')
    p.save()
    assert any(item['id'] == 'AuditKnight' for item in Project(p.directory).content['templates']['classes'])


def test_documented_controller_module_has_headless_help():
    result = subprocess.run([sys.executable, '-m', 'jeuxRPG.multiplayer.controller', '--help'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'directory' in result.stdout


def test_interrupted_save_recovers_all_catalogs_on_next_open(tmp_path):
    p = project(tmp_path)
    original_disk = p.disk_state()
    environment = {**os.environ, 'PYTHONPATH': str(Path.cwd()) + os.pathsep + os.environ.get('PYTHONPATH', '')}
    code = """
import os
import sys
from jeuxRPG.multiplayer.controller_project import Project
p = Project(sys.argv[1])
p.content['world']['starting_gold'] = 999
original = os.replace
calls = 0
def interrupt(source, target):
    global calls
    original(source, target)
    calls += 1
    if calls == 2:
        os._exit(23)
os.replace = interrupt
p.save()
"""
    result = subprocess.run([sys.executable, '-c', code, str(p.directory)], env=environment, capture_output=True, text=True)
    assert result.returncode == 23, result.stderr
    assert (p.directory / '.controller-recovery').exists()
    reopened = Project(p.directory)
    assert reopened.disk_state() == original_disk
    assert reopened.content['world']['starting_gold'] == 100
    assert not (p.directory / '.controller-recovery').exists()
    reopened.save()


@pytest.mark.parametrize('fail', [False, True])
def test_builder_exports_copy_and_restores_globals(tmp_path, monkeypatch, fail):
    from jeuxRPG.multiplayer import editor_ui, map_building, map_editor
    p = project(tmp_path)
    destination = tmp_path / 'exported'
    disk = p.disk_state()
    previous = map_building.MOBS, map_editor.MOBS
    editors = []
    noop = lambda *args, **kwargs: None
    panel = SimpleNamespace(content=SimpleNamespace(pack_forget=noop), transient=noop, grab_set=noop, protocol=noop)
    monkeypatch.setattr(editor_ui, 'EditorPanel', lambda *args: panel)
    monkeypatch.setitem(sys.modules, 'tkinter', SimpleNamespace(filedialog=SimpleNamespace(askdirectory=lambda **kwargs: str(destination))))
    def create_editor(*args):
        if fail:
            raise RuntimeError('Builder failed')
        editor = SimpleNamespace(selected=SimpleNamespace(set=noop), status=SimpleNamespace(set=noop), refresh_choice=noop, draw=noop)
        editors.append(editor)
        return editor
    monkeypatch.setattr(map_editor, 'MapEditor', create_editor)
    screen = controller.Controller.__new__(controller.Controller)
    screen.project = p
    screen.tk = screen.ttk = screen.messagebox = screen.simpledialog = None
    screen.tables = {'maps': SimpleNamespace(selection=lambda: ())}
    screen.remember = screen.refresh = noop
    def export(window):
        editor = editors[0]
        editor.maps['clearing']['name'] = 'Exported clearing'
        editor.on_save(True)
        assert editor.saved['clearing']['name'] != 'Exported clearing'
    screen.root = SimpleNamespace(wait_window=export)
    if fail:
        with pytest.raises(RuntimeError, match='Builder failed'):
            screen.builder()
    else:
        screen.builder()
        assert Project(destination).maps['clearing']['name'] == 'Exported clearing'
        assert p.disk_state() == disk
        assert p.maps['clearing']['name'] == 'Exported clearing'
    assert map_building.MOBS is previous[0]
    assert map_editor.MOBS is previous[1]
