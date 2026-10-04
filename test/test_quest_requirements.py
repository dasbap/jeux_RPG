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
    assert 'niveau 5' in messages[0] and 'succès requis' in messages[0] and 'quête à terminer' in messages[0]
    p['characters']['p']['level'] = 5
    p['characters']['q']['level'] = 4
    p['quest'] = 'completed'
    p['achievements']['kills'] = 10
    assert len(content.missing_requirements(p,data['quests'][-1])) == 1
    p['characters']['q']['level'] = 5
    assert content.missing_requirements(p,data['quests'][-1]) == []
    assert 'Quête acceptée' in content.quest_dialogue(p,'mira')[0]
    p['characters']['q']['level'] = 1
    content.quest_event(p,'kill','goblin')
    assert 'Quête terminée' in content.quest_dialogue(p,'mira')[0]
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
    hunt = deepcopy(content.HUNT)
    hunt['requirements'] = {'level':2}
    monkeypatch.setattr(content,'HUNT',hunt)
    p = party()
    p.update(step='village',battle=None)
    messages, _ = tutorial.execute_one(p,'p','talk',{'npc':'mira'},0,lambda *args:RuntimeError(args),lambda:.5)
    assert p['step'] == 'village'
    assert p['quest'] != 'active'
    assert 'niveau 2' in messages[0]
