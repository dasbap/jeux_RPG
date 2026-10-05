from copy import deepcopy

import pytest

from jeuxRPG.multiplayer import mob_rules, map_building, tutorial, tactics, mob_abilities
from test_controller import project


def ability(kind='damage', level=1):
    return {'name':'Sort','type':kind,'level':level,'power':7,'growth':2,'cooldown':5,'cast':.5,'range':6,'duration':2,'concentration':True}


@pytest.mark.parametrize('difference,factor', [(-20,.25),(-10,.25),(-5,.5),(0,1),(5,2),(10,4),(20,4)])
def test_xp_difference_is_smooth_and_capped(difference,factor):
    assert mob_rules.level_factor(30+difference,30) == pytest.approx(factor)


def test_xp_uses_level_class_multiplier_and_killer_level():
    mob = {'level':10,'class_name':'Orc','xp_class':'elite','xp_multiplier':2}
    assert mob_rules.experience(mob,10,50) == 2500
    assert mob_rules.experience(mob,1,50) == round(2500*4**.9)
    assert mob_rules.experience(mob,20,50) == 625


def test_independent_drop_attempts_and_quantity_ranges():
    draws = iter([.1,.9,.2,.75])
    rules = [{'item':'gem','chance':.5,'attempts':3,'min':1,'max':1,'rare':True}, {'item':'skin','chance':1,'attempts':1,'min':2,'max':5}]
    assert mob_rules.roll_drops(rules,lambda:next(draws)) == {'gem':2,'skin':5}
    assert mob_rules.roll_drops([{**rules[0],'chance':0}],lambda:pytest.fail('No draw for 0%')) == {}


def test_subspecies_inherits_and_overrides_stats_drops_and_abilities(tmp_path, monkeypatch):
    p = project(tmp_path)
    p.mobs['goblin'].update(stats={'hp':{'base':20,'growth':5},'force':{'base':4,'growth':2}}, abilities=[ability(level=3)], drops=[{'item':'gem','chance':.1,'attempts':2,'min':1,'max':1,'rare':True}])
    p.mobs['goblin_mage'] = {'parent':'goblin','name':'Gobelin mage','xp_class':'caster','xp_multiplier':1.5,'stats':{'hp':{'base':12,'growth':3}}}
    p.validate()
    monkeypatch.setattr(map_building,'MOBS',p.mobs)
    mob = map_building.create_mob(p.maps,'clearing',{'mob_id':'goblin_mage','level':4},0)
    assert mob['stats']['hp']['max'] == 21
    assert mob['stats']['force']['max'] == 10
    assert len(mob['abilities']) == 1
    assert mob['drops'][0]['rare']
    assert mob['xp_class'] == 'caster'
    low = map_building.create_mob(p.maps,'clearing',{'mob_id':'goblin_mage','level':2},0)
    assert low['abilities'] == []
    p.save()
    p.rename('mobs','goblin_mage','goblin_mage_2')


@pytest.mark.parametrize('change', ['cycle','chance','attempts','stats','ability'])
def test_invalid_mob_catalog_is_rejected_atomically(tmp_path,change):
    p = project(tmp_path)
    data = deepcopy(p.mobs)
    if change == 'cycle':
        data['orc']['parent'] = 'dragon_whelp'
        data['dragon_whelp']['parent'] = 'orc'
    elif change in ('chance','attempts'):
        data['orc']['drops'] = [{'item':'gem','chance':2 if change == 'chance' else .1,'attempts':0 if change == 'attempts' else 1,'min':1,'max':1}]
    elif change == 'stats':
        data['orc']['stats'] = {'hp':{'base':float('nan'),'growth':1}}
    else:
        data['orc']['abilities'] = [{**ability(),'type':'eval'}]
    with pytest.raises(ValueError):
        mob_rules.validate_mobs(data)


def battle_party():
    party = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}])
    tutorial.migrate(party,0)
    tutorial.spawn(party,0,lambda:.5,[],origin='explore')
    return party


def test_killer_level_drives_shared_reward_and_new_drops_are_used():
    party = battle_party()
    mob = party['mobs'].pop()
    mob.update(level=11,last_hit_by='p',xp_class='normal',xp_multiplier=1,drops=[{'item':'gem','chance':1,'attempts':3,'min':2,'max':2,'rare':True}])
    xp = party['characters']['p']['exp']
    tactics.defeated(party,mob,10,lambda:.5,[])
    assert party['characters']['p']['level'] > 1
    assert party['battle']['corpses'][0]['loot'] == {'gem':6}
    assert xp == 0


def test_ability_cast_completes_and_cooldown_prevents_spam():
    party = battle_party()
    mob = party['mobs'][0]
    mob.update(abilities=[ability()],next_attack=0,position=[9,4])
    unit = party['battle']['players']['p']
    unit.update(position=[9,5],route=[])
    characters = {'p':tutorial.unpack(party['characters']['p'])}
    messages = []
    preset = tactics.PRESETS[party['battle']['preset']]
    assert mob_abilities.advance(party,mob,'p',characters,{'p':unit},preset,0,messages)
    hp = characters['p'].hp.current_value
    assert mob_abilities.advance(party,mob,'p',characters,{'p':unit},preset,1.5,messages)
    assert characters['p'].hp.current_value < hp
    assert mob['ability_ready']['Sort'] == 16.5
    assert not mob_abilities.advance(party,mob,'p',characters,{'p':unit},preset,5,messages)


def test_damage_cancels_concentrated_enemy_ability():
    party = battle_party()
    mob = party['mobs'][0]
    mob['ability_cast'] = {'concentration':True}
    tactics.damaged(party,mob,'p',0)
    assert 'ability_cast' not in mob
    assert mob['last_hit_by'] == 'p'


@pytest.mark.parametrize('kind', ['heal','stun'])
def test_heal_and_stun_complete(kind):
    party = battle_party()
    mob = party['mobs'][0]
    mob.update(abilities=[ability(kind)],next_attack=0,position=[9,4])
    mob['stats']['hp']['current'] = 5
    unit = party['battle']['players']['p']
    unit.update(position=[9,5],route=[[9,6]])
    characters = {'p':tutorial.unpack(party['characters']['p'])}
    preset = tactics.PRESETS[party['battle']['preset']]
    assert mob_abilities.advance(party,mob,'p',characters,{'p':unit},preset,0,[])
    assert mob_abilities.advance(party,mob,'p',characters,{'p':unit},preset,1.5,[])
    if kind == 'heal':
        assert mob['stats']['hp']['current'] > 5
    else:
        assert characters['p'].is_stunned()
        assert unit['route'] == []


def test_offensive_cast_is_cancelled_when_target_leaves_range():
    party = battle_party()
    mob = party['mobs'][0]
    mob.update(abilities=[ability()],next_attack=0,position=[9,4])
    unit = party['battle']['players']['p']
    unit.update(position=[9,5],route=[])
    characters = {'p':tutorial.unpack(party['characters']['p'])}
    preset = tactics.PRESETS[party['battle']['preset']]
    assert mob_abilities.advance(party,mob,'p',characters,{'p':unit},preset,0,[])
    hp = characters['p'].hp.current_value
    unit['position'] = [0,0]
    assert not mob_abilities.advance(party,mob,'p',characters,{'p':unit},preset,1.5,[])
    assert 'ability_cast' not in mob
    assert characters['p'].hp.current_value == hp
