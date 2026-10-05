from jeuxRPG.multiplayer.state_bundles import encode
import json


def test_initial_delta_and_session_removal():
    state = {"player": {"id": "one"}, "session": {"id": "s", "tutorial": {"world": {"places": []}, "kills": 0, "characters": {"private": True}}}}
    first = encode(state)
    assert "session/tutorial/characters" not in first["bundles"]
    unchanged = encode(state, json.dumps(first["hashes"]))
    assert unchanged["bundles"] == {}
    state["session"]["tutorial"]["kills"] = 1
    delta = encode(state, json.dumps(first["hashes"]))
    assert delta["bundles"] == {"session/tutorial/kills": 1}
    state["session"] = None
    gone = encode(state, json.dumps(delta["hashes"]))
    assert gone["bundles"]["session"] is None
    assert "session/tutorial/world" in gone["removed"]


def test_bad_manifest_and_other_player_never_disclose_cached_data():
    state = {"player": {"id": "two"}, "session": None}
    for manifest in ("[]", "broken", "x" * 16001):
        assert encode(state, manifest)["bundles"] == state
    previous = encode({"player": {"id": "one"}, "session": None})
    assert encode(state, json.dumps(previous["hashes"]))["bundles"]["player"] == {"id": "two"}


def test_fixed_map_and_interactions_survive_bundle_transport():
    data = {'session': {'tutorial': {'field_map': 'rosee', 'field_interactions': [{'id':'mira'}], 'traveller': {'location':'rosee'}}}}
    result = encode(data)['bundles']
    assert result['session/tutorial/field_map'] == 'rosee'
    assert result['session/tutorial/field_interactions'] == [{'id':'mira'}]
    assert result['session/tutorial/traveller']['location'] == 'rosee'


def test_hunt_rules_survive_initial_and_delta_bundle_transport():
    objective = {"id": "mira_hunt_1", "npc": "mira", "target": "goblin", "zone": "lisiere", "map": "hunt", "count": 10}
    state = {"session": {"tutorial": {"hunt_objective": objective, "repop_seconds": 240, "fields": {"secret": True}}}}
    initial = encode(state)
    assert initial["bundles"]["session/tutorial/hunt_objective"] == objective
    assert initial["bundles"]["session/tutorial/repop_seconds"] == 240
    assert "session/tutorial/fields" not in initial["bundles"]
    state["session"]["tutorial"]["repop_seconds"] = 180
    delta = encode(state, json.dumps(initial["hashes"]))
    assert delta["bundles"] == {"session/tutorial/repop_seconds": 180}
