from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re


DEFAULTS = {
    'world': {'repop_seconds': 180, 'mob_xp': 50, 'xp_base': 500, 'xp_exponent': 1.8, 'merchant_stay_hours': 8, 'player_vision': 12},
    'quests': [{'id': 'mira_hunt', 'name': 'Protéger la lisière', 'npc': 'mira', 'kind': 'kill', 'target': 'goblin', 'zone': 'lisiere', 'count': 3, 'reward_xp': 300, 'description': 'Battez les gobelins puis rapportez la nouvelle à Mira.'}],
    'achievements': [
        {'id': 'silent', 'name': 'Victoire sans alerter d’ennemi', 'condition': 'silent', 'threshold': 1, 'title': 'Ombre silencieuse'},
        {'id': 'untouched', 'name': 'Victoire sans dégâts au groupe ni aux invocations', 'condition': 'untouched', 'threshold': 1, 'title': 'Intouchable'},
        {'id': 'fast', 'name': 'Victoire en 30 secondes réelles maximum', 'condition': 'fast', 'threshold': 30, 'title': 'Éclair de la lisière'},
        {'id': 'higher', 'name': 'Seul contre un ennemi de niveau supérieur', 'condition': 'higher', 'threshold': 1, 'title': 'Briseur de limites'},
        {'id': 'superiority', 'name': 'Victoire en supériorité numérique', 'condition': 'superiority', 'threshold': 1, 'title': 'Force du nombre'},
        {'id': 'inferiority', 'name': 'Victoire en infériorité numérique', 'condition': 'inferiority', 'threshold': 1, 'title': 'Contre toute attente'},
        *[{'id': f'level_{level}', 'name': f'Atteindre le niveau {level}', 'condition': 'level', 'threshold': level, 'title': title} for level, title in [(5, 'Aventurier confirmé'), (10, 'Vétéran'), (20, 'Légende vivante')]],
        *[{'id': f'kills_{count}', 'name': f'Vaincre {count} créatures', 'condition': 'kills', 'threshold': count, 'title': title} for count, title in [(1, 'Première victoire'), (10, 'Chasseur'), (50, 'Fléau des gobelins'), (100, 'Gardien des chemins')]],
    ],
}
CONDITIONS = ('silent', 'untouched', 'fast', 'higher', 'superiority', 'inferiority', 'level', 'kills')


def number(value, minimum, maximum):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def is_hunt(quest):
    return quest.get('role') == 'tutorial_hunt' or quest.get('role') is None and quest.get('id') == 'mira_hunt'


def validate_content(data):
    if not isinstance(data, dict) or set(data)-{'classes','skills','templates'} != set(DEFAULTS):
        raise ValueError('Sections monde, quêtes et succès requises.')
    limits = {'repop_seconds': (1, 86400), 'mob_xp': (0, 100000), 'xp_base': (1, 100000), 'xp_exponent': (1, 5), 'merchant_stay_hours': (.1, 168), 'player_vision': (1, 64)}
    if not isinstance(data['world'], dict) or set(data['world']) != set(limits):
        raise ValueError('Paramètres du monde invalides.')
    for key, (low, high) in limits.items():
        if not number(data['world'][key], low, high):
            raise ValueError(f'{key} : valeur entre {low} et {high}.')
    for key in ('player_vision', 'mob_xp'):
        if type(data['world'][key]) is not int:
            raise ValueError(f'{key} : nombre entier requis.')
    for section in ('quests', 'achievements'):
        values = data[section]
        if not isinstance(values, list) or len(values) > 200:
            raise ValueError('200 définitions maximum par catalogue.')
        ids = set()
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not re.fullmatch(r'[a-z0-9_]{1,64}', item['id']) or item['id'] in ids:
                raise ValueError('Identifiant invalide ou dupliqué.')
            ids.add(item['id'])
            aliases = item.get('previous_ids', [])
            if not isinstance(aliases, list) or len(aliases) > 100 or any(not isinstance(alias, str) or not re.fullmatch(r'[a-z0-9_]{1,64}', alias) for alias in aliases) or len(set(aliases)) != len(aliases):
                raise ValueError('Historique des identifiants invalide.')
            if item.get('role') not in (None, 'tutorial_hunt') or section != 'quests' and item.get('role'):
                raise ValueError('Rôle interne invalide.')
            for key in ('name', 'title') if section == 'achievements' else ('name', 'npc', 'target', 'description'):
                if not isinstance(item.get(key), str) or not 1 <= len(item[key]) <= (2000 if key == 'description' else 100):
                    raise ValueError(f'{key} : texte requis.')
            if section == 'quests':
                if item.get('kind') not in ('kill', 'craft') or type(item.get('count')) is not int or not 1 <= item['count'] <= 10000 or type(item.get('reward_xp')) is not int or not 0 <= item['reward_xp'] <= 100000 or not isinstance(item.get('zone', ''), str):
                    raise ValueError('Objectif ou récompense de quête invalide.')
            elif item.get('condition') not in CONDITIONS or not number(item.get('threshold'), .01, 100000):
                raise ValueError('Condition de succès invalide.')
    for section in ('quests', 'achievements'):
        owners = {}
        for item in data[section]:
            for identifier in [item['id'], *item.get('previous_ids', [])]:
                if identifier in owners and owners[identifier] != item['id']:
                    raise ValueError('Identifiant déjà utilisé ou réservé par un renommage.')
                owners[identifier] = item['id']
    quests = {q['id']:q for q in data['quests']}
    achievements = {a['id'] for a in data['achievements']}
    for quest in quests.values():
        requirements = quest.get('requirements', {})
        if not isinstance(requirements, dict) or set(requirements)-{'level','achievements','quests'} or type(requirements.get('level',1)) is not int or not 1 <= requirements.get('level',1) <= 100:
            raise ValueError('Prérequis de quête : niveau entier entre 1 et 100.')
        for key, known in [('quests',quests),('achievements',achievements)]:
            identifiers = requirements.get(key, [])
            if not isinstance(identifiers,list) or len(identifiers) > 200 or any(not isinstance(identifier,str) or identifier not in known for identifier in identifiers) or len(set(identifiers)) != len(identifiers):
                raise ValueError('Prérequis : quête ou succès inconnu ou dupliqué.')
    visited = set()
    def check(identifier, pending):
        if identifier in pending:
            raise ValueError('Cycle dans les prérequis de quêtes.')
        if identifier in visited:
            return
        for dependency in quests[identifier].get('requirements',{}).get('quests',[]):
            check(dependency,pending | {identifier})
        visited.add(identifier)
    for identifier in quests:
        check(identifier,set())
    hunts = [q for q in data['quests'] if is_hunt(q)]
    if len(hunts) != 1 or not any(q['npc'] == 'mira' and q['kind'] == 'kill' and q['target'] == 'goblin' and q.get('zone') == 'lisiere' for q in hunts):
        raise ValueError('La quête de chasse de Mira est nécessaire au tutoriel.')
    for section in ('classes','skills'):
        if section in data and not isinstance(data[section],list):
            raise ValueError('Catalogue de classes/compétences invalide.')
    if 'templates' in data:
        from jeuxRPG._class.res.character.class_models import validate as validate_templates
        validate_templates(data['templates'])
    return deepcopy(data)


def content_path():
    configured = os.environ.get('RPG_CONTENT_FILE')
    if configured:
        return Path(configured)
    maps = os.environ.get('RPG_MAPS_FILE')
    if maps:
        source = Path(maps)
        sibling = (source if source.is_dir() else source.parent) / 'content.json'
        if sibling.exists():
            return sibling
    local = Path.cwd() / 'maps' / 'content.json'
    return local if local.exists() else Path(__file__).resolve().parents[1] / 'maps' / 'content.json'


def load_content(path=None):
    path = Path(path) if path else content_path()
    if not path.exists():
        return deepcopy(DEFAULTS)
    if path.stat().st_size > 1024*1024:
        raise ValueError('Catalogue de contenu trop volumineux.')
    data = json.loads(path.read_text(encoding='utf-8'))
    result = data.get('content',data)
    from jeuxRPG._class.res.character.class_models import load as load_templates
    result['templates'] = load_templates(None if os.environ.get('RPG_CLASSES_FILE') else path.parent)
    return validate_content(result)


DATA = load_content()
WORLD = DATA['world']
HUNT = next(q for q in DATA['quests'] if is_hunt(q))


def quest_states(party):
    states = party.setdefault('custom_quests', {})
    for quest in DATA['quests']:
        for alias in quest.get('previous_ids', []):
            if alias not in states or alias == quest['id']:
                continue
            previous = states.pop(alias)
            current = states.get(quest['id'])
            if current is None:
                states[quest['id']] = previous
            else:
                current['progress'] = max(current.get('progress', 0), previous.get('progress', 0))
                if previous.get('status') == 'completed':
                    current['status'] = 'completed'
    return states


def quest_event(party, kind, target, zone=None):
    states = quest_states(party)
    for quest in DATA['quests']:
        state = states.get(quest['id'])
        if not is_hunt(quest) and state and state['status'] == 'active' and quest['kind'] == kind and quest['target'] == target and (not quest.get('zone') or quest['zone'] == zone):
            state['progress'] = min(quest['count'], state['progress']+1)


def missing_requirements(party, quest):
    from . import achievements
    requirements = quest.get('requirements', {})
    missing = []
    level = requirements.get('level',1)
    below = [character['name'] for character in party['characters'].values() if character['level'] < level]
    if below:
        missing.append(f"niveau {level} requis pour : {', '.join(below)}")
    stats = achievements.record(party)
    definitions = {item['id']:item for item in DATA['achievements']}
    for identifier in requirements.get('achievements',[]):
        definition = definitions[identifier]
        condition = definition['condition']
        value = stats['max_level'] if condition == 'level' else stats['kills'] if condition == 'kills' else None
        unlocked = value >= definition['threshold'] if value is not None else definition['title'] in stats['titles']
        if not unlocked:
            missing.append('succès requis : '+definition['name'])
    states = quest_states(party)
    definitions = {item['id']:item for item in DATA['quests']}
    for identifier in requirements.get('quests',[]):
        definition = definitions[identifier]
        completed = party.get('quest') == 'completed' if is_hunt(definition) else states.get(identifier,{}).get('status') == 'completed'
        if not completed:
            missing.append('quête à terminer : '+definition['name'])
    return missing


def quest_dialogue(party, npc):
    from .tutorial import unpack, pack
    messages = []
    states = quest_states(party)
    for quest in DATA['quests']:
        if is_hunt(quest) or quest['npc'] != npc:
            continue
        state = states.get(quest['id'])
        if state is None:
            missing = missing_requirements(party,quest)
            if missing:
                messages.append(f"{quest['name']} inaccessible : {' ; '.join(missing)}.")
                continue
            states[quest['id']] = {'status': 'active', 'progress': 0}
            messages.append(f"Quête acceptée : {quest['name']} · {quest['description']}")
        elif state['status'] == 'active' and state['progress'] >= quest['count']:
            state['status'] = 'completed'
            for key, data in party['characters'].items():
                actor = unpack(data)
                if quest['reward_xp']:
                    actor.gain_exp(quest['reward_xp'])
                party['characters'][key] = pack(actor)
            messages.append(f"Quête terminée : {quest['name']} · {quest['reward_xp']} XP par joueur.")
        elif state['status'] == 'active':
            messages.append(f"{quest['name']} : {state['progress']}/{quest['count']}.")
    return messages


def quest_journal(party):
    quest_states(party)
    return [{**deepcopy(quest), **party.get('custom_quests', {}).get(quest['id'], {'status': 'available', 'progress': 0})} for quest in DATA['quests'] if not is_hunt(quest) and quest['id'] in party.get('custom_quests', {})]
