import hashlib
import json


def split(state):
    result = {key: value for key, value in state.items() if key != "session"}
    session = state.get("session")
    result["session"] = None if session is None else {}
    if session is not None:
        for key, value in session.items():
            if key != "tutorial":
                result[f"session/{key}"] = value
        if "tutorial" in session:
            allowed = {"repop_seconds", "hunt_objective", "quest_journal", "hunt_goal", "hunt_name", "hunt_description", "field_map", "field_interactions", "traveller", "achievements", "battle", "control_credit", "encounter_number", "journey", "kills", "location", "mob", "mobs", "moving", "objective", "players", "position", "quest", "step", "transit", "travel_remaining_real_seconds", "world", "world_context", "combat_size"}
            result["session/tutorial"] = {}
            for key in allowed & session["tutorial"].keys():
                result[f"session/tutorial/{key}"] = session["tutorial"][key]
    return result


def encode(state, acknowledged=""):
    try:
        previous = json.loads(acknowledged) if acknowledged and len(acknowledged) <= 16000 else {}
    except (ValueError, RecursionError):
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    bundles = split(state)
    hashes = {key: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()[:24] for key, value in bundles.items()}
    return {"bundle_protocol": 1, "hashes": hashes, "bundles": {key: value for key, value in bundles.items() if previous.get(key) != hashes[key]}, "removed": [key for key in previous if key not in hashes]}
