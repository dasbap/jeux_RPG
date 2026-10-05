from copy import deepcopy

import pytest

from jeuxRPG.multiplayer import achievements, content, tutorial, tactics
from test_controller import project
from test_tactics import party


def definition(identifier='scoped', **values):
    return {'id': identifier, 'name': identifier, 'title': 'Titre ' + identifier, 'condition': 'kills', 'threshold': 666, **values}


def configure(monkeypatch, *definitions):
    data = deepcopy(content.DATA)
    data['achievements'] = list(definitions)
    monkeypatch.setattr(content, 'DATA', data)
    return data


def test_kills_can_combine_species_zone_and_precise_map(monkeypatch):
    goal = definition(target='goblin', zone='lisiere', map='hunt')
    configure(monkeypatch, goal)
    p = party()
    p.update(position='hunt', field_map='hunt')
    for _ in range(665):
        achievements.event(p, 'kills', 'goblin')
    achievements.event(p, 'kills', 'orc')
    p.update(position='forest', field_map='forest')
    achievements.event(p, 'kills', 'goblin')
    p.update(position='clearing', field_map='clearing')
    achievements.event(p, 'kills', 'goblin')
    assert achievements.progress(p, goal) == 665
    assert not achievements.unlocked(p, goal)
    p.update(position='hunt', field_map='hunt')
    achievements.event(p, 'kills', 'goblin')
    assert achievements.unlocked(p, goal)
    assert achievements.view(p)['kills'] == 669
    assert 'counters' not in achievements.view(p)


@pytest.mark.parametrize('filters,expected', [({}, 4), ({'target':'goblin'}, 3), ({'zone':'lisiere'}, 2), ({'map':'hunt'}, 2), ({'target':'orc','zone':'lisiere','map':'hunt'}, 1)])
def test_counter_filter_combinations(monkeypatch, filters, expected):
    goal = definition(**filters)
    configure(monkeypatch, goal)
    p = party()
    for map_id, mob in [('hunt','goblin'), ('hunt','orc'), ('forest','goblin'), ('clearing','goblin')]:
        p.update(position=map_id, field_map=map_id)
        achievements.event(p, 'kills', mob)
    assert achievements.progress(p, goal) == expected


def test_training_does_not_count_and_old_totals_are_not_invented(monkeypatch):
    scoped = definition(target='goblin')
    total = definition('total')
    configure(monkeypatch, scoped, total)
    p = party()
    p['achievements'] = {'kills': 100}
    assert achievements.progress(p, total) == 100
    assert achievements.progress(p, scoped) == 0
    p['training'] = True
    achievements.event(p, 'kills', 'goblin')
    assert achievements.progress(p, total) == 100


def test_filtered_combat_achievement_counts_only_complete_matching_victories(monkeypatch):
    goal = definition(condition='untouched', threshold=2, target='goblin', zone='lisiere')
    configure(monkeypatch, goal)
    p = party()
    p.update(position='hunt', field_map='hunt')
    for index in range(2):
        p['mobs'] = []
        p['battle'].update(awarded=False, started_at=0, damage_received=False, initial_mobs=1)
        p['battle']['defeated_targets'] = []
        achievements.event(p, 'kills', 'goblin')
        achievements.victory(p, 30)
        assert achievements.progress(p, goal) == index + 1
        assert achievements.unlocked(p, goal) == (index == 1)
        achievements.victory(p, 60)
        assert achievements.progress(p, goal) == index + 1
    p['battle'].update(awarded=False, damage_received=True)
    achievements.victory(p, 90)
    assert achievements.progress(p, goal) == 2


def test_title_collision_cannot_unlock_another_achievement(monkeypatch):
    easy = definition('easy', condition='fast', threshold=30, title='Même titre')
    hard = definition('hard', condition='fast', threshold=1, title='Même titre')
    configure(monkeypatch, easy, hard)
    p = party()
    p['mobs'] = []
    achievements.victory(p, 30)
    assert achievements.unlocked(p, easy)
    assert not achievements.unlocked(p, hard)
    easy.update(id='easy_2', previous_ids=['easy'], title='Titre renommé')
    assert achievements.unlocked(p, easy)
    assert 'Titre renommé' in achievements.view(p)['unlocked_titles']


def test_quest_requirements_use_scoped_achievement(monkeypatch):
    goal = definition(target='goblin', threshold=2)
    data = configure(monkeypatch, goal)
    q = {'requirements': {'achievements': ['scoped']}}
    p = party()
    achievements.event(p, 'kills', 'orc')
    achievements.event(p, 'kills', 'goblin')
    assert content.missing_requirements(p, q)
    achievements.event(p, 'kills', 'goblin')
    assert content.missing_requirements(p, q) == []


def test_craft_quest_and_discovery_conditions(monkeypatch):
    goals = [definition('craft',condition='craft',target='veste',threshold=1), definition('quest',condition='quests',target='mira_hunt',threshold=1), definition('visit',condition='discover',zone='lisiere',threshold=1), definition('map',condition='discover',map='hunt',threshold=1)]
    configure(monkeypatch,*goals)
    p = party()
    p.update(position='hunt',field_map='hunt',visited=['lisiere'])
    achievements.event(p,'craft','veste')
    achievements.event(p,'quests','mira_hunt')
    assert all(achievements.unlocked(p,goal) for goal in goals)


@pytest.mark.parametrize('values', [{'target':'missing'}, {'zone':'missing'}, {'map':'missing'}, {'zone':'rosee','map':'hunt'}, {'condition':'level','target':'goblin'}, {'condition':'kills','threshold':1.5}, {'condition':'discover','map':'hunt','threshold':2}])
def test_invalid_scope_prevents_saving(tmp_path,values):
    p = project(tmp_path)
    before = (p.directory/'content.json').read_bytes()
    p.content['achievements'].append(definition(**values))
    with pytest.raises(ValueError):
        p.save()
    assert (p.directory/'content.json').read_bytes() == before


def test_scope_references_follow_renames_and_block_deletion(tmp_path):
    p = project(tmp_path)
    p.content['achievements'].append(definition(target='orc',zone='rosee',map='cave_2'))
    p.rename('mobs','orc','orc_2')
    p.rename('maps','cave_2','salle_2')
    assert p.content['achievements'][-1]['target'] == 'orc_2'
    assert p.content['achievements'][-1]['map'] == 'salle_2'
    p.save()
    p.mobs.pop('orc_2')
    with pytest.raises(ValueError,match='cible'):
        p.save()


def test_actual_death_records_species_only_once_for_scoped_progress(monkeypatch):
    goal = definition(target='goblin',threshold=1)
    configure(monkeypatch, goal)
    p = party()
    mob = p['mobs'].pop()
    tactics.defeated(p,mob,30,lambda:.5,[])
    assert achievements.progress(p,goal) == 1


def test_partial_progress_keeps_renamed_mob_and_map_counts(tmp_path,monkeypatch):
    from jeuxRPG.multiplayer import fields, map_building
    p = project(tmp_path)
    goal = definition(target='orc',map='cave_2')
    p.content['achievements'].append(goal)
    configure(monkeypatch,goal)
    adventure = party()
    adventure.update(position='cave_2',field_map='cave_2')
    achievements.event(adventure,'kills','orc')
    p.rename('mobs','orc','orc_2')
    p.rename('maps','cave_2','cave_new')
    new_goal = p.content['achievements'][-1]
    monkeypatch.setattr(map_building,'MOBS',p.mobs)
    monkeypatch.setattr(fields,'MAPS',p.maps)
    assert achievements.progress(adventure,new_goal) == 1
