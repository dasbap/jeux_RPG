from copy import deepcopy

import pytest

from jeuxRPG.multiplayer import content, tutorial
from test_controller import project


def quest(identifier='second', requirements=None):
    return {'id':identifier,'name':identifier,'npc':'mira','kind':'kill','target':'goblin','zone':'','count':1,'reward_xp':0,'description':'Test','requirements':requirements or {}}


def party():
    return tutorial.new_party([{'id':'p','name':'Premier','class_name':'Knight'},{'id':'q','name':'Second','class_name':'Mage'}])


def test_all_requirements_gate_acceptance_and_explain_missing(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    data['quests'].append(quest(requirements={'level':5,'achievements':['kills_10'],'quests':['mira_hunt']}))
    monkeypatch.setattr(content,'DATA',data)
    p = party()
    messages = content.quest_dialogue(p,'mira')
    assert 'second' not in p['custom_quests']
    assert any('niveau 5' in message and 'succès requis' in message and 'quête à terminer' in message for message in messages)
    p['characters']['p']['level'] = 5
    p['characters']['q']['level'] = 4
    p['custom_quests']['mira_hunt'] = {'status': 'completed', 'progress': 3}
    p['achievements']['kills'] = 10
    assert len(content.missing_requirements(p,data['quests'][-1])) == 1
    p['characters']['q']['level'] = 5
    assert content.missing_requirements(p,data['quests'][-1]) == []
    assert any('Quête acceptée : second' in message for message in content.quest_dialogue(p,'mira'))
    p['characters']['q']['level'] = 1
    content.quest_event(p,'kill','goblin')
    assert any('Quête terminée : second' in message for message in content.quest_dialogue(p,'mira'))
    assert content.quest_dialogue(p,'mira') == []


def test_completed_custom_quest_and_combat_achievement_unlock_next(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    data['quests'] += [quest('first'),quest(requirements={'quests':['first'],'achievements':['silent']})]
    monkeypatch.setattr(content,'DATA',data)
    p = party()
    p['custom_quests'] = {'first':{'status':'completed','progress':1}}
    p['achievements'] = {'kills':0,'max_level':1,'zones':[],'best_seconds':None,'titles':['Ombre silencieuse']}
    assert content.missing_requirements(p,data['quests'][-1]) == []
    content.quest_dialogue(p,'mira')
    assert p['custom_quests']['second']['status'] == 'active'


@pytest.mark.parametrize('requirements', [{'level':0},{'level':True},{'level':101},{'quests':['missing']},{'achievements':['missing']},{'quests':['second']},{'achievements':['silent','silent']},{'other':1}])
def test_invalid_requirements_rejected(requirements):
    data = deepcopy(content.DEFAULTS)
    data['quests'].append(quest(requirements=requirements))
    with pytest.raises(ValueError):
        content.validate_content(data)


def test_cycles_rejected_and_renaming_updates_requirements(tmp_path):
    p = project(tmp_path)
    p.content['quests'] += [quest('first'),quest(requirements={'quests':['first'],'achievements':['silent']})]
    p.rename('quests','first','first_2')
    p.rename('achievements','silent','silent_2')
    requirements = p.content['quests'][-1]['requirements']
    assert requirements == {'quests':['first_2'],'achievements':['silent_2']}
    p.save()
    first = next(q for q in p.content['quests'] if q['id'] == 'first_2')
    first['requirements'] = {'quests':['second']}
    with pytest.raises(ValueError,match='Cycle'):
        p.validate()


def test_tutorial_quest_is_checked_by_server_before_state_changes(monkeypatch):
    data = deepcopy(content.DATA)
    next(quest for quest in data['quests'] if quest.get('category') == 'tutorial')['requirements'] = {'level':2}
    monkeypatch.setattr(content,'DATA',data)
    p = party()
    p.update(step='village',position='mira',battle=None)
    messages, _ = tutorial.execute_one(p,'p','talk',{'npc':'mira'},0,lambda *args:RuntimeError(args),lambda:.5)
    assert p['step'] == 'village'
    assert p['quest'] != 'active'
    assert any('niveau 2' in message for message in messages)


def test_tutorial_category_uses_the_same_quest_lifecycle(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    ordinary = {**deepcopy(data['quests'][0]), 'id': 'ordinary_hunt', 'category': 'standard'}
    data['quests'].append(ordinary)
    monkeypatch.setattr(content, 'DATA', data)
    p = party()
    messages = content.quest_dialogue(p, 'mira')
    assert sum(message.startswith('Quête acceptée') for message in messages) == 2
    for _ in range(data['quests'][0]['count']):
        content.quest_event(p, 'kill', 'goblin', 'lisiere')
    states = p['custom_quests']
    assert states[data['quests'][0]['id']]['progress'] == states['ordinary_hunt']['progress']
    rewards = content.quest_dialogue(p, 'mira')
    assert sum(message.startswith('Quête terminée') for message in rewards) == 2
    assert states[data['quests'][0]['id']]['status'] == states['ordinary_hunt']['status'] == 'completed'
    assert {item['id'] for item in content.quest_journal(p)} == {data['quests'][0]['id'], 'ordinary_hunt'}
    assert content.quest_dialogue(p, 'mira') == []


def test_catalogue_does_not_require_any_tutorial_quest():
    data = deepcopy(content.DEFAULTS)
    data['quests'] = []
    assert content.validate_content(data)['quests'] == []


def equipment_chain(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    craft = {**quest('craft_veste'), 'kind':'craft', 'target':'veste', 'npc':'forge', 'name':'Fabriquer la veste'}
    upgrade = {**quest('upgrade_veste', {'quests':['craft_veste']}), 'kind':'upgrade', 'target':'veste', 'npc':'forge', 'upgrade_level':1}
    # Builder ordering must not affect the dependency order.
    data['quests'] = [upgrade, craft]
    monkeypatch.setattr(content, 'DATA', data)
    return craft, upgrade


def test_equipment_already_owned_unlocks_chain_only_after_turn_in(monkeypatch):
    craft, upgrade = equipment_chain(monkeypatch)
    p = party()
    p['equipment'] = {'p': {'torso': {'recipe':'veste', 'level':1}}}
    content.quest_dialogue(p, 'forge')
    assert p['custom_quests'][craft['id']] == {'status':'active', 'progress':1}
    assert upgrade['id'] not in p['custom_quests']
    messages = content.quest_dialogue(p, 'forge')
    assert p['custom_quests'][craft['id']]['status'] == 'completed'
    assert p['custom_quests'][upgrade['id']] == {'status':'active', 'progress':1}
    assert sum(line.startswith('Quête terminée') for line in messages) == 1
    assert sum(line.startswith('Quête terminée') for line in content.quest_dialogue(p, 'forge')) == 1
    assert content.quest_dialogue(p, 'forge') == []


def test_existing_followup_cannot_progress_or_reward_before_prerequisite(monkeypatch):
    craft, upgrade = equipment_chain(monkeypatch)
    p = party()
    p['custom_quests'] = {
        craft['id']: {'status':'active','progress':1},
        upgrade['id']: {'status':'active','progress':0},
    }
    content.quest_event(p, 'upgrade', 'veste', level=1)
    assert p['custom_quests'][upgrade['id']]['progress'] == 0
    locked = next(q for q in content.quest_journal(p) if q['id'] == upgrade['id'])
    assert locked['status'] == 'locked'
    assert 'Fabriquer la veste' in locked['missing_requirements'][0]
    p['equipment'] = {'p': {'torso': {'recipe':'veste', 'level':1}}}
    messages = content.quest_dialogue(p, 'forge')
    completed = [message for message in messages if message.startswith('Quête terminée')]
    assert len(completed) == 2
    assert 'Fabriquer la veste' in completed[0]
    assert all(state['status']=='completed' for state in p['custom_quests'].values())
