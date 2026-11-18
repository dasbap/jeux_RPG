from copy import deepcopy
from pathlib import Path

import pytest

from jeuxRPG._class.character import CharacterMeta
from jeuxRPG.multiplayer import (
    coaches,
    content,
    fields,
    map_building,
    skill_catalog,
    tutorial,
    world,
)
from jeuxRPG.multiplayer.controller_gameplay import change
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.service import GameError
from jeuxRPG.multiplayer.world_topology import compile_world

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def network(monkeypatch):
    project = Project(ROOT / "projects/authored")
    monkeypatch.setattr(content, "DATA", project.content)
    monkeypatch.setattr(fields, "MAPS", project.maps)
    monkeypatch.setattr(world, "WORLD_MAP_DATA", project.maps)
    for name, value in zip(
        (
            "PLACES",
            "VILLAGE_STREETS",
            "ROUTES",
            "LEVELS",
            "POINT_MAPS",
            "ZONE_ENTRIES",
            "EDGES",
        ),
        compile_world(project.maps),
        strict=True,
    ):
        monkeypatch.setattr(world, name, value)
    original = CharacterMeta._classes.copy()
    monkeypatch.setattr(map_building, "MOBS", project.mobs)
    skill_catalog.install(project.content, project.mobs)
    try:
        yield project
    finally:
        CharacterMeta._classes.clear()
        CharacterMeta._classes.update(original)


def at_stop(project, key="coach_rosee"):
    party = tutorial.new_party(
        [{"id": "p", "name": "Voyageur", "class_name": "Knight"}]
    )
    party["field_mode"] = True
    stop = project.content["gameplay"]["coach_stations"][key]
    fields.enter(party, stop["map"], stop["position"], 100)
    party["mobs"] = []
    return party


def test_directed_trip_arrives_on_physical_dropoff_and_survives_serialization(network):
    import json

    party = at_stop(network)
    assert coaches.view(party, "p")["nearby"][0]["boarding"]
    coaches.depart(party, "p", "coach_rosee", "rosee_lisiere", 100, GameError)
    assert party["transit"]["mode"] == "coach" and not party["battle"]
    party = json.loads(json.dumps(party))
    tutorial.continue_journey(party, 120, lambda: 1, [])
    assert party["transit"] and not party["battle"]
    tutorial.continue_journey(party, 121, lambda: 1, [])
    assert (
        party["field_map"] == "lisiere" and party["battle"] and party["transit"] is None
    )
    stop = coaches.view(party, "p")["nearby"][0]
    assert stop["id"] == "arret_lisiere" and not stop["boarding"] and not stop["routes"]
    before = deepcopy(party)
    with pytest.raises(GameError):
        coaches.depart(party, "p", "arret_lisiere", "rosee_lisiere", 122, GameError)
    assert party == before


def test_boarding_requires_matching_route_proximity_and_no_combat(network):
    party = at_stop(network)
    before = deepcopy(party)
    with pytest.raises(GameError):
        coaches.depart(party, "p", "coach_rosee", "brume_rosee", 100, GameError)
    assert party == before
    party["battle"]["players"]["p"]["position"] = [1, 1]
    with pytest.raises(GameError) as refused:
        coaches.depart(party, "p", "coach_rosee", "rosee_brume", 100, GameError)
    assert refused.value.code == "wrong_location"
    party = at_stop(network)
    party["mobs"] = [{"alerted": True, "faction": "hostile"}]
    with pytest.raises(GameError):
        coaches.depart(party, "p", "coach_rosee", "rosee_brume", 100, GameError)


def test_every_authored_exit_has_a_physical_destination(network):
    assert all(
        gate["destination"] in network.maps
        and not gate.get("world_exit")
        and not gate.get("travel_minutes")
        for data in network.maps.values()
        for gate in data["exits"]
    )
    party = at_stop(network, "coach_foret")
    gate = next(
        g for g in network.maps["clearing"]["exits"] if g["destination"] == "cave_1"
    )
    fields.transition(
        party, {**gate, "world_exit": True, "travel_minutes": 9}, "p", 100
    )
    assert party["battle"] and party["field_map"] == "cave_1" and not party["transit"]


def test_legacy_global_save_returns_to_playable_sector(network):
    party = at_stop(network)
    party.update(battle=None, mobs=[], position="rosee", transit=None)
    party.pop("field_map")
    coaches.restore_field(party, 100)
    assert party["battle"] and party["field_map"] == "rosee"


def test_builder_keeps_map_site_and_stop_in_sync_and_rolls_back(network):
    stop = deepcopy(network.content["gameplay"]["coach_stations"]["arret_lisiere"])
    stop["name"] = "Nouveau nom"
    change(network, "coach_stations", "arret_lisiere", stop)
    assert (
        next(s for s in network.maps["lisiere"]["sites"] if s["id"] == "arret_lisiere")[
            "name"
        ]
        == "Nouveau nom"
    )
    before = network.state()
    stop["position"] = [9999, 9999]
    with pytest.raises(ValueError):
        change(network, "coach_stations", "arret_lisiere", stop)
    assert network.state() == before
    route = deepcopy(network.content["gameplay"]["coach_routes"]["rosee_lisiere"])
    route["from"] = "arret_lisiere"
    with pytest.raises(ValueError):
        change(network, "coach_routes", "invalid_dropoff_departure", route, new=True)
