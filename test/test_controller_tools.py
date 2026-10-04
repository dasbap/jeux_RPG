from copy import deepcopy
from types import SimpleNamespace

import pytest

from jeuxRPG.multiplayer import controller, controller_tools
from jeuxRPG._class.character import CharacterMeta
from test_controller import project


def test_search_and_references_cover_scoped_achievements(tmp_path):
    p = project(tmp_path)
    p.content['achievements'].append({'id':'goblin_666','name':'Chasseur de gobelins','condition':'kills','threshold':666,'title':'Fléau','target':'goblin','zone':'lisiere','map':'hunt'})
    rows = controller_tools.filter_rows(controller_tools.catalog_rows(p,'achievements'),'GOBLIN 666 lisiere')
    assert [row[0] for row in rows] == ['goblin_666']
    assert any('/achievements/' in ref for ref in controller_tools.references(p,'mobs','goblin'))
    assert any('/achievements/' in ref for ref in controller_tools.references(p,'maps','hunt'))


@pytest.mark.parametrize('section,identifier', [('quests','mira_hunt'),('achievements','silent'),('classes','Knight'),('skills','custom'),('mobs','orc')])
def test_independent_duplicates_can_be_saved_and_reloaded(tmp_path,section,identifier):
    p = project(tmp_path)
    if section == 'skills':
        p.content['skills'] = [{'id':'custom','name':'Custom','type':'damage','level':1,'power':3.,'growth':.5,'cooldown':5.,'cast':.6,'range':1.5,'duration':2.,'concentration':True}]
    p.duplicate(section,identifier,'copy_2')
    p.save()
    loaded = project(tmp_path)
    assert loaded.state() == p.state()
    if section == 'classes':
        value = next(item for item in p.content['templates']['classes'] if item['id'] == 'copy_2')
        assert 'table_id' not in value
        value['base_stats']['hp'] = 999
        assert next(item for item in p.content['templates']['classes'] if item['id'] == 'Knight')['base_stats']['hp'] != 999
    if section == 'quests':
        assert 'role' not in next(item for item in p.content['quests'] if item['id'] == 'copy_2')


def test_duplicate_failure_does_not_change_project(tmp_path):
    p = project(tmp_path)
    before = p.state()
    with pytest.raises(ValueError):
        p.duplicate('classes','Knight','mage')
    assert p.state() == before


def test_class_preview_has_level_stats_and_preserves_registry(tmp_path):
    p = project(tmp_path)
    before = CharacterMeta._classes.copy()
    values = controller_tools.preview(p,'classes','Knight',7)
    assert values['niveau'] == 7
    assert values['stats']['hp'] > 25
    assert next(item for item in values['compétences'] if item['nom'] == 'Sword Slash')['coût'] == 10
    assert CharacterMeta._classes == before


def test_drop_preview_uses_independent_trials_and_xp_level_difference(tmp_path):
    p = project(tmp_path)
    p.mobs['orc']['drops'] = [{'item':'rare','chance':.1,'attempts':3,'min':1,'max':3,'rare':True}]
    same = controller_tools.preview(p,'mobs','orc',11,11)
    low = controller_tools.preview(p,'mobs','orc',11,1)
    high = controller_tools.preview(p,'mobs','orc',11,21)
    assert same['drops'][0]['chance_au_moins_un_drop'] == pytest.approx(.271)
    assert same['drops'][0]['quantité_moyenne'] == pytest.approx(.6)
    assert low['xp'] == same['xp'] * 4
    assert high['xp'] == round(same['xp'] / 4)


def test_diagnostic_reports_multiple_categories_without_mutating_globals(tmp_path):
    p = project(tmp_path)
    before = controller_tools.map_building.MOBS
    p.content['world']['player_vision'] = 0
    p.mobs['orc']['rank'] = 'Z'
    values = controller_tools.report(p)
    assert len(values['erreurs']) >= 2
    assert controller_tools.map_building.MOBS is before


def test_undo_redo_and_new_edit_discards_future(tmp_path):
    p = project(tmp_path)
    screen = controller.Controller.__new__(controller.Controller)
    screen.project, screen.history, screen.future = p, [], []
    screen.refresh = lambda: None
    before = p.state()
    p.content['world']['player_vision'] = 20
    screen.remember(before)
    screen.undo()
    assert p.content['world']['player_vision'] == 12
    screen.redo()
    assert p.content['world']['player_vision'] == 20
    screen.undo()
    screen.remember(p.state())
    assert screen.future == []


def test_engine_skill_copy_edit_reuse_and_rename(tmp_path):
    from jeuxRPG.multiplayer import skill_catalog, mob_abilities
    from jeuxRPG._class.res.character.class_models import skill_from_data
    p = project(tmp_path)
    p.duplicate('skill_models','native:Knight:Sword Slash','slash_copy')
    key = 'ability:slash_copy'
    definition = p.content['templates']['skills'][key]
    definition.update(name='Entaille custom',cost=12,range=0)
    definition['balance']['cost_fixed'] = 12
    assignment = {'skill_id':key,'level':1}
    p.mobs['orc']['abilities'] = [assignment]
    p.save()
    entry = skill_catalog.library(p.content,p.mobs)[key]
    skill = skill_catalog.make_skill(entry,assignment)
    assert skill.energie_cost == 12
    assert skill.catalog_range == 0
    assert not skill.can_target_others
    ability = skill_catalog.mob_ability(entry,assignment)
    assert mob_abilities.native_skill(ability).name == 'Entaille custom'
    p.rename('skill_models',key,'entaille_custom')
    p.save()
    assert p.mobs['orc']['abilities'][0]['skill_id'] == 'entaille_custom'
    assert 'entaille_custom' in project(tmp_path).content['templates']['skills']


def test_engine_skill_editor_preserves_original_without_graphical_session(tmp_path):
    p = project(tmp_path)
    screen = controller.Controller.__new__(controller.Controller)
    screen.project = p
    screen.form = lambda title,values,choices=None: values
    screen.edit_records = lambda title,initial,default,choices=None: initial
    before = deepcopy(p.content['templates']['skills']['native:Knight:Sword Slash'])
    values = screen.edit_skill_model('native:Knight:Sword Slash',False)
    assert values['name'] == before['name']
    assert values['effects'] == before['effects']
    assert values['balance'] == before['balance']
    assert values['casting']['seconds'] > 0
    assert p.content['templates']['skills']['native:Knight:Sword Slash'] == before


def test_invocation_template_editor_preserves_tiers(tmp_path):
    p = project(tmp_path)
    screen = controller.Controller.__new__(controller.Controller)
    screen.project = p
    screen.form = lambda title,values,choices=None: values
    screen.edit_records = lambda title,initial,default,choices=None: initial
    original = deepcopy(next(model for model in p.content['templates']['classes'] if model['id'] == 'Squelette'))
    result = screen.edit_template('Squelette',False)
    assert result['skills'] == original['skills']
    assert result['class_type'] == 'INVOCATION'


@pytest.mark.parametrize('key', ['native:Knight:Sword Slash','native:Mage:Fire Ball','native:Priest:Heal','native:Necromancien:Low Skull'])
def test_engine_skill_editor_roundtrip_effects(tmp_path,key):
    p = project(tmp_path)
    screen = controller.Controller.__new__(controller.Controller)
    screen.project = p
    screen.form = lambda title,values,choices=None: values
    screen.edit_records = lambda title,initial,default,choices=None: initial
    before = deepcopy(p.content['templates']['skills'][key])
    result = screen.edit_skill_model(key,False)
    assert result['effects'] == before['effects']
    assert result['balance'] == before['balance']
    assert result['energy'] == before['energy']


def test_cancel_class_skill_dialog_does_not_change_project(tmp_path):
    p = project(tmp_path)
    p.content['skills'] = [{'id':'new_skill','name':'New','type':'damage','level':1,'power':3.,'growth':.5,'cooldown':5.,'cast':.6,'range':1.5,'duration':2.,'concentration':True}]
    screen = controller.Controller.__new__(controller.Controller)
    screen.project = p
    screen.form = lambda title,values,choices=None: values
    screen.edit_records = lambda title,initial,default,choices=None: None if title == 'Compétences universelles' else initial
    before = p.state()
    assert screen.edit_template('Knight',False) is None
    assert p.state() == before


def test_invocation_rename_keeps_saved_identifier_registered(tmp_path):
    from jeuxRPG.multiplayer import skill_catalog
    p = project(tmp_path)
    p.rename('classes','Squelette','squelette_2')
    p.save()
    before = CharacterMeta._classes.copy()
    try:
        CharacterMeta._classes.pop('squelette',None)
        skill_catalog.install(p.content,p.mobs)
        assert CharacterMeta._classes['squelette'] is CharacterMeta._classes['squelette_2']
    finally:
        CharacterMeta._classes.clear()
        CharacterMeta._classes.update(before)


@pytest.mark.parametrize('change', ['zero','no_damage_type','no_damage_effect','stun_without_name','invocation_without_model'])
def test_invalid_engine_skill_cannot_be_saved(tmp_path,change):
    p = project(tmp_path)
    definition = p.content['templates']['skills']['native:Knight:Sword Slash']
    if change == 'zero':
        definition['effects']['damage']['value'] = 0
    elif change == 'no_damage_type':
        definition['damage_type'] = None
    elif change == 'no_damage_effect':
        definition['effects']['other'] = definition['effects'].pop('damage')
    elif change == 'stun_without_name':
        definition['effects']['damage'].update(alteration='STUN',name='')
    else:
        definition = p.content['templates']['skills']['native:Necromancien:Low Skull']
        definition['effects']['invocation']['invocation'] = None
    with pytest.raises(ValueError):
        p.save()


def test_reused_stun_skill_executes_without_stat_target():
    from jeuxRPG.multiplayer import skill_catalog
    from jeuxRPG._class.character import Character
    entry = {'name':'Stun sans stat','type':'stun','power':1,'growth':0,'cooldown':1,'cast':0,'duration':2,'range':2}
    skill = skill_catalog.make_skill(entry,{})
    caster = Character.create('Mage','caster','Mage')
    target = Character.create('Goblin','target','Gobelin')
    result = skill.execute(caster,target)
    assert result['success']
    assert target.is_stunned()
