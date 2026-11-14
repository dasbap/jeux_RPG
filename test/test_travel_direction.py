"""Travel follows Builder point IDs while world-map labels use logical zone IDs."""

import json

import pytest
from test_narrative import story  # noqa: F401

from jeuxRPG.multiplayer import tutorial, world
from jeuxRPG.multiplayer.service import GameError
from jeuxRPG.multiplayer.state_bundles import encode


@pytest.mark.parametrize(
    ("origin", "goal"), [("rosee", "lisiere"), ("lisiere", "rosee")]
)
@pytest.mark.usefixtures("story")
def test_builder_trip_reaches_requested_endpoint_with_preserved_display_mapping(
    origin, goal
):
    party = tutorial.new_party([{"id": "p", "name": "Trajet", "class_name": "Knight"}])
    party.update(
        position=origin,
        step="village",
        battle=None,
        mobs=[],
        mob=None,
        journey=[],
        transit=None,
        field_mode=False,
    )
    tutorial.execute(party, "p", "move", {"destination": goal}, 0, GameError, lambda: 1)
    first = tutorial.view(party, "p", 0)
    route = next(
        route for route in first["world"]["routes"] if route["id"] == "rosee_lisiere"
    )
    assert route["from"] == "zone_rosee" and route["to"] == "zone_lisiere"
    assert route["from_point"] == "rosee" and route["to_point"] == "lisiere"
    assert first["transit"]["source"] == origin
    assert first["journey"][-1] == goal
    for _ in range(20):
        if not party["transit"]:
            break
        tutorial.advance(party, party["transit"]["ready_at"], lambda: 1)
    assert party["position"] == goal
    assert not party["journey"] and party["transit"] is None
    definition = next(route for route in world.ROUTES if route["id"] == "rosee_lisiere")
    assert definition["from"] == "rosee" and definition["to"] == "lisiere"


@pytest.mark.parametrize("origin,goal", [("rosee", "lisiere"), ("lisiere", "rosee")])
@pytest.mark.usefixtures("story")
def test_websocket_deltas_preserve_progress_and_labels_during_a_real_trip(origin, goal):
    party = tutorial.new_party([{"id": "p", "name": "Trajet", "class_name": "Knight"}])
    party.update(
        position=origin,
        step="village",
        battle=None,
        mobs=[],
        mob=None,
        journey=[],
        transit=None,
        field_mode=False,
    )
    tutorial.execute(party, "p", "move", {"destination": goal}, 0, GameError, lambda: 1)
    initial_view = tutorial.view(party, "p", 0)
    initial = encode({"session": {"id": "trip", "tutorial": initial_view}})
    for name in (
        "travel_progress",
        "travel_source_name",
        "travel_destination_name",
        "travel_goal_name",
    ):
        assert initial["bundles"][f"session/tutorial/{name}"] == initial_view[name]
    midpoint = party["transit"]["ready_at"] / 2
    tutorial.advance(party, midpoint, lambda: 1)
    moving_view = tutorial.view(party, "p", midpoint)
    delta = encode(
        {"session": {"id": "trip", "tutorial": moving_view}},
        json.dumps(initial["hashes"]),
    )
    cache = {**initial["bundles"], **delta["bundles"]}
    assert cache["session/tutorial/travel_progress"] > initial_view["travel_progress"]
    assert (
        cache["session/tutorial/travel_remaining_real_seconds"]
        < initial_view["travel_remaining_real_seconds"]
    )
    assert (
        cache["session/tutorial/travel_goal_name"] == initial_view["travel_goal_name"]
    )
    assert moving_view["moving"]
