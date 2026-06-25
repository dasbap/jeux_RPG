import json

from jeuxRPG._class.place.map_hierarchy import load_town_graph


def test_load_town_graph_builds_connections_and_entry_district(tmp_path):
    towns_path = tmp_path / "towns.json"
    towns_path.write_text(
        json.dumps(
            {
                "towns": [
                    {
                        "name": "Starting Town",
                        "population": 10,
                        "wealth": 5,
                        "reputation": 1,
                        "size": [30, 20],
                    },
                    {"name": "Other Town"},
                ],
                "paths": [
                    {"from": "Starting Town", "to": "Other Town", "bidirectional": True}
                ],
            }
        ),
        encoding="utf-8",
    )

    towns = load_town_graph(str(towns_path))
    assert set(towns.keys()) == {"Starting Town", "Other Town"}

    start = towns["Starting Town"]
    other = towns["Other Town"]

    assert start.size == (30, 20)
    assert start.can_travel_to("Other Town") is True
    assert other.can_travel_to("Starting Town") is True

    # Entry district is created automatically for spawning
    assert start.entry_district is not None
    assert start.entry_district.name == "Centre"
