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


def validate_content(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULTS):
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
            for key in ('name', 'title') if section == 'achievements' else ('name', 'npc', 'target', 'description'):
                if not isinstance(item.get(key), str) or not 1 <= len(item[key]) <= (2000 if key == 'description' else 100):
                    raise ValueError(f'{key} : texte requis.')
            if section == 'quests':
                if item.get('kind') not in ('kill', 'craft') or type(item.get('count')) is not int or not 1 <= item['count'] <= 10000 or type(item.get('reward_xp')) is not int or not 0 <= item['reward_xp'] <= 100000 or not isinstance(item.get('zone', ''), str):
                    raise ValueError('Objectif ou récompense de quête invalide.')
            elif item.get('condition') not in CONDITIONS or not number(item.get('threshold'), .01, 100000):
                raise ValueError('Condition de succès invalide.')
    if not any(q['id'] == 'mira_hunt' and q['npc'] == 'mira' and q['kind'] == 'kill' and q['target'] == 'goblin' and q.get('zone') == 'lisiere' for q in data['quests']):
        raise ValueError('La quête de chasse de Mira est nécessaire au tutoriel.')
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
    return validate_content(data.get('content', data))


DATA = load_content()
WORLD = DATA['world']
HUNT = next(q for q in DATA['quests'] if q['id'] == 'mira_hunt')


def quest_event(party, kind, target, zone=None):
    states = party.setdefault('custom_quests', {})
    for quest in DATA['quests']:
        state = states.get(quest['id'])
        if quest['id'] != 'mira_hunt' and state and state['status'] == 'active' and quest['kind'] == kind and quest['target'] == target and (not quest.get('zone') or quest['zone'] == zone):
            state['progress'] = min(quest['count'], state['progress']+1)


def quest_dialogue(party, npc):
    from .tutorial import unpack, pack
    messages = []
    states = party.setdefault('custom_quests', {})
    for quest in DATA['quests']:
        if quest['id'] == 'mira_hunt' or quest['npc'] != npc:
            continue
        state = states.get(quest['id'])
        if state is None:
            states[quest['id']] = {'status': 'active', 'progress': 0}
            messages.append(f"Quête acceptée : {quest['name']} · {quest['description']}")
        elif state['status'] == 'active' and state['progress'] >= quest['count']:
            state['status'] = 'completed'
            for key, data in party['characters'].items():
                actor = unpack(data)
                actor.gain_exp(quest['reward_xp'])
                party['characters'][key] = pack(actor)
            messages.append(f"Quête terminée : {quest['name']} · {quest['reward_xp']} XP par joueur.")
        elif state['status'] == 'active':
            messages.append(f"{quest['name']} : {state['progress']}/{quest['count']}.")
    return messages


def quest_journal(party):
    return [{**deepcopy(quest), **party.get('custom_quests', {}).get(quest['id'], {'status': 'available', 'progress': 0})} for quest in DATA['quests'] if quest['id'] != 'mira_hunt' and quest['id'] in party.get('custom_quests', {})]
