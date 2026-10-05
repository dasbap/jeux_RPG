from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re

from jeuxRPG._class.res.advantage import Advantage
from jeuxRPG._class.res.classType import ClassType, DamageType, SkillType
from jeuxRPG._class.res.character.alteration.alteration import AlterationType
from jeuxRPG._class.res.character.stats import basic_stat
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect
from jeuxRPG._function.skill.custom import multy_action_skill


STAT_NAMES = ('hp','force','endurance','intelligence','sagesse')
ENERGY_NAMES = ('Mana','Aura','Foie')
STAT_TYPES = {'hp':basic_stat.HP,'force':basic_stat.Force,'endurance':basic_stat.Endurance,'intelligence':basic_stat.Intelligence,'sagesse':basic_stat.Sagesse}


def path_for(directory=None):
    if directory:
        return Path(directory)/'classes.json'
    configured = os.environ.get('RPG_CLASSES_FILE')
    if configured:
        return Path(configured)
    maps = os.environ.get('RPG_MAPS_FILE')
    if maps:
        source = Path(maps)
        candidate = (source if source.is_dir() else source.parent)/'classes.json'
        if candidate.exists():
            return candidate
    local = Path.cwd()/'maps'/'classes.json'
    return local if local.exists() else Path(__file__).resolve().parents[3]/'maps'/'classes.json'


def valid_number(value,low=0,high=100000):
    return type(value) in (int,float) and math.isfinite(value) and low <= value <= high


def validate(data):
    if not isinstance(data,dict) or data.get('version') != 1 or not isinstance(data.get('classes'),list) or not 1 <= len(data['classes']) <= 200 or not isinstance(data.get('skills'),dict) or len(data['skills']) > 2000:
        raise ValueError('Catalogue universel de classes invalide.')
    ids = set()
    aliases = set()
    table_ids = set()
    for model in data['classes']:
        if not isinstance(model,dict) or not isinstance(model.get('id'),str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,64}',model['id']) or model['id'].lower() in ids or type(model.get('playable')) is not bool or not isinstance(model.get('name'),str) or not 1 <= len(model['name']) <= 100 or model.get('class_type') not in ClassType.__members__:
            raise ValueError('Identifiant, nom ou type de classe invalide.')
        ids.add(model['id'].lower())
        if model['id'].lower() in ('character','universalcharacter','invocation'):
            raise ValueError('Identifiant réservé au moteur.')
        history = model.get('previous_ids',[])
        if not isinstance(history,list) or len(history) > 100 or any(not isinstance(alias,str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,64}',alias) or alias.lower() in aliases for alias in history):
            raise ValueError('Historique de classe invalide.')
        aliases.update(alias.lower() for alias in history)
        if model.get('table_id'):
            if not isinstance(model['table_id'],str) or not re.fullmatch(r'[a-z0-9_]{1,64}_table',model['table_id']) or model['table_id'] in table_ids:
                raise ValueError('Alias de table invalide.')
            table_ids.add(model['table_id'])
        stats = model.get('base_stats',{})
        if not isinstance(stats,dict) or set(stats) != set(STAT_NAMES) or any(type(value) is not int or not 0 <= value <= 100000 for value in stats.values()) or stats['hp'] < 1:
            raise ValueError('Stats de base invalides.')
        energies = model.get('energies')
        if not isinstance(energies,list) or len(energies) > 3 or any(not isinstance(e,dict) or e.get('type') not in ENERGY_NAMES or type(e.get('value')) is not int or not 1 <= e['value'] <= 100000 or not valid_number(e.get('regen_rate'),0,1) for e in energies) or len({e['type'] for e in energies}) != len(energies):
            raise ValueError('Énergies de classe invalides.')
        if model['class_type'] == 'INVOCATION' and model['playable']:
            raise ValueError('Une invocation ne peut pas être une classe jouable.')
        growth = model.get('growth')
        if not isinstance(growth,list) or len(growth) > 100:
            raise ValueError('Progression de classe invalide.')
        levels = set()
        for entry in growth:
            if not isinstance(entry,dict) or type(entry.get('level')) is not int or not 1 <= entry['level'] <= 100 or entry['level'] in levels:
                raise ValueError('Palier de progression invalide.')
            levels.add(entry['level'])
            for key, known in [('stats', {value.__name__ for value in STAT_TYPES.values()}),('energies',set(ENERGY_NAMES)),('unlock_energies',set(ENERGY_NAMES))]:
                values = entry.get(key,{})
                if not isinstance(values,dict) or set(values)-known or any(type(value) is not int or not 0 <= value <= 100000 for value in values.values()):
                    raise ValueError('Bonus de progression invalide.')
        for key in ('weaknesses','resistances'):
            if not isinstance(model.get(key),list) or any(item not in DamageType.__members__ for item in model[key]):
                raise ValueError('Affinité invalide.')
        combat = model.get('combat',{})
        if not isinstance(combat,dict) or combat.get('attack_stat') not in STAT_NAMES or type(combat.get('summoner')) is not bool or any(not valid_number(combat.get(key),0,20 if key == 'attack_range' else 10000) for key in ('attack_base','attack_factor','attack_min','attack_range')):
            raise ValueError('Profil de combat invalide.')
        if combat['attack_min'] < 1:
            raise ValueError('Le minimum de dégâts doit être positif.')
        if 'xp_factor' in combat and not valid_number(combat['xp_factor'],0,100):
            raise ValueError('Multiplicateur XP de classe invalide.')
        if model.get('rank') not in (None,'SSS','SS','S','AA','A','B','C','D','E'):
            raise ValueError('Rang de classe invalide.')
        formulas = model.get('formulas',{})
        if not isinstance(formulas,dict) or set(formulas)-set(STAT_NAMES) or any(not isinstance(formula,dict) or not valid_number(formula.get('base'),1 if key == 'hp' else 0) or not valid_number(formula.get('growth'),0,10000) for key,formula in formulas.items()):
            raise ValueError('Formule de croissance invalide.')
        assigned = model.get('skills')
        if not isinstance(assigned,list) or len(assigned) > 100:
            raise ValueError('Compétences de classe invalides.')
        for entry in growth:
            available = {e['type'] for e in energies} | {key for row in growth if row['level'] <= entry['level'] for key in row.get('unlock_energies',{})}
            if set(entry.get('energies',{}))-available or any(value < 1 for value in entry.get('unlock_energies',{}).values()):
                raise ValueError('Progression d’une énergie non débloquée.')
        assignment_names = set()
        for entry in assigned:
            if not isinstance(entry,dict) or entry.get('skill_id') not in data['skills'] or not isinstance(entry.get('level'),str) or not re.fullmatch(r'level ([1-9][0-9]?|100)|[A-Z]{1,8}',entry['level']):
                raise ValueError('Compétence ou niveau de déblocage inconnu.')
            name_key = (entry['level'], data['skills'][entry['skill_id']].get('name')) if isinstance(data['skills'][entry['skill_id']],dict) else None
            if name_key in assignment_names:
                raise ValueError('Deux compétences portent le même nom au même palier.')
            assignment_names.add(name_key)
            level = int(entry['level'].split()[1]) if entry['level'].startswith('level ') else 1
            available = {e['type'] for e in energies} | {key for row in growth if row['level'] <= level for key in row.get('unlock_energies',{})}
            if not isinstance(data['skills'][entry['skill_id']],dict) or data['skills'][entry['skill_id']].get('energy') not in available:
                raise ValueError('Énergie requise par la compétence absente de la classe.')
            if 'range' in entry and not valid_number(entry['range'],0,20) or 'cost' in entry and (type(entry['cost']) is not int or not 0 <= entry['cost'] <= 10000):
                raise ValueError('Portée ou coût invalide.')
    if not any(model['playable'] for model in data['classes']):
        raise ValueError('Au moins une classe jouable est requise.')
    if ids & aliases:
        raise ValueError('Alias de classe déjà utilisé.')
    for identifier, skill in data['skills'].items():
        if not isinstance(identifier,str) or not 1 <= len(identifier) <= 200 or not isinstance(skill,dict) or skill.get('type') not in SkillType.__members__ or skill.get('energy') not in ENERGY_NAMES or skill.get('damage_type') not in (None,*DamageType.__members__) or skill.get('handler') not in ('default','damage_stun') or not isinstance(skill.get('name'),str) or not 1 <= len(skill['name']) <= 100:
            raise ValueError('Définition de compétence invalide.')
        if type(skill.get('cost')) is not int or not valid_number(skill['cost']) or not valid_number(skill.get('cooldown'),0,600) or type(skill.get('requires_target')) is not bool or type(skill.get('can_target_others')) is not bool or not isinstance(skill.get('effects'),dict) or not 1 <= len(skill['effects']) <= 16:
            raise ValueError('Paramètres de compétence invalides.')
        if not isinstance(skill.get('description',''),str) or len(skill.get('description','')) > 2000:
            raise ValueError('Description de compétence invalide.')
        for key,effect in skill['effects'].items():
            if not isinstance(key,str) or not 1 <= len(key) <= 100 or not isinstance(effect,dict) or not {'value','name','duration','stat_target','invocation','alteration'} <= effect.keys() or effect['name'] is not None and (not isinstance(effect['name'],str) or len(effect['name']) > 100):
                raise ValueError('Définition d’effet invalide.')
            if not isinstance(effect,dict) or effect.get('alteration') not in (None,*AlterationType.__members__) or effect.get('stat_target') not in (0,None,*[value.__name__ for value in STAT_TYPES.values()]) or effect.get('value') is not None and not valid_number(effect['value']) or not valid_number(effect.get('duration'),0,10000):
                raise ValueError('Effet de compétence invalide.')
            invocation = effect.get('invocation')
            if invocation is not None and (not isinstance(invocation,dict) or invocation.get('class','').lower() not in ids or not isinstance(invocation.get('level'),str)):
                raise ValueError('Invocation inconnue.')
            if invocation is not None:
                target = next(model for model in data['classes'] if model['id'].lower() == invocation['class'].lower())
                tiers = {entry['level'] for entry in target['skills']} or {'BL'}
                if target['class_type'] != 'INVOCATION' or invocation['level'] not in tiers:
                    raise ValueError('Modèle ou palier d’invocation invalide.')
            try:
                SkillEffect(value=effect['value'],name=effect['name'],duration=effect['duration'],stat_target=getattr(basic_stat,effect['stat_target']) if isinstance(effect['stat_target'],str) else effect['stat_target'],invocation=effect['invocation'],alterationtype=AlterationType[effect['alteration']] if effect['alteration'] else None)
            except (ValueError,TypeError) as exc:
                raise ValueError('Effet incompatible avec le moteur : '+str(exc)) from exc
        required = {'DAMAGE':'damage','HEAL':'heal','INVOCATION':'invocation'}.get(skill['type'])
        if required and required not in skill['effects']:
            raise ValueError('Effet requis absent : '+required)
        if skill['type'] in ('DAMAGE','HEAL') and not skill['effects'][required]['value'] or skill['type'] == 'DAMAGE' and skill['handler'] == 'default' and skill['damage_type'] is None or skill['type'] == 'INVOCATION' and not skill['effects']['invocation']['invocation']:
            raise ValueError('Paramètres obligatoires de l’action absents.')
        if skill['handler'] == 'damage_stun' and (set(skill['effects'])-{'damage','Stun'} or 'damage' not in skill['effects']):
            raise ValueError('Le gestionnaire damage_stun accepte damage et Stun.')
        if skill['handler'] == 'default' and skill['type'] in ('BUFF','DEBUFF') and any(not effect['alteration'] and not effect['stat_target'] for effect in skill['effects'].values()):
            raise ValueError('Un buff ou debuff doit viser une statistique ou définir une altération.')
        if 'scaling_growth' in skill and not valid_number(skill['scaling_growth'],0,1000):
            raise ValueError('Croissance de compétence invalide.')
        if 'casting' in skill and (not isinstance(skill['casting'],dict) or not valid_number(skill['casting'].get('seconds'),0,30) or type(skill['casting'].get('concentration')) is not bool):
            raise ValueError('Incantation invalide.')
        if 'range' in skill and not valid_number(skill['range'],0,20):
            raise ValueError('Portée de compétence invalide.')
        balance = skill.get('balance',{})
        if not isinstance(balance,dict) or any(not valid_number(balance.get(key),0,100) for key in ('cost_factor','cost_min','effect_factor','stat_factor')) or balance.get('cost_fixed') is not None and not valid_number(balance['cost_fixed']) or type(balance.get('bleeding')) is not bool:
            raise ValueError('Équilibrage de compétence invalide.')
    return deepcopy(data)


def load(directory=None):
    path = path_for(directory)
    if not path.exists():
        path = path_for()
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('Catalogue de classes trop volumineux.')
    return validate(json.loads(path.read_text(encoding='utf-8')))


MODELS = load()


def playable(data=None):
    return [model['id'] for model in (data or MODELS)['classes'] if model['playable']]


def skill_from_data(definition):
    effects = {}
    for name, value in definition['effects'].items():
        effects[name] = SkillEffect(value=value['value'],name=value['name'],duration=value['duration'],stat_target=getattr(basic_stat,value['stat_target']) if isinstance(value['stat_target'],str) else value['stat_target'],invocation=deepcopy(value['invocation']),alterationtype=AlterationType[value['alteration']] if value['alteration'] else None)
    skill = Skill(definition['name'],SkillType[definition['type']],effects,require_target=definition['requires_target'],can_target_others=definition['can_target_others'],energie_cost=definition['cost'],damage_type=DamageType[definition['damage_type']] if definition['damage_type'] else None,energie_target=getattr(basic_stat,definition['energy']),custom_action=multy_action_skill if definition['handler'] == 'damage_stun' else None,cooldown=definition['cooldown'],description=definition.get('description',''))
    skill.balance = deepcopy(definition['balance'])
    if 'range' in definition:
        skill.catalog_range = definition['range']
        skill.can_target_others = skill.can_target_others and definition['range'] != 0
    if 'scaling_growth' in definition:
        skill.catalog_growth = definition['scaling_growth']
    if 'casting' in definition:
        skill.catalog_cast = deepcopy(definition['casting'])
    return skill


def table_from_model(model,data=None):
    data = data or MODELS
    advantages = Advantage()
    advantages.weakness = [DamageType[name] for name in model['weaknesses']]
    advantages.resilience = [DamageType[name] for name in model['resistances']]
    if model.get('advantage_format') == 'mapping':
        advantages = {'weakness':advantages.weakness,'resilience':advantages.resilience}
    upgrades = {}
    for entry in model['growth']:
        values = {getattr(basic_stat,key):value for key,value in entry.get('stats',{}).items()}
        if entry.get('energies'):
            values['Energie'] = {getattr(basic_stat,key):value for key,value in entry['energies'].items()}
        if entry.get('unlock_energies'):
            values['new'] = {'Energie':{getattr(basic_stat,key):value for key,value in entry['unlock_energies'].items()}}
        upgrades[entry['level']] = values
    skills = {}
    for entry in model['skills']:
        skill = skill_from_data(data['skills'][entry['skill_id']])
        if 'range' in entry:
            skill.catalog_range = entry['range']
            skill.can_target_others = skill.can_target_others and entry['range'] != 0
        if 'cost' in entry:
            skill.catalog_cost = skill.energie_cost = entry['cost']
        skills.setdefault(entry['level'],{})[skill.name] = skill
    if model['class_type'] == 'INVOCATION' and not skills:
        skills['BL'] = {}
    return {'base_stats':{**deepcopy(model['base_stats']),'energie':{index+1:{'type':getattr(basic_stat,e['type']),'value':e['value'],'regen_rate':e['regen_rate']} for index,e in enumerate(model['energies'])}},'upgrade_stats':upgrades,'advantage':advantages,'class_type':ClassType[model['class_type']],'class_skills_dict':skills,'combat':deepcopy(model['combat']),'formulas':deepcopy(model.get('formulas',{}))}


def tables():
    return {model['table_id']:table_from_model(model) for model in MODELS['classes'] if model.get('table_id')}


def skill_to_data(skill):
    balance = getattr(skill,'balance',{'cost_fixed':None,'cost_factor':1.5,'cost_min':5,'effect_factor':.55,'stat_factor':.25,'bleeding':False})
    result = {'name':skill.name,'type':skill.skill_type.name,'damage_type':skill.DamageType.name if skill.DamageType else None,'requires_target':skill.requires_target,'can_target_others':skill.can_target_others,'cost':skill.energie_cost,'energy':skill.energie_target.__name__,'cooldown':skill.cooldown,'description':skill.description,'handler':'damage_stun' if skill.custom_action else 'default','effects':{name:{'value':effect.value,'name':effect.name,'duration':effect.duration,'stat_target':effect.stat_target.__name__ if isinstance(effect.stat_target,type) else effect.stat_target,'invocation':deepcopy(effect.invocation),'alteration':effect.alterationtype.name if effect.alterationtype else None} for name,effect in skill.effects.items()},'balance':deepcopy(balance)}
    if hasattr(skill,'catalog_range'):
        result['range'] = skill.catalog_range
    if hasattr(skill,'catalog_growth'):
        result['scaling_growth'] = skill.catalog_growth
    if hasattr(skill,'catalog_cast'):
        result['casting'] = deepcopy(skill.catalog_cast)
    return result


def model_from_actor(actor,identifier,name,data):
    table = actor.class_table
    advantages = table['advantage']
    weakness = advantages.get('weakness',[]) if isinstance(advantages,dict) else advantages.weakness
    resilience = advantages.get('resilience',[]) if isinstance(advantages,dict) else advantages.resilience
    growth = []
    for level,values in table['upgrade_stats'].items():
        growth.append({'level':level,'stats':{key.__name__:value for key,value in values.items() if isinstance(key,type)},'energies':{key.__name__:value for key,value in values.get('Energie',{}).items()},'unlock_energies':{key.__name__:value for key,value in values.get('new',{}).get('Energie',{}).items()}})
    skills = []
    for level,entries in table['class_skills_dict'].items():
        for skill in entries.values():
            key = f'class:{identifier}:{skill.name}'
            data['skills'][key] = skill_to_data(skill)
            assignment = {'level':level,'skill_id':key}
            if hasattr(skill,'catalog_range'):
                assignment['range'] = skill.catalog_range
            if hasattr(skill,'catalog_cost'):
                assignment['cost'] = skill.catalog_cost
            skills.append(assignment)
    base = table['base_stats']
    return {'id':identifier,'name':name,'playable':True,'class_type':table['class_type'].name,'base_stats':{key:value for key,value in base.items() if key != 'energie'},'energies':[{'type':value['type'].__name__,'value':value['value'],'regen_rate':value['regen_rate']} for value in base['energie'].values()],'growth':growth,'skills':skills,'weaknesses':[value.name for value in weakness],'resistances':[value.name for value in resilience],'advantage_format':'mapping' if isinstance(advantages,dict) else 'object','combat':deepcopy(actor.combat_profile)}
