from copy import deepcopy
import math
import re
import uuid

from .map_assets import validate
from .map_objects import place_portal


def create_zone(maps, key, name, width, height, biome, level, origin):
    if not re.fullmatch(r'[a-z0-9_]{1,64}', key) or key in maps:
        raise ValueError('Identifiant de zone invalide ou déjà utilisé.')
    if biome not in ('forest', 'village', 'cave'):
        raise ValueError('Ambiance de zone inconnue.')
    result = deepcopy(maps)
    result[key] = {'id': 'field_'+key, 'name': name, 'width': width, 'height': height, 'biome': biome, 'zone_id': key, 'zone_level': level, 'world_origin': list(origin), 'cell_metres': 2, 'cover': [], 'blocked': [], 'water': [], 'bridges': [], 'paths': [], 'decorations': [], 'spawns': [], 'spawners': [], 'sites': [], 'exits': [{'position': [0, height//2], 'destination': None, 'entry': None, 'name': 'Chemins rapides'}]}
    return validate(result)


def connect_maps(maps, source, destination, name, minutes, mode, point=None, entry=None, reverse=None, returning=None, bidirectional=False):
    if source == destination or source not in maps or destination not in maps:
        raise ValueError('Choisissez deux cartes différentes.')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise ValueError('Nom de liaison requis (100 caractères maximum).')
    if type(minutes) not in (int, float) or not math.isfinite(minutes) or not 0 <= minutes <= 10000:
        raise ValueError('Durée entre 0 et 10000 minutes en jeu.')
    if mode not in ('passage', 'trajet', 'rapide') or mode != 'passage' and minutes <= 0:
        raise ValueError('Un trajet demande une durée positive.')
    if mode == 'rapide':
        from . import world
        from .map_building import zone_of
        if zone_of(maps, source) != source or zone_of(maps, destination) != destination:
            raise ValueError('Les chemins rapides relient des zones racines. Pour les secteurs, choisissez un trajet.')
        result = deepcopy(maps)
        routes = result['clearing'].setdefault('travel_routes', deepcopy(world.ROUTES))
        routes.append({'id': 'link_'+uuid.uuid4().hex[:16], 'name': name.strip(), 'from': source, 'to': destination, 'distance_km': minutes/10, 'bidirectional': bidirectional})
    else:
        result = place_portal(maps, source, point, destination, entry, name, reverse if bidirectional else None, returning if bidirectional else None)
        link_id = uuid.uuid4().hex
        for key, position in [(source, point)] + ([(destination, reverse)] if bidirectional else []):
            gate = next(item for item in result[key]['exits'] if item['position'] == position)
            gate.update(link_id=link_id, travel_minutes=minutes if mode == 'trajet' else 0)
    return validate(result)


def links_from(maps, source):
    from . import world
    links = [('gate', index, gate['destination'], gate['name']) for index, gate in enumerate(maps[source]['exits']) if gate.get('destination')]
    for index, route in enumerate(maps['clearing'].get('travel_routes', world.ROUTES)):
        if route['from'] == source:
            links.append(('route', index, route['to'], route['name']))
        elif route['to'] == source and route.get('bidirectional', True):
            links.append(('route', index, route['from'], route['name']))
    return links


def remove_link(maps, source, kind, index, both=False):
    from . import world
    result = deepcopy(maps)
    if kind == 'gate':
        gate = result[source]['exits'].pop(index)
        if both and gate.get('destination'):
            target = result[gate['destination']]
            target['exits'] = [other for other in target['exits'] if not (other.get('destination') == source and (other.get('link_id') == gate['link_id'] if gate.get('link_id') else other.get('entry') == gate['position'] or other['position'] == gate.get('entry')))]
    elif kind == 'route':
        routes = result['clearing'].setdefault('travel_routes', deepcopy(world.ROUTES))
        route = routes[index]
        if route['id'] in {'clearing_rosee', 'rosee_lisiere', 'rosee_brume'}:
            raise ValueError('Ce chemin est nécessaire au tutoriel.')
        if both or not route.get('bidirectional', True):
            routes.pop(index)
        else:
            if route['from'] == source:
                route['from'], route['to'] = route['to'], route['from']
            route['bidirectional'] = False
    else:
        raise ValueError('Type de liaison inconnu.')
    for key, data in result.items():
        if not data['exits']:
            data['exits'] = [{'position': maps[key]['exits'][0]['position'][:], 'destination': None, 'entry': None, 'name': 'Chemins rapides'}]
    return validate(result)
