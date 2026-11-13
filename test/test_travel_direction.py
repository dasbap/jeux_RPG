"""Travel follows Builder point IDs while world-map labels use logical zone IDs."""

import pytest
from test_narrative import story  # noqa: F401

from jeuxRPG.multiplayer import tutorial, world
from jeuxRPG.multiplayer.service import GameError


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
