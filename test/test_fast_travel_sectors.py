from copy import deepcopy

from jeuxRPG.multiplayer import fields, tutorial, world
from jeuxRPG.multiplayer.service import GameError
from jeuxRPG.multiplayer.world_topology import compile_world


def test_village_graph_connects_attached_sectors(monkeypatch):
    maps = deepcopy(world.WORLD_MAP_DATA)
    maps['remote_forest'] = deepcopy(maps['forest'])
    maps['remote_forest'].update(name='Forêt', zone_id='rosee', sites=[], exits=[])
    maps['rosee']['exits'].append({'destination': 'remote_forest', 'entry': [1, 1]})
    maps['remote_forest']['exits'].append({'destination': 'rosee', 'entry': [1, 1]})
    monkeypatch.setattr(world, 'WORLD_MAP_DATA', maps)
    for name, value in zip(('PLACES', 'VILLAGE_STREETS', 'ROUTES', 'LEVELS', 'POINT_MAPS', 'ZONE_ENTRIES', 'EDGES'), compile_world(maps), strict=True):
        monkeypatch.setattr(world, name, value)
    graph = world.graph({'rosee'})
    assert 'rosee' in graph['remote_forest']
    assert world.validate_path('remote_forest', 'rosee', {'rosee'}, ['rosee'])


def test_leaving_second_map_unlocks_first_fast_travel(monkeypatch):
    party = tutorial.new_party([{'id': 'p', 'name': 'Test', 'class_name': 'Knight'}])
    tutorial.migrate(party, 0)
    fields.start(party, 0)
    fields.enter(party, 'forest', fields.arrival_point('forest'), 1)
    gate = next(g for g in fields.MAPS['forest']['exits'] if g['destination'] is None)
    fields.transition(party, gate, 'p', 2)
    assert party['step'] == 'road'
    assert party.get('battle') is None
    known = {p['id'] for p in world.view(party, 'p')['places']}
    route = world.path(party['position'], 'rosee', known)
    assert route is not None
    tutorial.execute(party, 'p', 'move', {'destination': 'rosee', 'paths': {party['position']: route}}, 3, GameError, lambda: .99)
    for now in range(1000, 31000, 1000):
        tutorial.advance(party, now, lambda: .99)
        if party.get('field_map'):
            break
    assert party['field_map'] == 'rosee'


def test_fast_origin_same_as_destination_enters_village_instead_of_noop(monkeypatch):
    maps = deepcopy(fields.MAPS)
    maps['forest']['fast_travel_origin'] = 'rosee'
    monkeypatch.setattr(fields, 'MAPS', maps)
    party = tutorial.new_party([{'id': 'p', 'name': 'Test', 'class_name': 'Knight'}])
    tutorial.migrate(party, 0)
    fields.start(party, 0)
    fields.enter(party, 'forest', fields.arrival_point('forest'), 1)
    gate = next(g for g in maps['forest']['exits'] if g['destination'] is None)
    fields.transition(party, gate, 'p', 2)
    assert party['position'] == 'rosee'
    tutorial.execute(party, 'p', 'move', {'destination': 'rosee', 'paths': {'rosee': []}}, 3, GameError, lambda: .99)
    assert party['field_map'] == 'rosee'
    assert party['step'] == 'village'
