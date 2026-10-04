from copy import deepcopy
from types import SimpleNamespace

import pytest

from test_map_assembly import maps
from jeuxRPG.multiplayer.map_links import create_zone, connect_maps, remove_link, links_from
from jeuxRPG.multiplayer.map_viewport import assembly_bounds, zoom_canvas
from jeuxRPG.multiplayer import world


def test_zone_creation_is_atomic_and_has_own_level():
    data = maps()
    before = deepcopy(data)
    result = create_zone(data, 'new_cave', 'Grotte', 20, 12, 'cave', 8, [-30, -20])
    assert data == before
    assert result['new_cave']['zone_id'] == 'new_cave'
    assert result['new_cave']['zone_level'] == 8
    assert result['new_cave']['world_origin'] == [-30, -20]
    with pytest.raises(ValueError):
        create_zone(data, 'clearing', 'Doublon', 20, 12, 'cave', 8, [0, 0])


def linked():
    return connect_maps(maps(), 'assembly_a', 'assembly_b', 'Sentier', 2, 'trajet', [2, 2], [3, 2], [4, 2], [5, 2], True)


def test_graphical_points_and_duration_are_saved_for_both_directions():
    result = linked()
    a, b = result['assembly_a']['exits'][-1], result['assembly_b']['exits'][-1]
    assert a['entry'] == [3, 2] and b['entry'] == [5, 2]
    assert a['position'] == [2, 2] and b['position'] == [4, 2]
    assert a['link_id'] == b['link_id']
    assert a['travel_minutes'] == b['travel_minutes'] == 2


@pytest.mark.parametrize('both', [False, True])
def test_remove_passage_direction_preserves_unrelated_exits(both):
    data = linked()
    result = remove_link(data, 'assembly_a', 'gate', 1, both)
    assert len(result['assembly_a']['exits']) == 1
    assert len(result['assembly_b']['exits']) == (1 if both else 2)
    assert len(data['assembly_a']['exits']) == 2


@pytest.mark.parametrize('minutes', [-1, float('nan'), float('inf'), 10001])
def test_invalid_travel_time_is_rejected_atomically(minutes):
    data = maps()
    before = deepcopy(data)
    with pytest.raises(ValueError):
        connect_maps(data, 'assembly_a', 'assembly_b', 'Sentier', minutes, 'trajet', [2, 2], [3, 2])
    assert data == before


def test_fast_route_without_portals_supports_independent_directions(monkeypatch):
    data = create_zone(maps(), 'new_zone', 'Zone', 20, 12, 'forest', 2, [100, 100])
    old_exits = deepcopy(data['clearing']['exits'])
    result = connect_maps(data, 'clearing', 'new_zone', 'Route', 4, 'rapide', bidirectional=True)
    routes = result['clearing']['travel_routes']
    assert result['clearing']['exits'] == old_exits
    assert routes[-1]['distance_km'] == .4
    one_way = remove_link(result, 'clearing', 'route', len(routes)-1)
    route = one_way['clearing']['travel_routes'][-1]
    assert (route['from'], route['to'], route['bidirectional']) == ('new_zone', 'clearing', False)
    monkeypatch.setattr(world, 'ROUTES', one_way['clearing']['travel_routes'])
    monkeypatch.setitem(world.PLACES, 'new_zone', {'name': 'Zone', 'points': []})
    graph = world.graph(['clearing', 'new_zone'])
    assert route['id'] not in graph['clearing']
    assert route['id'] in graph['new_zone']
    assert graph[route['id']] == ['clearing']
    assert links_from(one_way, 'new_zone')[-1][2] == 'clearing'
    deleted = remove_link(one_way, 'new_zone', 'route', len(routes)-1)
    assert len(deleted['clearing']['travel_routes']) == len(routes)-1


def test_assembly_bounds_expand_without_recentring_existing_coordinates():
    data = {'a': {'width': 20, 'height': 20}}
    initial = assembly_bounds(data, {'a': [0, 0]})
    expanded = assembly_bounds(data, {'a': [-200, -300]}, initial)
    assert expanded[:2] == (-300, -400)
    assert assembly_bounds(data, {'a': [10, 10]}, expanded) == expanded


def test_zoom_preserves_pointer_world_position():
    moves = []
    canvas = SimpleNamespace(canvasx=lambda x: x+100, canvasy=lambda y: y+200, cget=lambda name: '-1000 -1000 2000 2000', xview_moveto=lambda value: moves.append(value), yview_moveto=lambda value: moves.append(value))
    zoom_canvas(canvas, 10, 20, lambda: None, 50, 80)
    assert moves == pytest.approx([(300-50+1000)/3000, (560-80+1000)/3000])


@pytest.mark.parametrize('cancel_at', [0, 1, 2, 3, None])
def test_graphical_connection_cancel_is_atomic_and_four_points_are_independent(monkeypatch, cancel_at):
    from jeuxRPG.multiplayer.map_assembly import AssemblyWindow
    from jeuxRPG.multiplayer import map_objects
    data = maps()
    before = deepcopy(data)
    picks = [('assembly_a', [2, 2]), ('assembly_b', [3, 2]), ('assembly_b', [4, 2]), ('assembly_a', [5, 2])]
    calls, applied = [], []
    def pick(editor, title, fixed_map):
        index = len(calls)
        calls.append(fixed_map)
        return None if index == cancel_at else picks[index]
    monkeypatch.setattr(map_objects, 'pick_cell', pick)
    forms = iter([{'link_mode': 'trajet', 'name': 'Sentier'}, {'travel_minutes': '2'}])
    window = AssemblyWindow.__new__(AssemblyWindow)
    window.editor = SimpleNamespace(maps=data, form=lambda *args: next(forms))
    window.window = None
    window.link_source = 'assembly_a'
    window.info = SimpleNamespace(set=lambda value: None)
    window.messagebox = SimpleNamespace(askyesno=lambda *args, **kwargs: True, showerror=lambda *args, **kwargs: pytest.fail(str(args)))
    window.apply = applied.append
    window.finish_connect('assembly_b')
    assert data == before
    assert window.link_source is None
    if cancel_at is None:
        assert calls == ['assembly_a', 'assembly_b', 'assembly_b', 'assembly_a']
        assert applied[0]['assembly_a']['exits'][-1]['entry'] == [3, 2]
    else:
        assert not applied
