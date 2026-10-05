from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeuxRPG.multiplayer.map_objects import move_object, objects_at, place_portal
from jeuxRPG.multiplayer.map_assembly import align, merge
from jeuxRPG.multiplayer.map_world_editor import world_metadata
from jeuxRPG.multiplayer import world, tactics


def maps():
    return json.loads((Path(__file__).parent/'fixtures'/'fields.json').read_text())


def test_portal_explicit_click_coordinates_and_return_are_saved():
    data = maps()
    before = deepcopy(data)
    result = place_portal(data,'clearing',[2,10],'rosee',[2,20],'Vers Rosée',[3,20],[3,10])
    assert data == before
    assert result['clearing']['exits'][-1]['entry'] == [2,20]
    assert result['rosee']['exits'][-1]['entry'] == [3,10]
    assert result['rosee']['exits'][-1]['position'] == [3,20]


@pytest.mark.parametrize('reverse,returning', [([2,20],[3,10]),([3,20],[2,10]),([3,20],[29,10])])
def test_portal_return_rejects_loops_without_mutation(reverse, returning):
    data = maps()
    before = deepcopy(data)
    with pytest.raises(ValueError):
        place_portal(data,'clearing',[2,10],'rosee',[2,20],'Vers Rosée',reverse,returning)
    assert data == before


def test_move_portal_and_npc_preserves_properties():
    data = maps()
    result = move_object(data,'clearing','exits',0,None,[28,10])
    assert result['clearing']['exits'][0]['position'] == [28,10]
    assert result['clearing']['exits'][0]['entry'] == data['clearing']['exits'][0]['entry']
    result = move_object(data,'rosee','sites',0,None,[33,20])
    assert result['rosee']['sites'][0]['position'] == [33,20]
    assert result['rosee']['sites'][0]['id'] == data['rosee']['sites'][0]['id']


def test_move_spawn_moves_patrol_and_individual_waypoint():
    data = maps()
    data['clearing']['cover'] = [p for p in data['clearing']['cover'] if p != [18,10]]
    data['clearing']['decorations'] = [d for d in data['clearing']['decorations'] if d['position'] != [18,10]]
    data['clearing']['spawns'] = [[17,10]]
    data['clearing']['spawners'] = [{'position':[17,10],'mob_id':'goblin','patrol':[[18,10],[19,10]]}]
    result = move_object(data,'clearing','spawners',0,None,[16,10])
    assert result['clearing']['spawns'] == [[16,10]]
    assert result['clearing']['spawners'][0]['patrol'] == [[17,10],[18,10]]
    result = move_object(result,'clearing','spawners',0,1,[19,10])
    assert result['clearing']['spawners'][0]['patrol'][1] == [19,10]
    assert objects_at(result['clearing'],[19,10])[0][3] == 1


def test_move_rejects_blocked_cell_and_keeps_original():
    data = maps()
    before = deepcopy(data)
    with pytest.raises(ValueError):
        move_object(data,'clearing','exits',0,None,data['clearing']['cover'][0])
    assert data == before


def test_cave_rooms_can_merge_and_external_entries_are_remapped():
    data = maps()
    data = align(data,'cave_2','cave_1','est',0)
    result = merge(data,'cave_1','cave_2')
    assert 'cave_2' not in result
    assert result['cave_3']['exits'][0]['destination'] == 'cave_1'
    result = align(result,'cave_3','cave_1','est',0)
    result = merge(result,'cave_1','cave_3')
    assert 'cave_3' not in result
    assert result['cave_1']['width'] == 66
    assert len(result['cave_1']['spawns']) == 4


def test_world_routes_distances_and_street_order_can_be_configured():
    data = maps()
    data['clearing']['travel_routes'] = deepcopy(world.ROUTES)
    data['clearing']['travel_routes'][0]['distance_km'] = 1.2
    data['rosee']['village_streets'] = {'square':'mira','streets':[{'id':'rosee_new','name':'Rue neuve','buildings':['training','forge']}]}
    streets, routes = world_metadata(data,world.VILLAGE_STREETS,world.ROUTES)
    assert routes[0]['distance_km'] == 1.2
    assert streets['rosee']['streets'][0]['buildings'] == ['training','forge']


def test_invalid_route_and_duplicate_buildings_are_rejected():
    data = maps()
    data['clearing']['travel_routes'] = deepcopy(world.ROUTES)
    data['clearing']['travel_routes'][0]['distance_km'] = float('nan')
    with pytest.raises(ValueError):
        world_metadata(data,world.VILLAGE_STREETS,world.ROUTES)
    del data['clearing']['travel_routes']
    data['rosee']['village_streets'] = {'square':'mira','streets':[{'id':'new','name':'Rue','buildings':['forge','forge']}]}
    with pytest.raises(ValueError):
        world_metadata(data,world.VILLAGE_STREETS,world.ROUTES)


def test_configured_world_changes_actual_travel_and_city_graph(tmp_path):
    import os
    import subprocess
    import sys
    data = maps()
    data['clearing']['travel_routes'] = deepcopy(world.ROUTES)
    data['clearing']['travel_routes'][0]['distance_km'] = 1.2
    data['rosee']['village_streets'] = {'square':'mira','streets':[{'id':'rosee_new','name':'Rue neuve','buildings':['training','forge']}]}
    path = tmp_path/'world.json'
    path.write_text(json.dumps(data))
    result = subprocess.run([sys.executable,'-c',"from jeuxRPG.multiplayer import fields, world; assert abs(world.walking_seconds('clearing','clearing_rosee') - 360) < .001; assert 'training' in world.graph(['rosee'])['forge']; assert world.VILLAGE_STREETS['rosee']['streets'][0]['name'] == 'Rue neuve'"],env={**os.environ,'RPG_MAPS_FILE':str(path)},capture_output=True,text=True)
    assert result.returncode == 0, result.stderr


def test_saved_session_in_absorbed_cave_does_not_crash(monkeypatch):
    from jeuxRPG.multiplayer import fields, tutorial
    party = tutorial.new_party([{'id':'p','name':'Test','class_name':'Knight'}])
    fields.start(party,0)
    fields.enter(party,'cave_2',[1,7],1)
    monkeypatch.delitem(tactics.PRESETS,'field_cave_2')
    fields.migrate_terrain(party)
    assert party['battle'] is None
    assert party['position'] == 'cave_1'
    assert 'field_map' not in party
    tutorial.view(party,'p',2)
