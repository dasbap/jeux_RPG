from copy import deepcopy
import uuid

import pytest

from jeuxRPG.multiplayer import fields, tutorial, tactics, world
from jeuxRPG.multiplayer.service import GameError, GameService


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
    assert data["battle"] is None
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
