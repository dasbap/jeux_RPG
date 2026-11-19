from copy import deepcopy

import pytest
import test_coaches
from test_coaches import at_stop

from jeuxRPG.multiplayer import tactics
from jeuxRPG.multiplayer.map_building import zone_of
from jeuxRPG.multiplayer.map_playability import issues
from jeuxRPG.multiplayer.zone_navigation import passages, zone_passages
from scripts.refine_lisiere import author

coach_network = test_coaches.network


@pytest.fixture
def network(coach_network, monkeypatch):
    monkeypatch.setattr(
        tactics,
        "PRESETS",
        {
            **tactics.PRESETS,
            **{data["id"]: data for data in coach_network.maps.values()},
        },
    )
    return coach_network


def test_lisiere_has_returns_and_cave_entrance_never_bypasses_labyrinth(network):
    maps = network.maps
    assert not issues(maps)
    required = {
        "rosee_remparts",
        "hunt",
        "cave_1",
        "rosee_col",
    }
    assert required <= {g["destination"] for g in maps["lisiere"]["exits"]}
    for gate in maps["lisiere"]["exits"]:
        if gate["destination"] not in required:
            continue
        assert any(
            back["destination"] == "lisiere"
            for back in maps[gate["destination"]]["exits"]
        )
    boss_exit = next(
        r
        for r in maps["clearing"]["travel_routes"]
        if r["id"] == "link_b2f15f563af441e1"
    )
    assert boss_exit["from"] == "cave_2" and not boss_exit["bidirectional"]
    before = deepcopy(maps)
    author(network)
    assert network.maps == before


def test_red_passages_are_physical_crossings_not_interior_connections(network):
    maps = network.maps
    expected = {
        gate["destination"]
        for gate in maps["lisiere"]["exits"]
        if zone_of(maps, gate["destination"]) != zone_of(maps, "lisiere")
    }
    assert {p["destination"] for p in passages(maps, "lisiere")} == expected
    assert {
        "rosee_remparts",
        "cave_1",
        "rosee_col",
    } <= expected
    assert any(
        p["source"] == "clearing"
        and p["destination"] == "cave_1"
        and p["zone"] == "grotte_oublies"
        for p in zone_passages(maps, "foret_eveilles")
    )
    assert all(p["destination"] != "cave_7" for p in passages(maps, "cave_1"))
    before = deepcopy(maps)
    for key in maps:
        for crossing in passages(maps, key):
            assert any(
                g["position"] == crossing["position"]
                and g["destination"] == crossing["destination"]
                for g in maps[key]["exits"]
            )
    assert maps == before


def test_local_map_marks_cross_zone_exits_without_marking_ordinary_passages(network):
    party = at_stop(network, "arret_lisiere")
    data = tactics.view(party, 100, "p")["map"]
    expected = {
        gate["destination"]
        for gate in network.maps["lisiere"]["exits"]
        if zone_of(network.maps, gate["destination"])
        != zone_of(network.maps, "lisiere")
    }
    assert {g["destination"] for g in data["exits"] if g["changes_zone"]} == expected
    assert all(g["destination_zone_name"] for g in data["exits"] if g["changes_zone"])
    assert not next(g for g in data["exits"] if g["destination"] == "hunt")[
        "changes_zone"
    ]
    assert all("changes_zone" not in g for g in network.maps["lisiere"]["exits"])


def test_atlas_routes_match_instant_physical_passages_without_duplicate_or_walk_timer(
    network,
):
    from jeuxRPG.multiplayer import world

    routes = world._visible_routes(set(world.PLACES), "travel", False, False)
    lisiere = [
        r
        for r in routes
        if {r["from_point"], r["to_point"]} == {"lisiere", "rosee_remparts"}
    ]
    assert len(lisiere) == 1
    assert lisiere[0]["kind"] == "passage" and lisiere[0]["duration_real_seconds"] == 0
    assert lisiere[0]["from_map_name"] == network.maps["rosee_remparts"]["name"]
