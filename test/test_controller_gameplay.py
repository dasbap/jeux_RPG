from copy import deepcopy
import json
import os
import subprocess
import sys

import pytest

from jeuxRPG.multiplayer import controller_gameplay, gameplay_catalog
from jeuxRPG.multiplayer.controller import Controller, Project
from test_controller import project


@pytest.mark.parametrize('path,value', [
    (('rules', 'time', 'game_ratio'), 0),
    (('rules', 'time', 'game_ratio'), float('nan')),
    (('rules', 'forge', 'max_level'), 2.5),
    (('rules', 'social', 'realm_capacity'), True),
    (('recipes', 'veste', 'cost', 'peau'), -1),
    (('recipes', 'veste', 'slot'), 'missing'),
    (('materials', 'peau', 'rare_chance'), 2),
    (('rules', 'time', 'energy_regen_min'), 100),
    (('rules', 'encounters', 'factor_min'), 9),
    (('rules', 'travel', 'segment_random_fraction'), 1),
    (('rules', 'combat', 'level_xp_divisor'), .1),
    (('summon_control', 'Squelette', 'per_second'), -1),
])
def test_invalid_gameplay_cannot_replace_project(tmp_path, path, value):
    p = project(tmp_path)
    before = p.state()
    document = p.document()
    target = document['content']['gameplay']
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        p.replace_document(document)
    assert p.state() == before


def test_catalog_creation_references_and_atomic_deletion(tmp_path):
    p = project(tmp_path)
    controller_gameplay.change(p, 'materials', 'minerai', {'name': 'Minerai bleu', 'rare_chance': .5}, new=True)
    controller_gameplay.change(p, 'slots', 'finger', 'Doigt', new=True)
    recipe = {'name': 'Anneau bleu', 'adjective': 'brillant', 'slot': 'finger', 'cost': {'minerai': 2}, 'hp': 12}
    before_recipe = controller_gameplay.change(p, 'recipes', 'anneau', recipe, new=True)
    assert controller_gameplay.references(p, 'materials', 'minerai') == ['recettes/anneau']
    assert controller_gameplay.references(p, 'slots', 'finger') == ['recettes/anneau']
    saved = p.state()
    with pytest.raises(ValueError):
        controller_gameplay.change(p, 'materials', 'minerai', delete=True)
    assert p.state() == saved
    p.restore(before_recipe)
    assert 'anneau' not in p.content['gameplay']['recipes']
    p.restore(saved)
    p.save()
    assert Project(p.directory).state() == p.snapshot
    for section in ('recipes', 'materials', 'slots', 'rules', 'rare_costs', 'encounter_chain', 'summon_control', 'xp_classes', 'story'):
        assert controller_gameplay.rows(p, section)


def test_recipe_quest_and_control_references_are_local_to_project(tmp_path):
    p = project(tmp_path)
    recipe = deepcopy(p.content['gameplay']['recipes']['casque'])
    controller_gameplay.change(p, 'recipes', 'coiffe', recipe, new=True)
    p.content['quests'].append({'id': 'coiffe_quest', 'name': 'Coiffe', 'npc': 'mira', 'kind': 'craft', 'target': 'coiffe', 'zone': '', 'count': 1, 'reward_xp': 20, 'description': 'Fabriquez une coiffe.'})
    p.validate()
    with pytest.raises(ValueError):
        controller_gameplay.change(p, 'recipes', 'coiffe', delete=True)
    before = p.state()
    with pytest.raises(ValueError):
        controller_gameplay.change(p, 'summon_control', 'Knight', {'energy': 'Aura', 'per_second': 1.}, new=True)
    assert p.state() == before
    p.rename('classes', 'Squelette', 'squelette_bleu')
    assert 'squelette_bleu' in p.content['gameplay']['summon_control']
    assert 'Squelette' not in p.content['gameplay']['summon_control']


def test_saved_project_drives_forge_clock_movement_and_encounters(tmp_path):
    p = project(tmp_path)
    data = p.content['gameplay']
    data['materials']['peau']['name'] = 'Cuir du contrôleur'
    data['materials']['cristal_gobelin']['rare_chance'] = .7
    data['rules']['forge'].update(max_level=2, hp_per_level=4)
    data['recipes']['veste'].update(name='Armure du contrôleur', hp=23, cost={'peau': 1})
    data['rules']['time']['game_ratio'] = 2.
    data['rules']['movement']['walking_kmh'] = 12.
    data['rules']['movement']['move_seconds'] = .7
    data['rules']['social'].update(team_capacity=3, realm_capacity=30)
    data['rules']['bleeding'].update(ticks=5, damage_min=9)
    data['xp_classes']['elite'] = 7.
    p.mobs['orc']['xp_class'] = 'elite'
    data['encounter_chain'] = [1., 1.]
    data['story']['clearing']['description'] = 'Bienvenue dans mon aventure.'
    data['rules']['start'].update(x=1, y=9)
    p.save()
    program = '''
import json
import math
from jeuxRPG.multiplayer import tutorial, forge, progression, world, fields, encounters, bleeding
from jeuxRPG.multiplayer.clock import GameClock
from jeuxRPG.multiplayer.accounts import SOCIAL_RULES
from jeuxRPG.multiplayer.service import GameError
from jeuxRPG.multiplayer.mob_rules import CLASS_XP
p = tutorial.new_party([{'id':'p0','name':'Test','class_name':'Knight'}])
fields.start(p, 0)
assert p['battle']['players']['p0']['position'] == [1,9]
p.update(position='forge', quest='completed', step='craft', battle=None, mobs=[], mob=None)
p['inventory']['p0'] = {'peau':100, 'cristal_gobelin':100, 'noyau_gobelin':100}
base_hp = p['characters']['p0']['stats']['hp']['max']
forge.execute(p, 'p0', 'craft', 'veste', GameError)
forge.execute(p, 'p0', 'upgrade', 'veste', GameError)
forge.execute(p, 'p0', 'upgrade', 'veste', GameError)
assert p['equipment']['p0']['torso']['hp'] == 31
assert p['characters']['p0']['stats']['hp']['max'] == base_hp + 31
assert p['inventory']['p0']['peau'] == 89
assert p['equipment']['p0']['torso']['name'] == 'Armure du contrôleur solide'
try:
 forge.execute(p, 'p0', 'upgrade', 'veste', GameError)
 raise AssertionError('Maximum ignoré')
except GameError as e:
 assert e.code == 'max_upgrade'
v = tutorial.view(p, 'p0', 0)
assert v['material_names']['peau'] == 'Cuir du contrôleur'
assert all(r['max_level'] == 2 for r in v['players'][0]['forge'])
assert progression.RATIO == GameClock.ratio == 2
ticks = [0]
clock = GameClock(0, monotonic=lambda:ticks[0], wall=lambda:0)
ticks[0] = 5
assert clock.now() == 10
assert tutorial.tactics.MOVE_TIME == .7
assert math.isclose(world.walking_seconds('clearing','clearing_rosee'),45)
assert SOCIAL_RULES['team_capacity'] == 3 and SOCIAL_RULES['realm_capacity'] == 30
assert CLASS_XP['elite'] == 7
assert encounters.group_size('D',1,1,lambda:0) == 2
assert forge.RARE_DROPS['cristal_gobelin'] == .7
mob = {}
bleeding.apply(mob, 'p0', 10, 0)
assert mob['bleeding'][0]['damage'] == 9 and mob['bleeding'][0]['ticks'] == 5
assert tutorial.STEPS['clearing'][1] == 'Bienvenue dans mon aventure.'
print(json.dumps({'ok':True}))
'''
    environment = {**os.environ, 'RPG_MAPS_FILE': str(p.directory), 'RPG_CONTENT_FILE': str(p.directory / 'content.json'), 'RPG_CLASSES_FILE': str(p.directory / 'classes.json')}
    result = subprocess.run([sys.executable, '-c', program], env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['ok']


def test_old_catalogs_receive_balanced_gameplay_defaults(tmp_path):
    p = project(tmp_path)
    raw = json.loads((p.directory / 'content.json').read_text())
    raw['content'].pop('gameplay', None)
    (p.directory / 'content.json').write_text(json.dumps(raw))
    loaded = Project(p.directory)
    assert loaded.content['gameplay'] == gameplay_catalog.DEFAULTS


@pytest.mark.skipif(sys.platform != 'win32', reason='Tk réel vérifié par le builder Windows')
def test_graphical_controller_exposes_every_gameplay_catalog(tmp_path):
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        screen = Controller(root, project(tmp_path))
        root.update_idletasks()
        assert all(section in screen.tables for section, _ in controller_gameplay.SECTIONS)
        for section, _ in controller_gameplay.SECTIONS:
            assert screen.tables[section].get_children()
        screen.root.update()
        assert all(screen.label(key) != key for group in screen.project.content['gameplay']['rules'].values() for key in group if key not in ('map','x','y'))
    finally:
        root.destroy()


def test_equipment_rebalance_is_idempotent_and_preserves_removed_recipes(monkeypatch):
    from jeuxRPG.multiplayer import forge, tutorial
    p = tutorial.new_party([{'id': 'p', 'name': 'Test', 'class_name': 'Knight'}])
    p['quest'] = 'completed'
    p['position'] = 'forge'
    p['inventory']['p'] = {'peau': 100, 'croc': 100}
    from jeuxRPG.multiplayer.service import GameError
    forge.execute(p, 'p', 'craft', 'veste', GameError)
    before = deepcopy(p['characters']['p']['stats'])
    recipes = deepcopy(forge.RECIPES)
    recipes['veste'].update(name='Veste renforcée', hp=recipes['veste']['hp'] + 10, slot='head')
    monkeypatch.setattr(forge, 'RECIPES', recipes)
    monkeypatch.setattr(forge, 'GAMEPLAY', {**forge.GAMEPLAY, 'recipes': recipes})
    forge.migrate(p)
    assert p['characters']['p']['stats']['hp']['max'] == before['hp']['max'] + 10
    assert p['equipment']['p']['torso']['name'] == 'Veste renforcée'
    saved = deepcopy(p)
    forge.migrate(p)
    assert p == saved
    assert next(item for item in forge.catalogue(p, 'p') if item['recipe'] == 'veste')['equipped']
    with pytest.raises(GameError, match='déjà équipée'):
        forge.execute(p, 'p', 'craft', 'veste', GameError)
    forge.execute(p, 'p', 'upgrade', 'veste', GameError)
    assert p['equipment']['p']['torso']['level'] == 1
    recipes.pop('veste')
    saved = deepcopy(p)
    forge.migrate(p)
    assert p == saved


def test_equipment_replacement_subtracts_old_bonus_and_keeps_hp_nonnegative(monkeypatch):
    from jeuxRPG.multiplayer import forge, tutorial
    from jeuxRPG.multiplayer.service import GameError
    p = tutorial.new_party([{'id': 'p', 'name': 'Test', 'class_name': 'Knight'}])
    p['quest'] = 'completed'
    p['position'] = 'forge'
    p['inventory']['p'] = {'peau': 100, 'croc': 100}
    baseline = p['characters']['p']['stats']['hp']['max']
    forge.execute(p, 'p', 'craft', 'veste', GameError)
    recipes = deepcopy(forge.RECIPES)
    recipes['tunique'] = {**recipes['veste'], 'name': 'Tunique', 'hp': 0}
    monkeypatch.setattr(forge, 'RECIPES', recipes)
    monkeypatch.setattr(forge, 'GAMEPLAY', {**forge.GAMEPLAY, 'recipes': recipes})
    p['characters']['p']['stats']['hp']['current'] = 1
    forge.execute(p, 'p', 'craft', 'tunique', GameError)
    assert p['characters']['p']['stats']['hp']['max'] == baseline
    assert p['characters']['p']['stats']['hp']['current'] == 0
    assert p['equipment']['p']['torso']['recipe'] == 'tunique'


@pytest.mark.skipif(sys.platform != 'win32', reason='Formulaire Tk vérifié sous Windows')
def test_controller_large_form_scrolls_and_keeps_apply_visible(tmp_path):
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.withdraw()
    failures = []
    try:
        screen = Controller(root, project(tmp_path))
        values = {f'field_{index}': index for index in range(40)}
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        def apply():
            dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
            try:
                children = list(widgets(dialog))
                canvas = next(child for child in children if isinstance(child, tk.Canvas))
                root.update_idletasks()
                canvas.yview_moveto(1)
                assert canvas.yview()[0] > 0
                button = next(child for child in children if isinstance(child, ttk.Button) and child.cget('text') == 'Appliquer')
                assert button.winfo_ismapped()
                button.invoke()
            except Exception as error:
                failures.append(error)
                dialog.destroy()
        root.after(30, apply)
        assert screen.form('Formulaire long', values) == values
        assert failures == []
    finally:
        root.destroy()
