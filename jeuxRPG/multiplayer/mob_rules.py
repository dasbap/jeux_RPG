from copy import deepcopy
import math
import re


RANKS = ('SSS', 'SS', 'S', 'AA', 'A', 'B', 'C', 'D', 'E')
from jeuxRPG._class.res.character.class_models import MODELS
CLASSES = tuple(model['id'] for model in MODELS['classes'] if model['class_type'] != 'INVOCATION')
STATS = ('hp', 'force', 'endurance', 'intelligence', 'sagesse')
CLASS_XP = {'normal':1, 'warrior':1.5, 'caster':1.8, 'elite':2.5, 'boss':4}


def finite(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def resolve(mobs, identifier, visited=None):
    visited = set() if visited is None else visited
    if identifier not in mobs or identifier in visited:
        raise ValueError('Sous-espèce : parent inconnu ou cycle.')
    visited.add(identifier)
    item = deepcopy(mobs[identifier])
    parent = item.get('parent')
    if parent:
        base = resolve(mobs, parent, visited)
        base.pop('previous_ids',None)
        stats = {**base.get('stats', {}), **item.get('stats', {})}
        item = {**base, **item, 'stats':stats}
    return item


def validate_mobs(mobs,classes=None):
    classes = CLASSES if classes is None else classes
    if not isinstance(mobs, dict) or not 1 <= len(mobs) <= 200 or 'goblin' not in mobs:
        raise ValueError('De 1 à 200 espèces requises, dont goblin.')
    owners = set(mobs)
    for raw in mobs.values():
        history = raw.get('previous_ids',[]) if isinstance(raw,dict) else []
        if not isinstance(history,list) or len(history) > 100 or any(not isinstance(key,str) or not re.fullmatch(r'[a-z0-9_]{1,64}',key) or key in owners for key in history) or len(set(history)) != len(history):
            raise ValueError('Historique d’espèce invalide ou identifiant réservé.')
        owners.update(history)
    for identifier, raw in mobs.items():
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9_]{1,64}', identifier) or not isinstance(raw, dict):
            raise ValueError('Identifiant d’espèce invalide.')
        if raw.get('parent') is not None and not isinstance(raw['parent'], str):
            raise ValueError('Parent invalide.')
        item = resolve(mobs, identifier)
        if item.get('class_name') not in classes or not isinstance(item.get('name'), str) or not 1 <= len(item['name']) <= 100 or item.get('rank') not in RANKS or type(item.get('damage')) is not int or not 0 <= item['damage'] <= 10000:
            raise ValueError('Classe de base, nom, rang ou dégâts invalides.')
        if item.get('xp_class', 'normal') not in CLASS_XP or not finite(item.get('xp_multiplier', 1), 0, 100) or not finite(item.get('damage_growth', .5), 0, 1000):
            raise ValueError('Classe XP, multiplicateur ou progression des dégâts invalides.')
        stats = item.get('stats', {})
        if not isinstance(stats, dict) or set(stats)-set(STATS):
            raise ValueError('Statistique inconnue.')
        for key, value in stats.items():
            if not isinstance(value, dict) or set(value) != {'base','growth'} or not finite(value['base'], 1 if key == 'hp' else 0, 100000) or not finite(value['growth'], 0, 10000):
                raise ValueError('Statistique : base positive et croissance par niveau requises.')
        loot = item.get('loot', {})
        if not isinstance(loot, dict) or len(loot) > 100 or any(not isinstance(key, str) or not re.fullmatch(r'[a-z0-9_]{1,64}', key) or type(count) is not int or not 1 <= count <= 10000 for key,count in loot.items()):
            raise ValueError('Butin garanti invalide.')
        drops = item.get('drops', [])
        if not isinstance(drops, list) or len(drops) > 100:
            raise ValueError('100 règles de drop maximum.')
        for drop in drops:
            if not isinstance(drop, dict) or not isinstance(drop.get('item'), str) or not re.fullmatch(r'[a-z0-9_]{1,64}', drop['item']) or not finite(drop.get('chance'),0,1) or type(drop.get('attempts')) is not int or not 1 <= drop['attempts'] <= 100 or type(drop.get('min')) is not int or type(drop.get('max')) is not int or not 1 <= drop['min'] <= drop['max'] <= 10000 or type(drop.get('rare', False)) is not bool:
                raise ValueError('Drop : probabilité 0–1, 1–100 tirages, quantités 1–10000 et rareté requis.')
        phases = item.get('phases', [])
        if not isinstance(phases, list) or len(phases) > 10:
            raise ValueError('10 phases de boss maximum.')
        for phase in phases:
            if not isinstance(phase, dict) or set(phase) != {'name','hp_multiplier','damage_multiplier'} or not isinstance(phase.get('name'), str) or not 1 <= len(phase['name']) <= 100 or not finite(phase.get('hp_multiplier'), .1, 20) or not finite(phase.get('damage_multiplier'), 0, 20):
                raise ValueError('Phase de boss : nom et multiplicateurs PV/dégâts requis.')
        abilities = item.get('abilities', [])
        if not isinstance(abilities, list) or len(abilities) > 16:
            raise ValueError('16 capacités maximum.')
        names = set()
        for ability in abilities:
            if isinstance(ability,dict) and 'native' in ability:
                raise ValueError('Utilisez une référence skill_id pour une compétence native.')
            if isinstance(ability,dict) and 'skill_id' in ability:
                if not isinstance(ability['skill_id'],str) or type(ability.get('level')) is not int or not 1 <= ability['level'] <= 100 or not finite(ability.get('range',6),0,20):
                    raise ValueError('Référence de compétence, niveau ou portée invalide.')
                continue
            if not isinstance(ability, dict) or not isinstance(ability.get('name'), str) or not 1 <= len(ability['name']) <= 100 or ability['name'] in names or ability.get('type') not in ('damage','heal','stun'):
                raise ValueError('Nom ou type de capacité invalide.')
            names.add(ability['name'])
            for key, low, high in [('power',0,10000),('growth',0,1000),('cooldown',.2,600),('cast',0,30),('range',0,20),('duration',.1,60)]:
                if not finite(ability.get(key, {'duration':2}.get(key)), low, high):
                    raise ValueError(f'Capacité : {key} invalide.')
            if type(ability.get('level')) is not int or not 1 <= ability['level'] <= 100 or type(ability.get('concentration', True)) is not bool:
                raise ValueError('Niveau ou concentration invalide.')
    return deepcopy(mobs)


def level_factor(mob_level, player_level):
    return 4 ** (max(-10, min(10, mob_level-player_level))/10)


def experience(mob, player_level, base, models=None):
    classification = mob.get('xp_class')
    model = next((item for item in (models or MODELS)['classes'] if item['id'] == mob.get('class_name') or mob.get('class_name') in item.get('previous_ids',[])),{})
    class_factor = CLASS_XP.get(classification,model.get('combat',{}).get('xp_factor',1))
    level = max(1, mob.get('level',1))
    return max(0, round(base*level*class_factor*mob.get('xp_multiplier',1)*level_factor(level,player_level)))


def drop_rules(definition, legacy_rare):
    if 'drops' in definition:
        return deepcopy(definition['drops'])
    return [{'item':item, 'chance':1, 'attempts':1, 'min':count, 'max':count, 'rare':False} for item,count in definition.get('loot', {}).items()] + ([{'item':item,'chance':chance,'attempts':1,'min':1,'max':1,'rare':True} for item,chance in legacy_rare.items()] if definition.get('loot') else [])


def roll_drops(rules, random):
    loot = {}
    for rule in rules:
        for _ in range(rule['attempts']):
            if rule['chance'] <= 0 or rule['chance'] < 1 and random() >= rule['chance']:
                continue
            quantity = rule['min'] if rule['min'] == rule['max'] else rule['min']+min(rule['max']-rule['min'], int(random()*(rule['max']-rule['min']+1)))
            loot[rule['item']] = loot.get(rule['item'],0)+quantity
    return loot
