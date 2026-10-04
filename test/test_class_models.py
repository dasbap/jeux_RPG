from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeuxRPG.multiplayer import tutorial, content, skill_catalog
from jeuxRPG._class.res.character import class_models
from jeuxRPG._class.character import Character, CharacterMeta
from test_controller import project


GOLD = json.loads((Path(__file__).parent/'fixtures'/'class_compatibility.json').read_text())


@pytest.mark.parametrize('key',GOLD)
def test_default_class_conversion_keeps_exact_level_results(key):
    identifier,level = key.split(':')
    actor = tutorial.blueprint(identifier,int(level))
    actual = {'stats':{name:getattr(actor,name).value for name in class_models.STAT_NAMES},'energies':[[type(e).__name__,e.value,e.regen_rate] for e in actor.energie],'skills':{name:{'cost':s.energie_cost,'cooldown':s.cooldown,'effects':{key:{'value':e.value,'duration':e.duration,'alteration':e.alterationtype.name if e.alterationtype else None} for key,e in s.effects.items()}} for name,s in actor.skills.items()}}
    assert actual == GOLD[key]


def test_universal_class_creation_has_no_python_base_required(tmp_path,monkeypatch):
    p = project(tmp_path)
    model = deepcopy(next(item for item in p.content['templates']['classes'] if item['playable']))
    model.update(id='garde_universel',name='Garde universel',base_stats={**model['base_stats'],'hp':37})
    model.pop('table_id',None)
    model['combat'].update(attack_range=4,attack_base=7)
    p.content['templates']['classes'].append(model)
    p.save()
    loaded = project(tmp_path)
    assert loaded.content['templates'] == p.content['templates']
    old = CharacterMeta._classes.copy()
    try:
        skill_catalog.install(loaded.content,loaded.mobs)
        actor = Character.create('garde_universel','p','Test')
        assert actor.hp.value == 37
        assert actor.combat_profile['attack_range'] == 4
        assert actor.__class__.__bases__[0].__name__ == 'UniversalCharacter'
    finally:
        CharacterMeta._classes.clear()
        CharacterMeta._classes.update(old)
        tutorial.blueprint.cache_clear()


@pytest.mark.parametrize('field,value',[('attack_range',-1),('attack_stat','unknown'),('summoner','yes')])
def test_invalid_universal_combat_profiles_are_rejected(field,value):
    data = deepcopy(class_models.MODELS)
    data['classes'][0]['combat'][field] = value
    with pytest.raises(ValueError):
        class_models.validate(data)


def test_old_custom_classes_migrate_to_same_universal_format(tmp_path):
    p = project(tmp_path)
    p.content['classes'] = [{'id':'ancien_garde','name':'Ancien garde','base_class':'Knight','energy_capacity':30,'stats':{'hp':{'base':40,'growth':1.5}},'skills':[{'skill_id':'native:Priest:Heal','level':1,'range':0,'cost':4}]}]
    p.save()
    loaded = project(tmp_path)
    assert loaded.content['classes'] == []
    model = next(item for item in loaded.content['templates']['classes'] if item['id'] == 'ancien_garde')
    assert 'base_class' not in model
    assert model['formulas']['hp'] == {'base':40,'growth':1.5}
    loaded.save()
    reopened = project(tmp_path)
    assert reopened.content['templates'] == loaded.content['templates']
    old = CharacterMeta._classes.copy()
    try:
        skill_catalog.install(reopened.content,reopened.mobs)
        tutorial.blueprint.cache_clear()
        actor = tutorial.blueprint('ancien_garde',4)
        assert actor.hp.value == 44
        assert actor.skills['Heal'].energie_cost == 4
        assert actor.skills['Heal'].catalog_range == 0
    finally:
        CharacterMeta._classes.clear()
        CharacterMeta._classes.update(old)
        tutorial.blueprint.cache_clear()


def test_new_universal_class_can_be_used_as_a_creature_template(tmp_path):
    p = project(tmp_path)
    model = deepcopy(next(item for item in p.content['templates']['classes'] if item['id'] == 'Goblin'))
    model.update(id='creature_custom',name='Créature personnalisée')
    model.pop('table_id',None)
    p.content['templates']['classes'].append(model)
    p.mobs['custom'] = {**deepcopy(p.mobs['goblin']),'class_name':'creature_custom'}
    p.save()
    reopened = project(tmp_path)
    assert reopened.mobs['custom']['class_name'] == 'creature_custom'


def test_universal_class_shared_skill_updates_and_rename(tmp_path):
    p = project(tmp_path)
    p.content['skills'] = [{'id':'soin_test','name':'Soin test','level':1,'type':'heal','power':3,'growth':1,'cooldown':2,'cast':.2,'range':0,'concentration':False}]
    model = deepcopy(next(item for item in p.content['templates']['classes'] if item['id'] == 'Priest'))
    model.update(id='soigneur_test',name='Soigneur test',skills=[{'skill_id':'skill:soin_test','level':'level 1','range':0}])
    model.pop('table_id',None)
    model['energies'].append({'type':'Mana','value':30,'regen_rate':.3})
    p.content['templates']['skills']['skill:soin_test'] = class_models.skill_to_data(skill_catalog.make_skill(p.content['skills'][0],{}))
    p.content['templates']['classes'].append(model)
    p.content['skills'][0]['power'] = 9
    p.save()
    assert p.content['templates']['skills']['skill:soin_test']['effects']['heal']['value'] == 9
    p.rename('skills','soin_test','soin_renomme')
    p.save()
    assert model['skills'][0]['skill_id'] == 'skill:soin_renomme'
    assert 'skill:soin_test' not in p.content['templates']['skills']
    assert project(tmp_path).content['templates'] == p.content['templates']
