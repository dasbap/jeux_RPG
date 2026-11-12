from copy import deepcopy
from types import SimpleNamespace

import pytest

from jeuxRPG.multiplayer import forge, gameplay_catalog, tutorial, controller_gameplay
from jeuxRPG.multiplayer.service import GameError
from test_controller import project

RECIPES = ('casque', 'veste', 'gants', 'jambieres', 'bottes', 'ceinture')
SET = {'name':'Panoplie test', 'bonuses':{
    '2':{'hp':4,'endurance':1}, '4':{'force':2,'intelligence':2,'sagesse':1},
    '5':{'hp':8,'endurance':2,'sagesse':2},
}}


@pytest.fixture
def configured(monkeypatch):
    data = deepcopy(forge.GAMEPLAY)
    data['equipment_sets'] = {'test':deepcopy(SET)}
    for key in RECIPES:
        data['recipes'][key]['set_id'] = 'test'
    data['recipes']['outside'] = {**data['recipes']['gants'], 'name':'Hors panoplie', 'set_id':''}
    monkeypatch.setattr(forge, 'GAMEPLAY', data)
    monkeypatch.setattr(forge, 'RECIPES', data['recipes'])
    return data


def party():
    p = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}, {'id':'q','name':'Autre','class_name':'Mage'}])
    p.update(position='forge', quest='completed')
    p['inventory'] = {player:{item:10000 for item in forge.GAMEPLAY['materials']} for player in ('p','q')}
    return p


def expected_stats(p, base, player='p'):
    bonus = {stat:sum(row['bonuses'][stat] for row in forge.set_catalogue(p['equipment'].get(player, {}))) for stat in forge.BONUS_STATS}
    for stat in forge.BONUS_STATS:
        individual = sum(piece[stat] for piece in p['equipment'].get(player, {}).values())
        assert p['characters'][player]['stats'][stat]['max'] == base[stat]['max'] + individual + bonus[stat]


def test_thresholds_are_cumulative_and_upgrades_do_not_duplicate_bonus(configured):
    p = party()
    base = deepcopy(p['characters']['p']['stats'])
    for count, recipe in enumerate(RECIPES, 1):
        forge.execute(p, 'p', 'craft', recipe, GameError)
        row = forge.set_catalogue(p['equipment']['p'])[0]
        assert row['pieces'] == count
        assert [tier['pieces'] for tier in row['tiers'] if tier['active']] == [n for n in (2,4,5) if n<=count]
        expected_stats(p, base)
        saved = deepcopy(p)
        forge.migrate(p)
        forge.migrate(p)
        assert p == saved
    assert row['bonuses'] == {'hp':12,'endurance':3,'force':2,'intelligence':2,'sagesse':3}
    forge.execute(p, 'p', 'upgrade', 'veste', GameError)
    expected_stats(p, base)
    assert forge.set_catalogue(p['equipment']['p'])[0]['bonuses'] == row['bonuses']


def test_replacing_piece_removes_only_the_lost_threshold(configured):
    p = party()
    base = deepcopy(p['characters']['p']['stats'])
    for recipe in RECIPES[:5]:
        forge.execute(p, 'p', 'craft', recipe, GameError)
    forge.execute(p, 'p', 'craft', 'outside', GameError)
    row = forge.set_catalogue(p['equipment']['p'])[0]
    assert row['pieces'] == 4
    assert [tier['pieces'] for tier in row['tiers'] if tier['active']] == [2,4]
    assert row['bonuses']['hp'] == 4
    expected_stats(p, base)


def test_only_distinct_slots_on_same_character_count(configured):
    p = party()
    forge.execute(p, 'p', 'craft', 'casque', GameError)
    forge.execute(p, 'q', 'craft', 'veste', GameError)
    assert all(not tier['active'] for player in ('p','q') for tier in forge.set_catalogue(p['equipment'][player])[0]['tiers'])
    copies = {str(index): forge.piece('casque') for index in range(6)}
    assert forge.set_catalogue(copies)[0]['pieces'] == 1


def test_old_saves_gain_bonus_once_and_rebalance_removes_old_values(configured, monkeypatch):
    p = party()
    old_recipes = deepcopy(configured['recipes'])
    for definition in old_recipes.values(): definition.pop('set_id', None)
    with monkeypatch.context() as old:
        old.setattr(forge, 'RECIPES', old_recipes)
        old.setattr(forge, 'GAMEPLAY', {**configured, 'recipes':old_recipes, 'equipment_sets':{}})
        for recipe in RECIPES[:5]: forge.execute(p, 'p', 'craft', recipe, GameError)
    p.pop('equipment_set_bonuses')
    old_hp = p['characters']['p']['stats']['hp']['max']
    p['characters']['p']['stats']['hp']['current'] = 0
    forge.migrate(p)
    assert p['characters']['p']['stats']['hp']['max'] == old_hp + 12
    assert p['characters']['p']['stats']['hp']['current'] == 0
    saved = deepcopy(p)
    forge.migrate(p)
    assert p == saved
    configured['equipment_sets']['test']['bonuses']['5']['hp'] += 5
    forge.migrate(p)
    assert p['characters']['p']['stats']['hp']['max'] == old_hp + 17
    monkeypatch.setattr(forge, 'RECIPES', old_recipes)
    monkeypatch.setattr(forge, 'GAMEPLAY', {**configured, 'recipes':old_recipes, 'equipment_sets':{}})
    forge.migrate(p)
    assert p['characters']['p']['stats']['hp']['max'] == old_hp


@pytest.mark.parametrize('mutation', ['threshold','negative','fraction','unknown_stat','unknown_set','invalid_set_id'])
def test_invalid_sets_are_rejected(configured, mutation):
    data = deepcopy(configured)
    if mutation=='threshold': data['equipment_sets']['test']['bonuses']['3'] = {'hp':1}
    elif mutation=='negative': data['equipment_sets']['test']['bonuses']['2']['hp'] = -1
    elif mutation=='fraction': data['equipment_sets']['test']['bonuses']['2']['hp'] = 1.5
    elif mutation=='unknown_stat': data['equipment_sets']['test']['bonuses']['2']['damage'] = 1
    elif mutation=='unknown_set': data['recipes']['veste']['set_id'] = 'missing'
    else: data['recipes']['veste']['set_id'] = ['test']
    with pytest.raises(ValueError): gameplay_catalog.validate(data)


def test_builder_set_form_save_reload_and_reference_protection(tmp_path):
    p = project(tmp_path)
    answers = iter([{'id':'test','name':SET['name']}, *[SET['bonuses'][str(n)] for n in (2,4,5)]])
    ui = SimpleNamespace(project=p, form=lambda *args,**kwargs:deepcopy(next(answers)))
    identifier, definition = controller_gameplay.ControllerGameplayMixin.gameplay_form(ui,'equipment_sets',None,True)
    assert definition == SET
    controller_gameplay.change(p,'equipment_sets',identifier,definition,new=True)
    recipe = {**p.content['gameplay']['recipes']['veste'], 'set_id':identifier}
    controller_gameplay.change(p,'recipes','veste',recipe)
    assert controller_gameplay.references(p,'equipment_sets',identifier) == ['recettes/veste']
    with pytest.raises(ValueError):controller_gameplay.change(p,'equipment_sets',identifier,delete=True)
    p.save()
    from jeuxRPG.multiplayer.controller_project import Project
    reloaded = Project(p.directory)
    assert reloaded.content['gameplay']['equipment_sets'][identifier] == SET
    assert reloaded.content['gameplay']['recipes']['veste']['set_id'] == identifier


def test_legacy_catalog_has_no_implicit_sets():
    data = deepcopy(gameplay_catalog.DEFAULTS)
    del data['equipment_sets']
    assert gameplay_catalog.validate(data)['equipment_sets'] == {}
