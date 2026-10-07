from copy import deepcopy
from pathlib import Path
import shutil

from jeuxRPG.multiplayer import controller, content, map_building, skill_catalog
from jeuxRPG._class.character import CharacterMeta


def test_authored_catalogues_are_valid_and_all_spawners_can_create_their_mobs(tmp_path,monkeypatch):
    source = Path(__file__).resolve().parent.parent/'jeuxRPG'/'maps'
    directory = tmp_path/'authored'
    shutil.copytree(source,directory)
    p = controller.Project(directory)
    assert p.validate()
    original = CharacterMeta._classes.copy()
    monkeypatch.setattr(map_building,'MOBS',p.mobs)
    monkeypatch.setattr(content,'DATA',p.content)
    try:
        skill_catalog.install(p.content,p.mobs)
        for identifier,definition in p.maps.items():
            for index,config in enumerate(map_building.spawners(definition)):
                mob = map_building.create_mob(p.maps,identifier,config,index)
                assert mob['stats']['hp']['max'] >= 1
                assert mob['mob_id'] == config['mob_id']
        before = {path.name:path.read_bytes() for path in source.glob('*.json')}
        p.save()
        assert {path.name:path.read_bytes() for path in source.glob('*.json')} == before
        assert controller.Project(directory).state() == p.state()
    finally:
        CharacterMeta._classes.clear()
        CharacterMeta._classes.update(original)


def test_quest_can_require_a_specific_sector_inside_its_parent_zone(monkeypatch):
    from jeuxRPG.multiplayer import tutorial
    data = deepcopy(content.DATA)
    data['quests'].append({'id':'boss_sector','name':'Le chef','npc':'mira','kind':'kill','target':'goblin','zone':'hunt','count':1,'reward_xp':10,'description':'Secteur précis'})
    monkeypatch.setattr(content,'DATA',data)
    p = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}])
    p['custom_quests'] = {'boss_sector':{'status':'active','progress':0}}
    p.update(position='forest',field_map='forest')
    content.quest_event(p,'kill','goblin','lisiere')
    assert p['custom_quests']['boss_sector']['progress'] == 0
    p.update(position='hunt',field_map='hunt')
    content.quest_event(p,'kill','goblin','lisiere')
    assert p['custom_quests']['boss_sector']['progress'] == 1
