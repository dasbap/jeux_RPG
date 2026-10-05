from copy import deepcopy
import uuid
import json
from pathlib import Path

import pytest

from jeuxRPG.multiplayer import fields, tutorial, tactics, world
from jeuxRPG.multiplayer.service import GameError, GameService


@pytest.fixture(autouse=True)
def stable_field_scenarios(monkeypatch):
    maps = json.loads((Path(__file__).parent / "fixtures" / "fields.json").read_text())
    monkeypatch.setattr(fields, "MAPS", maps)
    places = deepcopy(world.PLACES)
    for key, definition in maps.items():
        zone = fields.zone_of(maps, key)
        if key != zone and not any(point['id'] == key for place in places.values() for point in place['points']):
            places[zone]['points'].append({'id': key, 'name': definition['name'], 'kind': 'field'})
    monkeypatch.setattr(world, 'PLACES', places)
    for definition in maps.values():
        monkeypatch.setitem(tactics.PRESETS, definition["id"], definition)


def party():
    data = tutorial.new_party([{"id": "p", "name": "Test", "class_name": "Knight"}])
    fields.start(data, 0)
    return data


@pytest.mark.parametrize("identifier", fields.MAPS)
def test_fixed_maps_have_connected_walkable_gates_sites_and_spawns(identifier):
    definition = fields.MAPS[identifier]
    entry = [1, 20] if identifier == "rosee" else [1, 16] if identifier == "brume" else [1, 10]
    for point in [*[gate["position"] for gate in definition["exits"]], *definition["spawns"], *[site["position"] for site in definition["sites"]]]:
        assert tactics.walkable(definition, point)
        assert tactics.path(definition, entry, point) is not None
    for gate in definition["exits"]:
        if gate["destination"]:
            assert tactics.walkable(fields.MAPS[gate["destination"]], gate["entry"])


def test_cave_has_three_rooms_and_only_a_return_at_its_end():
    assert [gate["destination"] for gate in fields.MAPS["cave_1"]["exits"]] == ["rosee", "cave_2", "lisiere"]
    assert [gate["destination"] for gate in fields.MAPS["cave_2"]["exits"]] == ["cave_1", "cave_3"]
    assert [gate["destination"] for gate in fields.MAPS["cave_3"]["exits"]] == ["cave_2"]


def test_fixed_mobs_and_terrain_survive_return_without_respawn():
    data = party()
    first_id = data["mobs"][0]["combat_id"]
    data["mobs"][0]["stats"]["hp"]["current"] = 5
    gate = fields.MAPS["clearing"]["exits"][0]
    fields.transition(data, gate, "p", 1)
    assert data["field_map"] == "clearing_trail"
    fields.enter(data, "clearing", [1, 10], 2)
    assert data["mobs"][0]["combat_id"] == first_id
    assert data["mobs"][0]["stats"]["hp"]["current"] == 5
    assert data["battle"]["preset"] == "field_clearing"
    enemy = data["mobs"].pop()
    tactics.defeated(data, enemy, 3, lambda: .99, [])
    fields.transition(data, gate, "p", 4)
    fields.enter(data, "clearing", [1, 10], 5)
    assert data["mobs"] == []
    assert len(data["battle"]["corpses"]) == 1


def test_only_enemies_who_see_the_exit_can_pursue_and_complete_exit_stops_them():
    data = party()
    fields.enter(data, "hunt", [1, 10], 10)
    gate = fields.MAPS["hunt"]["exits"][1]
    data["battle"]["players"]["p"]["position"] = gate["position"][:]
    enemies = data["mobs"]
    enemies[0].update(position=[28, 10], alerted=True)
    enemies[1].update(position=[1, 1], alerted=True)
    enemies[2].update(position=[28, 11], alerted=False)
    follower = enemies[0]["combat_id"]
    messages = fields.transition(data, gate, "p", 11)
    assert data["field_map"] == "forest"
    assert follower not in {mob["combat_id"] for mob in data["mobs"]}
    assert len(data["battle"]["arrivals"]) == 1
    assert "arrivals" not in tutorial.view(data, "p", 11)["battle"]
    fields.advance(data, 20)
    assert follower in {mob["combat_id"] for mob in data["mobs"]}
    assert follower not in {mob["combat_id"] for mob in data["fields"]["hunt"]["mobs"]}
    assert len(data["fields"]["hunt"]["mobs"]) == 2
    assert any("poursuivent" in message for message in messages)
    full_exit = fields.MAPS["forest"]["exits"][-1]
    fields.transition(data, full_exit, "p", 12)
    assert data["battle"] is None and data["mobs"] == []
    assert "field_map" not in data


def test_stunned_or_blinded_by_cover_enemy_does_not_follow():
    data = party()
    fields.enter(data, "hunt", [1, 10], 0)
    gate = fields.MAPS["hunt"]["exits"][1]
    unit = data["battle"]["players"]["p"]
    unit.update(position=gate["position"][:], hidden=True)
    for enemy in data["mobs"]:
        enemy.update(position=[25, 10], alerted=True)
    data["mobs"][0].update(position=[28, 10], stunned_until=100)
    identifiers = {enemy["combat_id"] for enemy in data["mobs"]}
    fields.transition(data, gate, "p", 1)
    assert identifiers.isdisjoint({enemy["combat_id"] for enemy in data["mobs"]})


def test_gate_transition_runs_from_authoritative_movement_and_old_paths_are_rejected():
    data = party()
    fields.enter(data, "cave_1", [20, 7], 0)
    tactics.execute(data, "p", "battle_move", {"x": 21, "y": 7, "path": [[21, 7]]}, 0, GameError)
    tactics.advance(data, 2, lambda: .5)
    assert data["field_map"] == "cave_2"
    assert data["battle"]["players"]["p"]["position"] == [1, 7]
    with pytest.raises(GameError, match="Trajet bloqué"):
        tactics.execute(data, "p", "battle_move", {"x": 21, "y": 7, "path": [[21, 7]]}, 3, GameError)


def test_village_requires_proximity_for_quest_and_forge_and_restores_map():
    data = party()
    data["step"] = "road"
    fields.enter(data, "rosee", [1, 20], 0)
    with pytest.raises(GameError) as failure:
        tutorial.execute(data, "p", "talk", {"npc": "mira"}, 0, GameError, lambda: .5)
    assert failure.value.code == "wrong_location"
    data["battle"]["players"]["p"]["position"] = [32, 20]
    tutorial.execute(data, "p", "talk", {"npc": "mira"}, 1, GameError, lambda: .5)
    assert data["quest"] == "active"
    data["kills"] = 3
    tutorial.execute(data, "p", "talk", {"npc": "mira"}, 2, GameError, lambda: .5)
    assert data["quest"] == "completed"
    data["battle"]["players"]["p"]["position"] = [44, 12]
    data["inventory"]["p"] = {"peau": 2, "croc": 3}
    tutorial.execute(data, "p", "craft", {"recipe": "veste"}, 3, GameError, lambda: .5)
    assert data["step"] == "travel"
    assert data["battle"] and data["position"] == "rosee"
    assert "fields" not in tutorial.view(data, "p", 3)


def test_service_starts_fixed_forest_and_rejects_invalid_mode(tmp_path):
    service = GameService(tmp_path / "state.sqlite3")
    try:
        player = service.register("Tester", "Knight")
        with pytest.raises(GameError):
            service.command(player["token"], uuid.uuid4().hex, "tutorial", field_mode="yes")
        result = service.command(player["token"], uuid.uuid4().hex, "tutorial", field_mode=True)
        state = result["session"]["tutorial"]
        assert state["field_map"] == "clearing"
        assert state["battle"]["map"]["id"] == "field_clearing"
        assert state["mobs"] == []
        assert "fields" not in state
    finally:
        service.close()


def test_total_defeat_clears_field_mode_view_without_erasing_zone_enemies():
    data = party()
    for character in data["characters"].values():
        character["stats"]["hp"]["current"] = 0
    tactics.advance(data, 2, lambda: .5)
    assert data["battle"] is None
    assert "field_map" not in data
    assert data["fields"]["clearing"]["mobs"]
    assert tutorial.view(data, "p", 3)["battle"] is None


def test_exploration_reveals_terrain_without_disclosing_unseen_enemies():
    data = party()
    state = tutorial.view(data, "p", 0)
    assert state["mobs"] == []
    assert [29, 10] not in state["battle"]["explored"]
    data["battle"]["players"]["p"]["position"] = [24, 10]
    fields.reveal(data)
    assert [29, 10] in tutorial.view(data, "p", 1)["battle"]["explored"]


def test_unloaded_zone_regeneration_keeps_fractional_minutes_without_double_heal():
    data = party()
    data["mobs"][0]["stats"]["hp"].update(max=100, current=50)
    fields.transition(data, fields.MAPS["clearing"]["exits"][0], "p", 1)
    fields.enter(data, "clearing", [1, 10], 121)
    assert data["mobs"][0]["stats"]["hp"]["current"] == 52
    tutorial.progression.health_resources(data, 121)
    assert data["mobs"][0]["stats"]["hp"]["current"] == 52


def test_fixed_zone_quest_counts_prior_kills_so_cleared_maps_cannot_block_it():
    data = party()
    data.update(step="road", zone_kills={"lisiere": 3})
    fields.enter(data, "rosee", [32, 20], 0)
    tutorial.execute(data, "p", "talk", {"npc": "mira"}, 1, GameError, lambda: .5)
    assert data["kills"] == 3
    tutorial.execute(data, "p", "talk", {"npc": "mira"}, 2, GameError, lambda: .5)
    assert data["quest"] == "completed"


def test_repop_requires_three_full_game_minutes_without_players():
    data = party()
    enemy = data["mobs"].pop()
    tactics.defeated(data, enemy, 1, lambda: .99, [])
    gate = fields.MAPS["clearing"]["exits"][0]
    fields.transition(data, gate, "p", 2)
    fields.enter(data, "clearing", [1, 10], 181)
    assert data["mobs"] == []
    fields.transition(data, gate, "p", 182)
    fields.enter(data, "clearing", [1, 10], 362)
    assert len(data["mobs"]) == 1
    assert data["mobs"][0]["combat_id"] != enemy["combat_id"]
    assert data["mobs"][0]["stats"]["hp"]["current"] == data["mobs"][0]["stats"]["hp"]["max"]
    assert data["battle"]["corpses"][0]["id"] == enemy["combat_id"]
    assert data["mobs"][0]["position"] == fields.MAPS["clearing"]["spawns"][0]


def test_no_repop_while_players_remain_in_zone():
    data = party()
    enemy = data["mobs"].pop()
    tactics.defeated(data, enemy, 1, lambda: .99, [])
    tutorial.sync_mobs(data)
    tutorial.advance(data, 1000, lambda: .5)
    assert data["field_map"] == "clearing"
    assert data["mobs"] == []


def test_repop_keeps_survivors_and_does_not_duplicate_a_pursuer():
    data = party()
    fields.enter(data, "hunt", [1, 10], 0)
    gate = fields.MAPS["hunt"]["exits"][1]
    data["battle"]["players"]["p"]["position"] = gate["position"][:]
    follower, survivor, dead = data["mobs"]
    follower.update(position=[28, 10], alerted=True)
    survivor.update(position=[2, 2], alerted=False)
    survivor["stats"]["hp"]["current"] = 10
    data["mobs"].remove(dead)
    tactics.defeated(data, dead, 1, lambda: .99, [])
    fields.transition(data, gate, "p", 2)
    fields.advance(data, 20)
    fields.transition(data, fields.MAPS["forest"]["exits"][-1], "p", 21)
    fields.enter(data, "hunt", [1, 10], 182)
    origins = [mob["combat_id"].split(":repop:")[0] for mob in data["mobs"]]
    assert follower["combat_id"] not in origins
    assert origins.count(survivor["combat_id"]) == 1
    assert origins.count(dead["combat_id"]) == 1


def test_player_vision_is_twelve_cells_and_does_not_increase_mob_detection(monkeypatch):
    data = party()
    definition = deepcopy(fields.MAPS["clearing"])
    definition["cover"] = [p for p in definition["cover"] if p[1] != 10]
    monkeypatch.setitem(tactics.PRESETS, definition["id"], definition)
    data["battle"]["players"]["p"]["position"] = [1, 10]
    enemy = data["mobs"][0]
    enemy["position"] = [13, 10]
    assert tactics.visible(data, "p", enemy)
    assert not tactics.sees(definition, enemy, data["battle"]["players"]["p"])
    enemy["position"] = [14, 10]
    assert not tactics.visible(data, "p", enemy)
    fields.reveal(data)
    assert [13, 10] in data["battle"]["explored"]
    assert [14, 10] not in data["battle"]["explored"]
    enemy["position"] = [29, 2]
    assert not tactics.visible(data, "p", enemy)


def test_fast_travel_reaches_camp_without_entering_intermediate_village():
    data = party()
    fields.enter(data, "clearing_road", [28, 10], 1)
    fields.transition(data, fields.MAPS["clearing_road"]["exits"][-1], "p", 1)
    data.update(step="hunt", quest="active", visited=["clearing", "rosee", "lisiere"])
    tutorial.execute(data, "p", "travel", {"destination": "hunt"}, 2, GameError, lambda: .99)
    for instant in range(1000, 31000, 1000):
        tutorial.advance(data, instant, lambda: .99)
        if data.get("field_map"):
            break
    assert data["field_map"] == "hunt"
    assert data["battle"]["preset"] == "field_hunt"


def test_complete_exit_and_reentry_return_through_the_same_gate():
    data = party()
    fields.enter(data, "rosee", [62, 30], 0)
    passage = fields.MAPS["rosee"]["exits"][-1]
    fields.transition(data, passage, "p", 1)
    tutorial.execute(data, "p", "enter_zone", {}, 2, GameError, lambda: .5)
    assert data["battle"]["players"]["p"]["position"] == [62, 30]
    assert fields.arrival_point("rosee", "rosee_lisiere") == [62, 20]
    assert fields.arrival_point("clearing", "clearing_rosee") == [28, 10]


def test_river_blocks_player_and_mob_routes_but_not_line_of_sight():
    definition = fields.MAPS["clearing"]
    river = next(point for point in definition["blocked"] if tactics.walkable(definition, [point[0] - 3, point[1]]) and tactics.walkable(definition, [point[0] + 3, point[1]]) and tactics.sight(definition, [point[0] - 3, point[1]], [point[0] + 3, point[1]]))
    source = [river[0] - 3, river[1]]
    target = [river[0] + 3, river[1]]
    assert not tactics.walkable(definition, river)
    assert tactics.sight(definition, source, target)
    route = tactics.path(definition, source, target)
    assert route and river not in route
    assert all(tactics.walkable(definition, point) for point in route)
    bridge = definition["bridges"][0]
    assert tactics.walkable(definition, bridge)
    data = party()
    data["battle"]["players"]["p"]["position"] = source
    with pytest.raises(GameError):
        tactics.execute(data, "p", "battle_move", {"x": river[0], "y": river[1], "path": [river]}, 1, GameError)


def test_existing_save_migrates_entities_off_new_water_and_clears_old_routes():
    data = party()
    river = fields.MAPS["clearing"]["blocked"][0]
    data["battle"].pop("terrain_version", None)
    data["battle"]["players"]["p"].update(position=river[:], route=[river[:]])
    tutorial.migrate(data, 1)
    assert tactics.walkable(fields.MAPS["clearing"], data["battle"]["players"]["p"]["position"])
    assert data["battle"]["players"]["p"]["route"] == []


def test_three_starting_maps_overlap_with_identical_terrain_and_decorations():
    for first, second in (("clearing", "clearing_trail"), ("clearing_trail", "clearing_road")):
        left, right = fields.MAPS[first], fields.MAPS[second]
        assert right["world_origin"][0] - left["world_origin"][0] == 26
        for field in ("cover", "water", "bridges", "blocked", "paths"):
            assert {(x - 26, y) for x, y in left[field] if x >= 26} == {(x, y) for x, y in right[field] if x < 4}
        assert {(item["position"][0] - 26, item["position"][1], item["kind"]) for item in left["decorations"] if item["position"][0] >= 26} == {(item["position"][0], item["position"][1], item["kind"]) for item in right["decorations"] if item["position"][0] < 4}
        assert left["bridges"] and right["bridges"]


def test_initial_forest_route_can_be_crossed_reversed_and_rejoined_after_full_exit():
    data = party()
    data["mobs"] = []
    fields.transition(data, fields.MAPS["clearing"]["exits"][0], "p", 1)
    assert data["field_map"] == "clearing_trail"
    fields.transition(data, fields.MAPS["clearing_trail"]["exits"][0], "p", 2)
    assert data["field_map"] == "clearing"
    fields.transition(data, fields.MAPS["clearing"]["exits"][0], "p", 3)
    fields.transition(data, fields.MAPS["clearing_trail"]["exits"][-1], "p", 4)
    assert data["field_map"] == "clearing_road"
    fields.transition(data, fields.MAPS["clearing_road"]["exits"][-1], "p", 5)
    assert data["battle"] is None
    assert data["position"] == "clearing"
    assert data["step"] == "road"
    tutorial.execute(data, "p", "enter_zone", {}, 6, GameError, lambda: .99)
    assert data["field_map"] == "clearing_road"
    assert data["battle"]["players"]["p"]["position"] == [28, 10]


def test_timed_map_link_waits_and_arrives_at_chosen_cell():
    data = party()
    gate = {'position': [0, 10], 'destination': 'rosee', 'entry': [3, 20], 'name': 'Sentier', 'travel_minutes': 2}
    fields.transition(data, gate, 'p', 1)
    assert data['battle'] is None
    assert data['transit']['ready_at'] == 121
    tutorial.advance(data, 120, lambda: .99)
    assert data['battle'] is None
    tutorial.advance(data, 121, lambda: .99)
    assert data['field_map'] == 'rosee'
    assert data['battle']['players']['p']['position'] == [3, 20]
    assert data['transit'] is None


def test_custom_npc_quest_requires_proximity_and_rewards_once(monkeypatch):
    from jeuxRPG.multiplayer import content
    configuration = deepcopy(content.DEFAULTS)
    configuration['quests'].append({'id':'guide_hunt','name':'Chasse du guide','npc':'guide','kind':'kill','target':'orc','zone':'lisiere','count':1,'reward_xp':75,'description':'Vaincre un orc.'})
    monkeypatch.setattr(content, 'DATA', configuration)
    fields.MAPS['rosee']['sites'].append({'position':[3,20], 'id':'guide', 'name':'Guide', 'dialogue':'Bonjour !'})
    data = party()
    fields.enter(data, 'rosee', [10,20], 1)
    with pytest.raises(GameError, match='Approchez'):
        fields.execute(data, 'p', 'talk', {'npc':'guide'}, 1, GameError, lambda: .99)
    assert not data.get('custom_quests')
    data['battle']['players']['p']['position'] = [3,20]
    messages, _ = fields.execute(data, 'p', 'talk', {'npc':'guide'}, 2, GameError, lambda: .99)
    assert any('Quête acceptée' in message for message in messages)
    content.quest_event(data, 'kill', 'orc', 'lisiere')
    xp = data['characters']['p']['exp']
    fields.execute(data, 'p', 'talk', {'npc':'guide'}, 3, GameError, lambda: .99)
    fields.execute(data, 'p', 'talk', {'npc':'guide'}, 4, GameError, lambda: .99)
    assert data['characters']['p']['exp'] == xp + 75


def test_client_receives_configured_repopulation_delay(monkeypatch):
    from jeuxRPG.multiplayer import content
    monkeypatch.setitem(content.WORLD, "repop_seconds", 240)
    party = tutorial.new_party([{"id": "p0", "name": "Test", "class_name": "Knight"}])
    assert tutorial.view(party, "p0", 0)["repop_seconds"] == 240
