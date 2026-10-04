from copy import deepcopy
from functools import lru_cache
import re

from jeuxRPG._class.character import Character, CharacterMeta
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect
from jeuxRPG._class.res.classType import SkillType, DamageType
from jeuxRPG._class.res.character.alteration.alteration import AlterationType
from jeuxRPG._class.res.character.stats.basic_stat import Mana, HP, Force, Endurance, Intelligence, Sagesse
from .mob_rules import STATS, finite, resolve, validate_mobs


BASE_CLASSES = ('Knight','Mage','Archer','Priest','Necromancien')


@lru_cache(maxsize=1)
def builtins():
    result = {}
    for name in (*BASE_CLASSES,'Goblin','Orc','DragonWhelp'):
        actor = Character.create(name,'catalog','Catalogue')
        for skills in actor.class_skills_dict.values():
            for skill in skills.values():
                result[f'native:{name}:{skill.name}'] = deepcopy(skill)
    return result


def library(data, mobs):
    result = {key:{'name':skill.name,'native':key} for key,skill in builtins().items()}
    for definition in data.get('skills',[]):
        result['skill:'+definition['id']] = deepcopy(definition)
    for identifier in mobs:
        for ability in resolve(mobs,identifier).get('abilities',[]):
            if 'skill_id' not in ability:
                result[f'mob:{identifier}:{ability["name"]}'] = deepcopy(ability)
    return result


def validate(data, mobs):
    validate_mobs(mobs)
    skills = data.get('skills',[])
    classes = data.get('classes',[])
    for values in (skills,classes):
        if not isinstance(values,list) or len(values) > 200:
            raise ValueError('200 compétences ou classes maximum.')
        ids = set()
        for item in values:
            if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not re.fullmatch(r'[a-z0-9_]{1,64}',item['id']) or item['id'] in ids or not isinstance(item.get('name'),str) or not 1 <= len(item['name']) <= 100:
                raise ValueError('Identifiant ou nom de classe/compétence invalide.')
            ids.add(item['id'])
    for skill in skills:
        validate_mobs({'goblin':{'class_name':'Goblin','name':'Test','rank':'D','damage':1,'abilities':[skill]}})
    available = library(data,mobs)
    owners = {}
    for definition in classes:
        aliases = definition.get('previous_ids',[])
        if not isinstance(aliases,list) or len(aliases) > 100 or any(not isinstance(alias,str) or not re.fullmatch(r'[a-z0-9_]{1,64}',alias) for alias in aliases):
            raise ValueError('Historique de classe invalide.')
        for identifier in [definition['id'],*aliases]:
            if identifier in owners or identifier.lower() in CharacterMeta._classes and not getattr(CharacterMeta._classes[identifier.lower()],'catalog_class',False):
                raise ValueError('Identifiant de classe réservé ou dupliqué.')
            owners[identifier] = definition['id']
        if definition['id'].lower() in CharacterMeta._classes and not getattr(CharacterMeta._classes[definition['id'].lower()],'catalog_class',False) or definition.get('base_class') not in BASE_CLASSES:
            raise ValueError('Identifiant réservé ou modèle de classe inconnu.')
        if not finite(definition.get('energy_capacity',30),1,10000):
            raise ValueError('Capacité d’énergie invalide.')
        validate_mobs({'goblin':{'class_name':'Goblin','name':'Test','rank':'D','damage':1,'stats':definition.get('stats',{})}})
        assigned = definition.get('skills',[])
        if not isinstance(assigned,list) or len(assigned) > 32:
            raise ValueError('32 compétences maximum par classe.')
        names = set()
        for assignment in assigned:
            validate_assignment(assignment,available)
            name = available[assignment['skill_id']]['name']
            if name in names:
                raise ValueError('Deux compétences de la classe portent le même nom.')
            names.add(name)
    for identifier in mobs:
        for assignment in resolve(mobs,identifier).get('abilities',[]):
            if 'skill_id' in assignment:
                validate_assignment(assignment,available)
                entry = available[assignment['skill_id']]
                if entry.get('native') and builtins()[entry['native']].skill_type in (SkillType.INVOCATION,SkillType.RESURRECT):
                    raise ValueError('Cette compétence nécessite un propriétaire joueur ou une cible alliée morte ; elle est utilisable dans une classe humaine.')
    return available


def validate_assignment(item, available):
    if not isinstance(item,dict) or not isinstance(item.get('skill_id'),str) or item['skill_id'] not in available or type(item.get('level')) is not int or not 1 <= item['level'] <= 100 or not finite(item.get('range',6),0,20):
        raise ValueError('Compétence inconnue, niveau ou portée invalide.')
    if 'cost' in item and (type(item['cost']) is not int or not 0 <= item['cost'] <= 10000):
        raise ValueError('Coût d’énergie invalide.')


def make_skill(entry, assignment):
    if entry.get('native'):
        skill = deepcopy(builtins()[entry['native']])
    else:
        kind = entry['type']
        power = max(1,round(entry['power']))
        effect = SkillEffect(value=power) if kind != 'stun' else SkillEffect(value=1,name=entry['name'],duration=max(1,round(entry.get('duration',2)/1.2)),alterationtype=AlterationType.STUN)
        skill = Skill(entry['name'],{'damage':SkillType.DAMAGE,'heal':SkillType.HEAL,'stun':SkillType.DEBUFF}[kind],{'heal' if kind == 'heal' else 'damage' if kind == 'damage' else 'stun':effect},energie_target=Mana,energie_cost=5,damage_type=DamageType.MAGIC,cooldown=entry['cooldown'])
        skill.catalog_growth = entry['growth']
        skill.catalog_cast = {'seconds':entry['cast'],'concentration':entry.get('concentration',True)}
    skill.catalog_range = assignment.get('range',entry.get('range',6))
    skill.can_target_others = skill.can_target_others and skill.catalog_range != 0
    if 'cost' in assignment:
        skill.energie_cost = assignment['cost']
    skill.catalog_cost = skill.energie_cost
    return skill


def mob_ability(entry, assignment):
    if entry.get('native'):
        skill = make_skill(entry,assignment)
        from .progression import casting
        timing = casting(skill)
        return {'name':skill.name,'type':'native','native':entry['native'],'level':assignment['level'],'range':skill.catalog_range,'cast':timing['seconds'],'concentration':timing['concentration'],'cooldown':max(.2,skill.cooldown),'cost':skill.energie_cost}
    return {**deepcopy(entry),'level':assignment['level'],'range':assignment.get('range',entry['range'])}


def install(data, mobs):
    available = validate(data,mobs)
    installed = []
    stat_types = {'hp':HP,'force':Force,'endurance':Endurance,'intelligence':Intelligence,'sagesse':Sagesse}
    for definition in data.get('classes',[]):
        base = CharacterMeta._classes[definition['base_class'].lower()]
        template = Character.create(definition['base_class'],'catalog','Catalogue')
        table = deepcopy(template.class_table)
        for key, formula in definition.get('stats',{}).items():
            table['base_stats'][key] = round(formula['base'])
            for upgrade in table['upgrade_stats'].values():
                upgrade.pop(stat_types[key],None)
            table['upgrade_stats'].setdefault(1,{})[stat_types[key]] = round(formula['growth'])
        skill_table = {}
        for assignment in definition.get('skills',[]):
            skill = make_skill(available[assignment['skill_id']],assignment)
            skill_table.setdefault('level '+str(assignment['level']),{})[skill.name] = skill
            if not any(info['type'] == skill.energie_target for info in table['base_stats']['energie'].values()):
                for upgrade in table['upgrade_stats'].values():
                    upgrade.get('new',{}).get('Energie',{}).pop(skill.energie_target,None)
                table['base_stats']['energie'][len(table['base_stats']['energie'])+1] = {'type':skill.energie_target,'value':round(definition.get('energy_capacity',30)),'regen_rate':.3}
        table['class_skills_dict'] = skill_table
        def initialize(self,user_id,name,table=table,identifier=definition['id']):
            Character.__init__(self,user_id,name,deepcopy(table),char_class=identifier)
        def level_up(self, base=base, formulas=deepcopy(definition.get('stats',{}))):
            result = base.level_up(self)
            for key,formula in formulas.items():
                stat = getattr(self,key)
                missing = stat.value-stat.current_value
                stat.value = round(formula['base']+formula['growth']*(self.level-1))
                stat.current_value = max(0,stat.value-missing)
            return result
        dynamic = CharacterMeta(definition['id'],(base,),{'__init__':initialize,'level_up':level_up,'class_skills_dict':skill_table,'catalog_class':True,'catalog_base_class':definition['base_class'],'is_playable':True})
        for alias in definition.get('previous_ids',[]):
            CharacterMeta._classes[alias] = dynamic
        installed.append(dynamic.__name__)
    return installed
