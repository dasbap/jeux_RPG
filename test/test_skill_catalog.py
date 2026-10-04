from copy import deepcopy

import pytest

from jeuxRPG._class.character import Character, CharacterMeta
from jeuxRPG.multiplayer import skill_catalog, content, map_building, tutorial, tactics, progression, mob_abilities
from test_controller import project


def definition():
    return {'id':'sentinelle','name':'Sentinelle','base_class':'Knight','energy_capacity':30,'stats':{'hp':{'base':40,'growth':8},'intelligence':{'base':9,'growth':3}},'skills':[{'skill_id':'native:Priest:Heal','level':1,'range':0,'cost':4},{'skill_id':'native:Goblin:Stab','level':2,'range':1.5,'cost':3},{'skill_id':'native:Necromancien:Low Skull','level':3,'range':0,'cost':5}]}


@pytest.fixture
def catalog(monkeypatch):
    data = deepcopy(content.DEFAULTS)
    data['classes'] = [definition()]
    data['skills'] = []
    monkeypatch.setattr(content,'DATA',data)
    old = CharacterMeta._classes.copy()
    skill_catalog.install(data,map_building.MOBS)
    tutorial.blueprint.cache_clear()
    yield data
    CharacterMeta._classes.clear()
    CharacterMeta._classes.update(old)
    tutorial.blueprint.cache_clear()


def test_human_class_has_level_stats_energies_and_reused_skills(catalog):
    actor = tutorial.blueprint('sentinelle',3)
    assert actor.char_class == 'sentinelle'
    assert actor.hp.value == 56
    assert actor.intelligence.value == 15
    assert set(actor.skills) == {'Heal','Stab','Low Skull'}
    assert actor.get_energie(actor.skills['Heal'].energie_target).value == 30
    assert actor.skills['Heal'].energie_cost == 4
    restored = tutorial.unpack(tutorial.pack(actor))
    assert set(restored.skills) == set(actor.skills)
    assert progression.attack_range(restored,restored.skills['Heal']) == 0
    assert 'Stab' not in tutorial.blueprint('sentinelle',1).skills


def test_zero_range_excludes_other_entities_even_on_same_cell(catalog):
    p = tutorial.new_party([{'id':'p','name':'Un','class_name':'sentinelle'},{'id':'q','name':'Deux','class_name':'Knight'}])
    tutorial.migrate(p,0)
    tutorial.spawn(p,0,lambda:.5,[],origin='explore')
    actor = tutorial.unpack(p['characters']['p'])
    other = tutorial.unpack(p['characters']['q'])
    actor.hp.current_value -= 1
    other.hp.current_value -= 1
    skill = actor.skills['Heal']
    assert tutorial.can_target(actor,skill,actor,None)
    assert not tutorial.can_target(actor,skill,other,None)
    p['battle']['players']['q']['position'] = p['battle']['players']['p']['position'][:]
    assert tactics.allowed(p,'p','p',0)
    assert not tactics.allowed(p,'p','q',0)


def test_custom_class_reuses_mob_and_shared_abilities(tmp_path):
    p = project(tmp_path)
    p.content['skills'] = [{'id':'restauration','name':'Restauration','type':'heal','level':1,'power':8,'growth':2,'cooldown':3,'cast':.5,'range':0,'duration':2,'concentration':True}]
    p.mobs['goblin']['abilities'] = [{'name':'Impact','type':'damage','level':1,'power':4,'growth':1,'cooldown':3,'cast':.2,'range':2,'duration':2}]
    p.content['classes'] = [{**definition(),'skills':[{'skill_id':'mob:goblin:Impact','level':1,'range':2},{'skill_id':'skill:restauration','level':1,'range':0}]}]
    p.save()
    available = skill_catalog.validate(p.content,p.mobs)
    assert skill_catalog.make_skill(available['skill:restauration'],{'range':0}).can_target_others is False
    assert skill_catalog.make_skill(available['mob:goblin:Impact'],{}).name == 'Impact'
    p.rename('skills','restauration','restauration_2')
    assert p.content['classes'][0]['skills'][1]['skill_id'] == 'skill:restauration_2'


def test_mob_can_use_native_human_damage(monkeypatch):
    mobs = deepcopy(map_building.MOBS)
    mobs['goblin']['abilities'] = [{'skill_id':'native:Mage:Fire Ball','level':1,'range':6,'cost':1}]
    skill_catalog.validate(content.DATA,mobs)
    monkeypatch.setattr(map_building,'MOBS',mobs)
    p = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}])
    tutorial.migrate(p,0)
    tutorial.spawn(p,0,lambda:.5,[],origin='explore')
    mob = map_building.create_mob({'clearing':{'level':1}},'clearing',{'mob_id':'goblin','level':1},0)
    mob.update(position=[9,4],next_attack=0)
    unit = p['battle']['players']['p']
    unit['position'] = [9,5]
    actors = {'p':tutorial.unpack(p['characters']['p'])}
    preset = tactics.PRESETS[p['battle']['preset']]
    before = actors['p'].hp.current_value
    assert mob_abilities.advance(p,mob,'p',actors,{'p':unit},preset,0,[])
    assert mob_abilities.advance(p,mob,'p',actors,{'p':unit},preset,10,[])
    assert actors['p'].hp.current_value < before


@pytest.mark.parametrize('change',['range','missing','duplicate','reserved'])
def test_invalid_class_catalog_rejected(change):
    data = deepcopy(content.DEFAULTS)
    item = definition()
    if change == 'range':
        item['skills'][0]['range'] = -1
    elif change == 'missing':
        item['skills'][0]['skill_id'] = 'missing'
    elif change == 'duplicate':
        item['skills'].append(deepcopy(item['skills'][0]))
    else:
        item['id'] = 'mage'
    data['classes'] = [item]
    with pytest.raises(ValueError):
        skill_catalog.validate(data,map_building.MOBS)


def test_imported_invocation_and_self_heal_execute(catalog):
    actor = deepcopy(tutorial.blueprint('sentinelle',3))
    actor.hp.current_value -= 10
    assert actor.use_skill('Heal',actor)[0]
    assert actor.hp.current_value > actor.hp.value-10
    assert actor.use_skill('Low Skull',actor)[0]
    assert actor.invocations.get_all()
    from jeuxRPG._class.sub_character.invocations.invocation import Invocation
    for invocation in actor.invocations.get_all():
        if invocation in Invocation.all_invocation:
            Invocation.all_invocation.remove(invocation)


def test_class_rename_keeps_old_saved_character_readable(tmp_path):
    p = project(tmp_path)
    p.content['classes'] = [definition()]
    p.rename('classes','sentinelle','sentinelle_2')
    assert p.content['classes'][0]['previous_ids'] == ['sentinelle']
    old = CharacterMeta._classes.copy()
    try:
        skill_catalog.install(p.content,p.mobs)
        actor = Character.create('sentinelle','p','Test')
        assert actor.char_class == 'sentinelle_2'
    finally:
        CharacterMeta._classes.clear()
        CharacterMeta._classes.update(old)


def test_fractional_stat_growth_matches_formula(catalog):
    catalog['classes'][0]['stats']['hp'] = {'base':40,'growth':1.5}
    skill_catalog.install(catalog,map_building.MOBS)
    tutorial.blueprint.cache_clear()
    assert tutorial.blueprint('sentinelle',4).hp.value == 44


def test_custom_class_is_listed_and_registerable_over_http(catalog,tmp_path):
    import threading
    from jeuxRPG.multiplayer.service import GameService
    from jeuxRPG.multiplayer.server import RPGServer
    from test_multiplayer import request
    game = GameService(tmp_path/'game.sqlite3')
    server = RPGServer(('127.0.0.1',0),game,log_directory=tmp_path/'.logs')
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        status, available = request(server,'/api/classes')
        assert status == 200
        assert {'id':'sentinelle','name':'Sentinelle'} in available
        status, registered = request(server,'/api/register',{'name':'Sentinelle test','class_name':'sentinelle'})
        assert status == 201
        assert registered['player']['class_name'] == 'sentinelle'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        game.close()


def test_arbitrary_native_reference_cannot_bypass_catalog_validation():
    mobs = deepcopy(map_building.MOBS)
    mobs['goblin']['abilities'] = [{'name':'Test','type':'heal','level':1,'power':2,'growth':0,'cooldown':1,'cast':0,'range':0,'native':'untrusted'}]
    with pytest.raises(ValueError,match='skill_id'):
        skill_catalog.validate(content.DATA,mobs)


def test_imported_late_energy_is_not_duplicated_at_original_unlock_level(catalog):
    catalog['classes'][0]['skills'] = [{'skill_id':'native:Knight:Holy Strike','level':1,'range':1.5,'cost':5}]
    skill_catalog.install(catalog,map_building.MOBS)
    tutorial.blueprint.cache_clear()
    actor = tutorial.blueprint('sentinelle',21)
    target = actor.skills['Holy Strike'].energie_target
    assert sum(isinstance(energy,target) for energy in actor.energie) == 1
