from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from jeuxRPG.multiplayer import content, tutorial, progression, achievements, controller, map_building, map_editor


def project(tmp_path):
    return controller.Project(tmp_path/'maps')


def test_project_saves_and_reloads_all_catalogs(tmp_path):
    p = project(tmp_path)
    p.content['world']['repop_seconds'] = 240
    p.mobs['orc']['damage'] = 9
    p.maps['rosee']['sites'][0]['dialogue'] = 'Bienvenue !'
    p.save()
    loaded = controller.Project(p.directory)
    assert loaded.content['world']['repop_seconds'] == 240
    assert loaded.mobs['orc']['damage'] == 9
    assert loaded.maps['rosee']['sites'][0]['dialogue'] == 'Bienvenue !'
    assert loaded.state() == p.snapshot


def test_new_species_can_be_used_by_spawners_and_cannot_be_deleted_while_referenced(tmp_path):
    p = project(tmp_path)
    p.mobs['goblin_elite'] = {**deepcopy(p.mobs['goblin']), 'name':'Gobelin élite'}
    definition = next(data for data in p.maps.values() if data.get('spawners'))
    definition['spawners'][0]['mob_id'] = 'goblin_elite'
    p.save()
    p.mobs.pop('goblin_elite')
    with pytest.raises(ValueError):
        p.validate()
    assert map_building.MOBS.get('goblin_elite') is None


def test_invalid_quest_reference_does_not_write_any_catalog(tmp_path):
    p = project(tmp_path)
    before = {name:(p.directory/name).read_bytes() for name in ['world.json','mobs.json','content.json']}
    p.content['quests'].append({'id':'missing', 'name':'Test', 'npc':'absent', 'kind':'kill', 'target':'goblin', 'zone':'', 'count':1, 'reward_xp':50, 'description':'Test'})
    with pytest.raises(ValueError, match='introuvable'):
        p.save()
    assert all((p.directory/name).read_bytes() == data for name,data in before.items())


def test_save_rolls_back_on_partial_replace_failure(tmp_path, monkeypatch):
    p = project(tmp_path)
    before = {name:(p.directory/name).read_bytes() for name in ['world.json','mobs.json','content.json']}
    p.content['world']['repop_seconds'] = 200
    original = controller.os.replace
    count = 0
    def failing(source, destination):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('Disque indisponible')
        return original(source, destination)
    monkeypatch.setattr(controller.os, 'replace', failing)
    with pytest.raises(OSError):
        p.save()
    assert all((p.directory/name).read_bytes() == data for name,data in before.items())
    assert not list(p.directory.glob('*.controller.tmp'))


@pytest.mark.parametrize('change', ['duplicate','condition','nonfinite','vision','hunt'])
def test_invalid_content_is_rejected(change):
    data = deepcopy(content.DEFAULTS)
    if change == 'duplicate':
        data['quests'].append(deepcopy(data['quests'][0]))
    elif change == 'condition':
        data['achievements'][0]['condition'] = 'eval'
    elif change == 'nonfinite':
        data['world']['xp_exponent'] = float('nan')
    elif change == 'vision':
        data['world']['player_vision'] = 2.5
    else:
        data['quests'] = []
    with pytest.raises(ValueError):
        content.validate_content(data)


def test_custom_kill_and_craft_quests_progress_and_reward_only_once(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    data['quests'] += [
        {'id':'hunt_extra', 'name':'Chasse', 'npc':'guide', 'kind':'kill', 'target':'orc', 'zone':'lisiere', 'count':2, 'reward_xp':75, 'description':'Battez les orcs.'},
        {'id':'craft_extra', 'name':'Artisan', 'npc':'guide', 'kind':'craft', 'target':'casque', 'zone':'', 'count':1, 'reward_xp':25, 'description':'Fabriquez un casque.'},
    ]
    monkeypatch.setattr(content, 'DATA', data)
    party = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}])
    messages = content.quest_dialogue(party, 'guide')
    assert len(messages) == 2
    content.quest_event(party, 'kill', 'goblin', 'lisiere')
    content.quest_event(party, 'kill', 'orc', 'rosee')
    assert party['custom_quests']['hunt_extra']['progress'] == 0
    content.quest_event(party, 'kill', 'orc', 'lisiere')
    content.quest_event(party, 'kill', 'orc', 'lisiere')
    content.quest_event(party, 'craft', 'casque')
    initial = party['characters']['p']['exp']
    assert len(content.quest_dialogue(party, 'guide')) == 2
    assert party['characters']['p']['exp'] == initial+100
    assert content.quest_dialogue(party, 'guide') == []
    assert len(content.quest_journal(party)) == 2


def test_success_definition_controls_speed_threshold_and_title(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    fast = next(a for a in data['achievements'] if a['condition'] == 'fast')
    fast.update(threshold=10, title='Fulgurant')
    monkeypatch.setattr(content, 'DATA', data)
    party = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}])
    party.update(battle={'initial_mobs':1, 'initial_players':1, 'started_at':0}, mobs=[])
    achievements.victory(party, 30)
    assert 'Fulgurant' in achievements.view(party)['unlocked_titles']
    assert 'Éclair de la lisière' not in achievements.view(party)['unlocked_titles']


def test_world_xp_curve_and_merchant_schedule_are_used(monkeypatch):
    settings = {**content.WORLD, 'xp_base':1000, 'xp_exponent':2, 'merchant_stay_hours':1}
    monkeypatch.setattr(progression, 'WORLD', settings)
    monkeypatch.setattr(content, 'WORLD', settings)
    assert progression.required(3) == 9000
    assert tutorial.npc(3599)['location'] == 'Rosée'
    assert tutorial.npc(3601)['travelling']


def test_builder_save_delegates_to_controller():
    editor = map_editor.MapEditor.__new__(map_editor.MapEditor)
    calls = []
    editor.on_save = lambda choose: calls.append(choose)
    editor.save(True)
    assert calls == [True]


def test_saved_project_is_loaded_by_game_in_separate_process(tmp_path):
    import os
    import subprocess
    import sys
    p = project(tmp_path)
    p.content['world']['repop_seconds'] = 321
    p.content['quests'][0].update(count=5, reward_xp=444)
    p.mobs['goblin_elite'] = {**deepcopy(p.mobs['goblin']), 'name':'Élite', 'damage':7}
    definition = next(data for data in p.maps.values() if data.get('spawners'))
    definition['spawners'][0]['mob_id'] = 'goblin_elite'
    p.save()
    code = 'from jeuxRPG.multiplayer import content, fields, map_building; assert content.WORLD["repop_seconds"] == 321; assert content.HUNT["count"] == 5; assert map_building.MOBS["goblin_elite"]["damage"] == 7; assert any(s["mob_id"] == "goblin_elite" for d in fields.MAPS.values() for s in d.get("spawners", []))'
    result = subprocess.run([sys.executable, '-c', code], env={**os.environ, 'RPG_MAPS_FILE':str(p.directory)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_tutorial_quest_can_be_renamed_with_number_suffix_and_reloaded(tmp_path):
    p = project(tmp_path)
    p.rename('quests', 'mira_hunt', 'mira_hunt_2')
    p.save()
    loaded = controller.Project(p.directory)
    hunt = next(q for q in loaded.content['quests'] if content.is_hunt(q))
    assert hunt['id'] == 'mira_hunt_2'
    assert hunt['role'] == 'tutorial_hunt'
    assert hunt['previous_ids'] == ['mira_hunt']
    assert hunt['npc'] == 'mira'


def test_new_quest_name_and_id_accept_underscores_and_digits(tmp_path):
    p = project(tmp_path)
    p.content['quests'].append({'id':'mira_hunt_2','name':'mira_hunt_2','npc':'mira','kind':'kill','target':'goblin','zone':'lisiere','count':2,'reward_xp':50,'description':'Une nouvelle chasse.'})
    p.save()
    assert len(controller.Project(p.directory).content['quests']) == 2


def test_rename_updates_species_spawners_and_npc_quest_references(tmp_path):
    p = project(tmp_path)
    data = p.maps['rosee']
    data['sites'].append({'id':'guide','name':'Guide','dialogue':'Bonjour','position':[3,20]})
    p.content['quests'].append({'id':'quest_2','name':'Chasse','npc':'guide','kind':'kill','target':'orc','zone':'','count':1,'reward_xp':50,'description':'Une chasse.'})
    definition = next(data for data in p.maps.values() if data.get('spawners'))
    definition['spawners'][0]['mob_id'] = 'orc'
    p.rename('mobs', 'orc', 'orc_2')
    p.rename('npcs', 'guide', 'guide_2')
    assert definition['spawners'][0]['mob_id'] == 'orc_2'
    assert p.content['quests'][-1]['target'] == 'orc_2'
    assert p.content['quests'][-1]['npc'] == 'guide_2'
    p.save()
    loaded = controller.Project(p.directory)
    assert 'orc_2' in loaded.mobs and 'orc' not in loaded.mobs


def test_quest_rename_migrates_completed_progress_without_second_reward(tmp_path, monkeypatch):
    p = project(tmp_path)
    p.content['quests'].append({'id':'quest_2','name':'Chasse','npc':'mira','kind':'kill','target':'orc','zone':'','count':1,'reward_xp':50,'description':'Une chasse.'})
    p.rename('quests', 'quest_2', 'quest_3')
    p.rename('quests', 'quest_3', 'quest_4')
    monkeypatch.setattr(content, 'DATA', p.content)
    party = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}])
    party['custom_quests'] = {'quest_2':{'status':'completed','progress':1}, 'quest_4':{'status':'active','progress':0}}
    xp = party['characters']['p']['exp']
    assert content.quest_dialogue(party, 'mira') == []
    assert party['characters']['p']['exp'] == xp
    assert party['custom_quests'] == {'quest_4':{'status':'completed','progress':1}}
    assert content.quest_journal(party)[0]['id'] == 'quest_4'


@pytest.mark.parametrize('replacement', ['mira_hunt','invalid id','BadID',''])
def test_invalid_or_duplicate_rename_is_atomic(tmp_path, replacement):
    p = project(tmp_path)
    before = p.state()
    with pytest.raises(ValueError):
        p.rename('achievements', 'silent', 'untouched' if replacement == 'mira_hunt' else replacement)
    assert p.state() == before


def test_edit_form_allows_tutorial_quest_id_change(tmp_path):
    p = project(tmp_path)
    screen = controller.Controller.__new__(controller.Controller)
    screen.project = p
    screen.root = None
    screen.history = []
    screen.tables = {'quests':SimpleNamespace(selection=lambda:['mira_hunt'])}
    screen.form = lambda title, values, choices: {**values, 'id':'mira_hunt_2'}
    screen.edit_requirements = lambda initial: initial
    screen.refresh = lambda: None
    screen.status = SimpleNamespace(set=lambda value: None)
    screen.messagebox = SimpleNamespace(showerror=lambda *args, **kwargs: pytest.fail(str(args)))
    screen.edit('quests')
    assert p.content['quests'][0]['id'] == 'mira_hunt_2'
    assert content.is_hunt(p.content['quests'][0])
    assert len(screen.history) == 1


def test_installed_game_starts_with_renamed_tutorial_quest(tmp_path):
    import os
    import subprocess
    import sys
    p = project(tmp_path)
    p.rename('quests', 'mira_hunt', 'mira_hunt_2')
    p.save()
    code = 'from jeuxRPG.multiplayer import content, tutorial; assert content.HUNT["id"] == "mira_hunt_2"; party = tutorial.new_party([{"id":"p","name":"Test","class_name":"Knight"}]); assert content.quest_dialogue(party, "mira") == []; assert content.quest_journal(party) == []'
    result = subprocess.run([sys.executable, '-c', code], env={**os.environ, 'RPG_MAPS_FILE':str(p.directory)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
