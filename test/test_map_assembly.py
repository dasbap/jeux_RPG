from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeuxRPG.multiplayer.map_assembly import align, merge, positions
from jeuxRPG.multiplayer.map_assets import validate


def maps():
    data = json.loads((Path(__file__).parent / 'fixtures' / 'fields.json').read_text())
    for key, x in [('assembly_a', 10), ('assembly_b', 18)]:
        data[key] = {'id': 'field_'+key, 'name': key, 'width': 8, 'height': 6, 'zone_id': 'clearing', 'world_origin': [x, 10], 'cover': [], 'blocked': [], 'water': [], 'paths': [], 'bridges': [], 'decorations': [], 'spawns': [], 'sites': [], 'spawners': [], 'exits': [{'position': [0, 2], 'destination': 'clearing', 'entry': [1, 10], 'name': 'Sortie'}]}
    return data


@pytest.mark.parametrize('direction,gap,expected', [('est', 0, [18,10]), ('est', 5, [23,10]), ('ouest', 0, [2,10]), ('sud', 0, [10,16]), ('nord', 0, [10,4]), ('est', -2, [16,10])])
def test_align_blocks_in_each_direction_with_spacing_and_overlap(direction, gap, expected):
    data = maps()
    before = deepcopy(data)
    result = align(data, 'assembly_b', 'assembly_a', direction, gap)
    assert result['assembly_b']['world_origin'] == expected
    assert data == before
    assert result['assembly_b']['exits'] == data['assembly_b']['exits']


def test_merge_offsets_entities_patrols_and_external_arrivals():
    data = maps()
    data['assembly_b'].update(spawns=[[3,3]], spawners=[{'position':[3,3], 'mob_id':'orc', 'level':5, 'patrol':[[4,3]]}], sites=[{'position':[4,4], 'id':'guide', 'name':'Guide', 'dialogue':'Bonjour'}])
    data['clearing']['exits'].append({'position':[0,10], 'destination':'assembly_b', 'entry':[1,1], 'name':'Vers bloc'})
    before = deepcopy(data)
    result = merge(data, 'assembly_a', 'assembly_b')
    assert data == before
    assert 'assembly_b' not in result
    combined = result['assembly_a']
    assert (combined['width'], combined['height']) == (16,6)
    assert combined['spawns'] == [[11,3]]
    assert combined['spawners'][0]['patrol'] == [[12,3]]
    assert combined['sites'][0]['position'] == [12,4]
    assert result['clearing']['exits'][-1]['entry'] == [9,1]
    assert result['clearing']['exits'][-1]['destination'] == 'assembly_a'
    validate(result)


def test_merge_with_negative_origin_offsets_target_and_removes_internal_passages():
    data = maps()
    data['assembly_b']['world_origin'] = [2,10]
    data['assembly_a']['exits'].append({'position':[7,2], 'destination':'assembly_b', 'entry':[1,2], 'name':'Interne'})
    data['clearing']['exits'].append({'position':[0,10], 'destination':'assembly_a', 'entry':[1,1], 'name':'Externe'})
    result = merge(data, 'assembly_a', 'assembly_b')
    assert result['assembly_a']['world_origin'] == [2,10]
    assert result['clearing']['exits'][-1]['entry'] == [9,1]
    assert all(g['destination'] == 'clearing' for g in result['assembly_a']['exits'])


def test_overlap_preserves_target_terrain_and_rejects_conflicting_spawners():
    data = maps()
    data['assembly_b']['world_origin'] = [14,10]
    data['assembly_b'].update(cover=[[0,1]], decorations=[{'position':[0,1], 'kind':'tree'}])
    result = merge(data, 'assembly_a', 'assembly_b')
    assert not result['assembly_a']['cover']
    assert not result['assembly_a']['decorations']
    data['assembly_a']['spawns'] = [[5,3]]
    data['assembly_b']['spawns'] = [[1,3]]
    with pytest.raises(ValueError, match='spawners'):
        merge(data, 'assembly_a', 'assembly_b')


@pytest.mark.parametrize('change', ['size', 'zone', 'core'])
def test_invalid_merge_is_atomic(change):
    data = maps()
    if change == 'size':
        data['assembly_b']['world_origin'] = [200,10]
    elif change == 'zone':
        data['assembly_b']['zone_id'] = 'rosee'
    before = deepcopy(data)
    with pytest.raises(ValueError):
        merge(data, 'assembly_a', 'clearing' if change == 'core' else 'assembly_b')
    assert before == data


def test_default_layout_is_stable_and_does_not_mutate():
    data = maps()
    del data['assembly_b']['world_origin']
    assert positions(data) == positions(data)
    assert 'world_origin' not in data['assembly_b']


def test_drag_snap_saves_one_undo_snapshot_and_keeps_local_data():
    from types import SimpleNamespace
    from jeuxRPG.multiplayer.map_assembly import AssemblyWindow
    data = maps()
    history, moves = [], []
    window = AssemblyWindow.__new__(AssemblyWindow)
    window.editor = SimpleNamespace(maps=data, remember=lambda: history.append(deepcopy(data)))
    window.selected = 'assembly_a'
    window.scale = 8
    window.dragging = (0,0,[10,10],False)
    window.canvas = SimpleNamespace(canvasx=lambda x:x, canvasy=lambda y:y, move=lambda *args:moves.append(args))
    window.drag(SimpleNamespace(x=17,y=7))
    window.drag(SimpleNamespace(x=25,y=17))
    assert len(history) == 1
    assert data['assembly_a']['world_origin'] == [13,12]
    assert data['assembly_a']['exits'] == history[0]['assembly_a']['exits']
    assert moves[-1] == ('map:assembly_a',8,8)
    window.draw = lambda:None
    window.release(None)
    assert window.dragging is None
    assert window.last_dx == window.last_dy == 0


def test_merge_preserves_implicit_spawner_level():
    data = maps()
    data['assembly_b'].update(level=8, spawns=[[3,3]])
    result = merge(data, 'assembly_a', 'assembly_b')
    assert result['assembly_a']['spawners'][0]['level'] == 8
