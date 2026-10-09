import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from jeuxRPG.multiplayer.service import GameError, GameService
from jeuxRPG.multiplayer.tutorial import pack, unpack
from jeuxRPG._class.character import Character
from jeuxRPG._class.sub_character.invocations.invocation import Invocation


class Clock:
    def __init__(self):
        self.value = 0

    def now(self):
        return self.value


@pytest.fixture
def game(tmp_path):
    service = GameService(tmp_path / "tutorial.sqlite3", Clock(), random_source=lambda: 0.5)
    yield service
    service.close()


def command(game, token, action, **params):
    state = game.state(token)["session"]
    if state and "tutorial" in state:
        adventure = state["tutorial"]
        destination = "mira" if action == "talk" else "forge" if action == "craft" else "hunt" if action == "explore" and adventure["step"] == "hunt" else "training" if action == "explore" and adventure["step"] in ("craft", "travel") else None
        if destination and adventure.get("position") != destination:
            command(game, token, "move", destination=destination)
        if action == "strike":
            params.setdefault("target", adventure["mobs"][0]["combat_id"] if adventure.get("mobs") else "mob")
    if action in ("strike", "skill") and state and state.get("tutorial", {}).get("battle"):
        combat_fixture(game, token)
    game.clock.value += 3.6
    state = game.state(token)["session"]
    if action not in ("tutorial", "create", "join"):
        params.update(session_id=state["id"], revision=state["revision"])
    previous = game.random
    if action in ("travel", "move"):
        game.random = lambda: 1.0
    try:
        result = game.command(token, uuid.uuid4().hex, action, **params)["session"]
        if action == "skill" and any(p.get("casting") is not None for p in result["tutorial"]["players"]):
            party = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (result["id"],)).fetchone()[0])
            cast = next(unit["casting"] for unit in party["battle"]["players"].values() if unit.get("casting"))
            game.clock.value = cast["ends_at"]
            game.tick()
            result = game.state(token)["session"]
        if action in ("travel", "move"):
            for _ in range(100):
                transit = result["tutorial"].get("transit")
                if not transit:
                    break
                game.clock.value = max(game.clock.value, transit["ready_at"])
                game.tick()
                result = game.state(token)["session"]
            else:
                pytest.fail("Trajet bloqué")
        return result
    finally:
        game.random = previous


def combat_fixture(game, token, injury=False):
    state = game.state(token)["session"]
    party = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()[0])
    for key, unit in party["battle"]["players"].items():
        unit["position"] = [9, 5]
        if injury:
            party["characters"][key]["stats"]["hp"]["current"] -= 5
    for mob in party["mobs"]:
        mob["position"] = [9, 4]
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    return party


def win(game, token):
    for _ in range(100):
        state = game.state(token)["session"]
        if not state["tutorial"]["battle"]["hostiles_alive"]:
            break
        combat_fixture(game, token)
        command(game, token, "strike")
    else:
        pytest.fail("Combat bloqué")
    for corpse in state["tutorial"]["battle"]["corpses"]:
        command(game, token, "harvest", target=corpse["id"])
    from jeuxRPG.multiplayer import tactics
    current = game.state(token)["session"]
    party = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (current["id"],)).fetchone()[0])
    party["battle"]["players"][current["me"]]["position"] = tactics.exit_cell(party)
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), current["id"]))
    return command(game, token, "leave_battle")


def reach_forge(game, token):
    command(game, token, "tutorial")
    command(game, token, "explore")
    win(game, token)
    command(game, token, "travel", destination="rosee")
    command(game, token, "talk", npc="mira")
    for _ in range(3):
        command(game, token, "explore")
        win(game, token)
    command(game, token, "talk", npc="mira")
    return command(game, token, "move", destination="forge")


@pytest.mark.parametrize("class_name", GameService.classes)
def test_complete_tutorial_and_acquired_skills(game, class_name):
    player = game.register("Voyageur", class_name)
    state = reach_forge(game, player["token"])
    me = state["tutorial"]["players"][0]
    assert me["level"] == 2
    assert me["inventory"] == {"peau": 4, "croc": 4}
    expected = Character.create(class_name, "expected", "Expected")
    expected.gain_exp(100)
    assert {s["name"] for s in me["skills"]} == set(expected.skills)
    before = me["max_hp"]
    command(game, player["token"], "craft", recipe="veste")
    result = command(game, player["token"], "travel", destination="brume")
    assert result["state"] == "finished"
    assert result["tutorial"]["step"] == "complete"
    assert result["tutorial"]["players"][0]["max_hp"] == before + 10
    assert result["tutorial"]["players"][0]["inventory"] == {"peau": 2, "croc": 1}


@pytest.mark.parametrize("class_name", GameService.classes)
def test_level_one_skill_uses_real_engine_and_survives_restart(game, class_name, tmp_path):
    player = game.register("Voyageur", class_name)
    state = command(game, player["token"], "tutorial")
    command(game, player["token"], "explore")
    skill = state["tutorial"]["players"][0]["skills"][0]
    if class_name == "Priest":
        combat_fixture(game, player["token"], injury=True)
    target = player["player"]["id"] if class_name in ("Priest", "Necromancien") else "mob"
    result = command(game, player["token"], "skill", skill_name=skill["name"], target=target)
    if result["tutorial"]["mob"]:
        energy = state["tutorial"]["players"][0]["energies"][0]
        expected = energy["max"] - skill["cost"]
        assert result["tutorial"]["players"][0]["energies"][0]["current"] == expected
    else:
        assert result["tutorial"]["step"] == "road"
        assert result["tutorial"]["players"][0]["level"] == 1
    if class_name == "Necromancien":
        assert len(result["tutorial"]["players"][0]["invocations"]) == 1
    other = GameService(tmp_path / "tutorial.sqlite3", game.clock)
    try:
        assert other.state(player["token"])["session"]["tutorial"] == result["tutorial"]
    finally:
        other.close()


def test_party_shares_quest_but_each_member_crafts_once(game):
    first = game.register("Chevalier", "Knight")
    second = game.register("Soigneur", "Priest")
    created = game.command(first["token"], "create000", "create")
    command(game, second["token"], "join", invite=created["invite"])
    reach_forge(game, first["token"])
    state = command(game, first["token"], "craft", recipe="veste")
    assert state["tutorial"]["step"] == "craft"
    with pytest.raises(GameError, match="déjà équipée"):
        command(game, first["token"], "craft", recipe="veste")
    state = command(game, second["token"], "craft", recipe="veste")
    assert state["tutorial"]["step"] == "travel"
    state = command(game, second["token"], "travel", destination="brume")
    assert len(state["tutorial"]["players"]) == 2
    assert all(p["level"] == 2 and p["equipment"] for p in state["tutorial"]["players"])
    assert game.state(first["token"], state["id"])["tutorial"]["step"] == "complete"


def test_rejects_locked_skill_external_target_and_skipped_steps(game):
    player = game.register("Mage", "Mage")
    outsider = game.register("Autre", "Mage")
    command(game, player["token"], "tutorial")
    for action, params in [("travel", {"destination": "brume"}), ("craft", {"recipe": "veste"}), ("talk", {"npc": "mira"})]:
        with pytest.raises(GameError):
            command(game, player["token"], action, **params)
    command(game, player["token"], "explore")
    for name, target in [("Thunder", "mob"), ("Heal", player["player"]["id"]), ("Fire Ball", outsider["player"]["id"])]:
        before = game.state(player["token"])["session"]
        with pytest.raises(GameError):
            command(game, player["token"], "skill", skill_name=name, target=target)
        after = game.state(player["token"])["session"]
        assert before["revision"] == after["revision"]
        assert before["tutorial"]["players"][0]["energies"] == after["tutorial"]["players"][0]["energies"]


def test_craft_retries_and_concurrent_commands_do_not_duplicate_items(game):
    player = game.register("Mage", "Mage")
    state = reach_forge(game, player["token"])
    params = {"session_id": state["id"], "revision": state["revision"], "recipe": "veste"}
    def craft(request_id):
        try:
            return game.command(player["token"], request_id, "craft", **params)
        except GameError as exc:
            return exc.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(craft, ["craft0001", "craft0002"]))
    assert sum(isinstance(r, dict) for r in results) == 1
    request_id = "craft0001" if isinstance(results[0], dict) else "craft0002"
    assert craft(request_id) == next(r for r in results if isinstance(r, dict))
    state = game.state(player["token"])["session"]["tutorial"]
    assert state["players"][0]["inventory"] == {"peau": 2, "croc": 1}


def test_tutorial_does_not_expire_and_npc_changes_village(game):
    player = game.register("Mage", "Mage")
    state = command(game, player["token"], "tutorial")
    assert state["tutorial"]["traveller"]["location"] == "Rosée"
    game.clock.value = 8 * 3600 + 720
    game.tick()
    assert game.state(player["token"])["session"]["tutorial"]["traveller"]["location"] == "Brume"
    game.clock.value = 100000
    game.tick()
    assert game.state(player["token"])["session"]["state"] == "running"


def test_level_five_blessing_has_effect_and_persists(game):
    player = game.register("Prêtre", "Priest")
    state = reach_forge(game, player["token"])
    party = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()[0])
    from jeuxRPG.multiplayer import progression
    character = unpack(party["characters"][player["player"]["id"]])
    character.gain_exp(sum(progression.required(level) for level in range(1, 5)))
    party["characters"][player["player"]["id"]] = pack(character)
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    command(game, player["token"], "explore")
    state = command(game, player["token"], "skill", skill_name="Blessing", target=player["player"]["id"])
    data = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()[0])
    original = Character.create("Priest", "original", "Original")
    original.gain_exp(1000)
    restored = unpack(data["characters"][player["player"]["id"]])
    assert restored.endurance.current_value == original.endurance.value + 10
    assert restored.skills["Blessing"].current_cooldown == 2
    assert restored.status["alteration"]["buff"][0].duration == 3
    assert pack(restored) == data["characters"][player["player"]["id"]]


def test_repeated_invocation_snapshots_do_not_leak_global_registry(game):
    player = game.register("Invocateur", "Necromancien")
    command(game, player["token"], "tutorial")
    command(game, player["token"], "explore")
    before = len(Invocation.all_invocation)
    command(game, player["token"], "skill", skill_name="Low Skull", target=player["player"]["id"])
    for _ in range(10):
        game.state(player["token"])
    assert len(Invocation.all_invocation) == before


def test_skill_requires_energy_and_blocks_actor_spoofing(game):
    player = game.register("Mage", "Mage")
    command(game, player["token"], "tutorial")
    state = command(game, player["token"], "explore")
    row = game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()
    data = json.loads(row[0])
    data["characters"][player["player"]["id"]]["energies"][0]["current"] = 0
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(data), state["id"]))
    with pytest.raises(GameError) as failure:
        command(game, player["token"], "skill", skill_name="Fire Ball", target="mob")
    assert failure.value.code == "skill_unavailable"
    with pytest.raises(GameError) as failure:
        game.command(player["token"], "spoof0001", "strike", session_id=state["id"], revision=state["revision"], actor="someone-else")
    assert failure.value.code == "invalid_command"


def test_completed_adventure_is_restored_without_client_session_id(game):
    player = game.register("Mage", "Mage")
    reach_forge(game, player["token"])
    command(game, player["token"], "craft", recipe="veste")
    result = command(game, player["token"], "travel", destination="brume")
    restored = game.state(player["token"])
    assert restored["session"]["id"] == result["id"]
    assert restored["session"]["tutorial"]["players"][0]["level"] == 2


def test_no_combat_targets_when_spawning_or_recovering(game):
    player = game.register("Chevalier", "Knight")
    state = command(game, player["token"], "tutorial")
    me = state["tutorial"]["players"][0]
    assert not me["can_attack"]
    assert all(not skill["targets"] for skill in me["skills"])
    state = command(game, player["token"], "explore")
    assert state["tutorial"]["players"][0]["skills"][0]["targets"] == []
    state = command(game, player["token"], "skill", skill_name="Sword Slash", target="mob")
    me = state["tutorial"]["players"][0]
    assert not me["can_attack"]
    assert all(not skill["targets"] for skill in me["skills"])
    with pytest.raises(GameError) as failure:
        game.command(player["token"], "double000", "skill", session_id=state["id"], revision=state["revision"], skill_name="Sword Slash", target="mob")
    assert failure.value.code == "cooldown"


def test_strike_requires_explicit_enemy_target(game):
    player = game.register("Chevalier", "Knight")
    command(game, player["token"], "tutorial")
    state = command(game, player["token"], "explore")
    for target in (player["player"]["id"], "unknown", None, []):
        with pytest.raises(GameError) as failure:
            command(game, player["token"], "strike", target=target)
        assert failure.value.code == "invalid_target"
        assert game.state(player["token"])["session"]["revision"] == state["revision"]
    with pytest.raises(GameError) as failure:
        game.command(player["token"], "missing00", "strike", session_id=state["id"], revision=state["revision"])
    assert failure.value.code == "invalid_command"


def test_heal_targets_only_injured_group_members(game):
    priest = game.register("Soigneur", "Priest")
    knight = game.register("Chevalier", "Knight")
    created = game.command(priest["token"], "create000", "create")
    command(game, knight["token"], "join", invite=created["invite"])
    command(game, priest["token"], "tutorial")
    state = command(game, priest["token"], "explore")
    healer = next(p for p in state["tutorial"]["players"] if p["id"] == priest["player"]["id"])
    assert healer["skills"][0]["targets"] == []
    with pytest.raises(GameError) as failure:
        command(game, priest["token"], "skill", skill_name="Heal", target=knight["player"]["id"])
    assert failure.value.code == "invalid_target"
    party = combat_fixture(game, priest["token"])
    party["characters"][knight["player"]["id"]]["stats"]["hp"]["current"] -= 5
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    state = game.state(priest["token"])["session"]
    healer = next(p for p in state["tutorial"]["players"] if p["id"] == priest["player"]["id"])
    injured_id = next(p["id"] for p in state["tutorial"]["players"] if p["hp"] < p["max_hp"])
    assert healer["skills"][0]["targets"] == [injured_id]
    state = command(game, priest["token"], "skill", skill_name="Heal", target=injured_id)
    healed = next(p for p in state["tutorial"]["players"] if p["id"] == injured_id)
    assert healed["hp"] == healed["max_hp"]


def test_duel_rechecks_selected_opponent(game):
    first = game.register("Chevalier", "Knight")
    second = game.register("Mage", "Mage")
    created = game.command(first["token"], "create000", "create")
    command(game, second["token"], "join", invite=created["invite"])
    state = command(game, first["token"], "start")
    with pytest.raises(GameError) as failure:
        command(game, first["token"], "attack", target=first["player"]["id"])
    assert failure.value.code == "invalid_target"
    assert game.state(first["token"])["session"]["revision"] == state["revision"]
    state = command(game, first["token"], "attack", target=second["player"]["id"])
    assert next(p for p in state["players"] if p["id"] == second["player"]["id"])["hp"] < second["player"]["max_hp"]


@pytest.mark.parametrize("class_name", ["Knight", "Mage", "Archer", "Necromancien"])
def test_no_ally_target_without_learned_support_skill(game, class_name):
    player = game.register("Aventurier", class_name)
    ally = game.register("Allié", "Knight")
    created = game.command(player["token"], "create000", "create")
    command(game, ally["token"], "join", invite=created["invite"])
    command(game, player["token"], "tutorial")
    state = command(game, player["token"], "explore")
    me = next(p for p in state["tutorial"]["players"] if p["id"] == player["player"]["id"])
    assert all(ally["player"]["id"] not in skill["targets"] for skill in me["skills"])
    with pytest.raises(GameError) as failure:
        command(game, player["token"], "skill", skill_name=me["skills"][0]["name"], target=ally["player"]["id"])
    assert failure.value.code == "invalid_target"


def test_map_and_bestiary_discoveries_are_progressive(game):
    player = game.register("Voyageur", "Mage")
    state = command(game, player["token"], "tutorial")
    world = state["tutorial"]["world"]
    assert [p["id"] for p in world["places"]] == ["clearing"]
    assert world["routes"] == []
    assert world["bestiary"] == []
    state = command(game, player["token"], "explore")
    assert state["tutorial"]["world"]["bestiary"][0]["name"] == "Gobelin des bois"
    assert all(point["action"] is None for place in state["tutorial"]["world"]["places"] for point in place["points"])
    state = win(game, player["token"])
    rosee = next(place for place in state["tutorial"]["world"]["places"] if place["id"] == "rosee")
    assert not rosee["visited"]
    assert rosee["points"] == []
    assert "forge" not in rosee["description"]
    assert state["tutorial"]["world"]["routes"][0]["destination"] == "rosee"
    state = command(game, player["token"], "travel", destination="rosee")
    rosee = next(place for place in state["tutorial"]["world"]["places"] if place["id"] == "rosee")
    assert rosee["visited"]
    assert next(point for point in rosee["points"] if point["id"] == "mira")["action"] is None
    state = command(game, player["token"], "move", destination="mira")
    rosee = next(place for place in state["tutorial"]["world"]["places"] if place["id"] == "rosee")
    assert next(point for point in rosee["points"] if point["id"] == "mira")["action"] == "dialogue"
    assert next(point for point in rosee["points"] if point["id"] == "forge")["action"] is None


def test_visited_villages_and_codex_survive_restart(game, tmp_path):
    player = game.register("Voyageur", "Mage")
    state = reach_forge(game, player["token"])
    before = state["tutorial"]["world"]
    assert next(p for p in before["places"] if p["id"] == "brume")["points"] == []
    command(game, player["token"], "craft", recipe="veste")
    state = command(game, player["token"], "travel", destination="brume")
    reopened = GameService(tmp_path / "tutorial.sqlite3", game.clock)
    try:
        world = reopened.state(player["token"])["session"]["tutorial"]["world"]
        assert all(place["visited"] for place in world["places"])
        assert next(p for p in world["places"] if p["id"] == "rosee")["points"]
        assert world["bestiary"][0]["loot"] == [{"item": item, "quantity": 1, "chance": 1, "attempts": 1, "max_quantity": 1} for item in ("peau", "croc")]
        assert world == state["tutorial"]["world"]
    finally:
        reopened.close()


def test_bestiary_matches_combat_rules_and_old_saves_are_supported(game):
    from jeuxRPG.multiplayer.world import GOBLIN
    from jeuxRPG._class.res.character.table_stat_subclass import goblin_table
    player = game.register("Voyageur", "Knight")
    command(game, player["token"], "tutorial")
    state = command(game, player["token"], "explore")
    creature = state["tutorial"]["world"]["bestiary"][0]
    assert creature["hp"]["first_encounter"] == combat_fixture(game, player["token"])["mobs"][0]["stats"]["hp"]["max"]
    assert creature["xp"]["hunt"] == GOBLIN["xp_hunt"]
    assert creature["weaknesses"] == [v.name for v in goblin_table["advantage"]["weakness"]]
    assert creature["resistances"] == [v.name for v in goblin_table["advantage"]["resilience"]]
    row = game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()
    data = json.loads(row[0])
    data.pop("visited")
    data.pop("seen_mobs")
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(data), state["id"]))
    assert game.state(player["token"])["session"]["tutorial"]["world"] == state["tutorial"]["world"]


def test_travelling_npc_appears_only_in_visited_current_village(game):
    player = game.register("Voyageur", "Mage")
    command(game, player["token"], "tutorial")
    command(game, player["token"], "explore")
    win(game, player["token"])
    command(game, player["token"], "travel", destination="rosee")
    game.clock.value = 600
    places = game.state(player["token"])["session"]["tutorial"]["world"]["places"]
    rosee = next(place for place in places if place["id"] == "rosee")
    assert any(point["id"] == "leon" for point in rosee["points"])
    game.clock.value = 8 * 3600 + 1
    places = game.state(player["token"])["session"]["tutorial"]["world"]["places"]
    assert not any(point["id"] == "leon" for place in places for point in place["points"])


def test_delayed_movement_is_validated_in_current_encounter_without_revision_retry(game):
    token = game.register("Marcheur", "Knight")["token"]
    game.command(token, uuid.uuid4().hex, "tutorial")
    state = command(game, token, "explore")
    stale = state["revision"]
    encounter = state["tutorial"]["encounter_number"]
    for _ in range(40):
        game.clock.value += .3
        game.tick()
    latest = game.state(token)["session"]
    assert latest["revision"] > stale
    result = game.command(token, uuid.uuid4().hex, "battle_move", session_id=state["id"], revision=stale, encounter=encounter, x=1, y=4, path=[[1, 5], [1, 4]])
    assert result["session"]["tutorial"]["battle"]["players"][result["session"]["me"]]["route"] == [[1, 5], [1, 4]]
    with pytest.raises(GameError) as failure:
        game.command(token, uuid.uuid4().hex, "battle_move", session_id=state["id"], revision=stale, encounter=encounter + 1, x=1, y=4, path=[[1, 5], [1, 4]])
    assert failure.value.code in ("stale_revision", "stale_encounter")
    with pytest.raises(GameError) as failure:
        game.command(token, uuid.uuid4().hex, "battle_move", session_id=state["id"], revision=stale, encounter=encounter, x=12, y=8, path=[[12, 8]])
    assert failure.value.code == "invalid_path"


def test_stale_tactical_command_without_encounter_revalidates_current_battle(game):
    token = game.register("Prudent", "Knight")["token"]
    command(game, token, "tutorial")
    state = command(game, token, "explore")
    party = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state['id'],)).fetchone()[0])
    party['encounter_number'] += 1
    player_id = state["me"]
    party["battle"]["players"][player_id]["route"] = [[1, 5], [1, 4]]
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state['id']))
    game.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (state['id'],))
    result = game.command(token, uuid.uuid4().hex, "stop_move", session_id=state["id"], revision=state["revision"])
    assert result["session"]["tutorial"]["battle"]["players"][player_id]["route"] == []


@pytest.mark.parametrize("draw,encounter", [(0.24, True), (0.25, False), (0.9, False)])
def test_travel_encounters_have_separate_lower_probability(draw, encounter, monkeypatch):
    from jeuxRPG.multiplayer import tutorial
    data = tutorial.new_party([{"id": "p0", "name": "Marcheur", "class_name": "Knight"}])
    tutorial.migrate(data, 0)
    data["transit"] = {"destination": "rosee", "remaining": 300, "started_at": 0, "ready_at": 150, "segment": 150, "hazard": True}
    calls = []
    monkeypatch.setattr(tutorial, "spawn", lambda *args: calls.append(args))
    tutorial.continue_journey(data, 150, lambda: draw, [])
    assert bool(calls) is encounter


def test_coop_world_action_survives_time_only_revision_but_not_changed_encounter(game):
    first = game.register("Alice", "Knight")["token"]
    second = game.register("Bob", "Mage")["token"]
    room = game.command(first, uuid.uuid4().hex, "create")
    game.command(second, uuid.uuid4().hex, "join", invite=room["invite"])
    game.command(first, uuid.uuid4().hex, "tutorial")
    snapshot = game.state(second)["session"]
    game.clock.value = 6
    game.tick()
    assert game.state(second)["session"]["revision"] > snapshot["revision"]
    params = {"session_id": snapshot["id"], "revision": snapshot["revision"], "world_context": snapshot["tutorial"]["world_context"]}
    result = game.command(second, uuid.uuid4().hex, "explore", **params)
    assert result["session"]["tutorial"]["battle"]
    with pytest.raises(GameError) as failure:
        game.command(first, uuid.uuid4().hex, "explore", **params)
    assert failure.value.code == "wrong_location"


def test_coop_move_accepts_slow_snapshot_without_teleport(game):
    first = game.register("Alice", "Knight")["token"]
    second = game.register("Bob", "Mage")["token"]
    room = game.command(first, uuid.uuid4().hex, "create")
    game.command(second, uuid.uuid4().hex, "join", invite=room["invite"])
    game.command(first, uuid.uuid4().hex, "tutorial")
    snapshot = game.state(second)["session"]
    game.clock.value = 6
    game.tick()
    result = game.command(second, uuid.uuid4().hex, "move", session_id=snapshot["id"], revision=snapshot["revision"], world_context=snapshot["tutorial"]["world_context"], destination="clearing_fight")
    assert result["session"]["tutorial"]["transit"]["destination"] == "clearing_fight"
    assert result["session"]["tutorial"]["position"] == "clearing"


def test_client_world_route_is_validated_without_server_search(game, monkeypatch):
    from jeuxRPG.multiplayer import tutorial, world
    token = game.register("Route", "Knight")["token"]
    state = game.command(token, uuid.uuid4().hex, "tutorial")["session"]
    data = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()[0])
    data["step"] = "road"
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(data), state["id"]))
    proposed = ["clearing_rosee", "rosee"]
    def forbidden(*args):
        raise AssertionError("Server must not calculate the client route")
    monkeypatch.setattr(world, "path", forbidden)
    result = game.command(token, uuid.uuid4().hex, "travel", session_id=state["id"], revision=state["revision"], destination="rosee", paths={"clearing": proposed})
    assert result["session"]["tutorial"]["transit"]["destination"] == "clearing_rosee"
    assert proposed == ["clearing_rosee", "rosee"]
    assert result["session"]["tutorial"]["journey"] == ["rosee"]


@pytest.mark.parametrize("proposed", [["rosee"], ["clearing_rosee", "rosee", "brume"], ["clearing_rosee", "clearing", "clearing_rosee", "rosee"], [True, "rosee"]])
def test_forged_world_routes_are_rejected(proposed):
    from jeuxRPG.multiplayer import world
    assert not world.validate_path("clearing", "rosee", {"clearing", "rosee"}, proposed)


def test_delayed_strike_rechecks_current_combat_and_cooldown(game):
    token = game.register('Réactif', 'Knight')['token']
    game.command(token, uuid.uuid4().hex, 'tutorial')
    state = command(game, token, 'explore')
    combat_fixture(game, token)
    state = game.state(token)['session']
    encounter = state['tutorial']['encounter_number']
    stale = state['revision']
    game.clock.value += .3
    game.tick()
    params = {'session_id': state['id'], 'revision': stale, 'encounter': encounter, 'target': state['tutorial']['mobs'][0]['combat_id']}
    game.command(token, uuid.uuid4().hex, 'strike', **params)
    with pytest.raises(GameError) as failure:
        game.command(token, uuid.uuid4().hex, 'strike', **params)
    assert failure.value.code == 'cooldown'
    params['encounter'] += 1
    with pytest.raises(GameError) as failure:
        game.command(token, uuid.uuid4().hex, 'strike', **params)
    assert failure.value.code in ('stale_encounter', 'stale_revision')


def test_stale_tutorial_intent_is_revalidated_against_current_state(game):
    player = game.register("Aventurier", "Knight")
    state = command(game, player["token"], "tutorial")
    stale_revision = state["revision"]
    game.db.execute(
        "UPDATE sessions SET revision=revision+5 WHERE id=?",
        (state["id"],),
    )
    result = game.command(
        player["token"],
        uuid.uuid4().hex,
        "rest",
        session_id=state["id"],
        revision=stale_revision,
    )
    assert result["session"]["revision"] == stale_revision + 6


def test_stale_tutorial_intent_returns_current_business_error(game):
    player = game.register("Aventurier", "Knight")
    state = command(game, player["token"], "tutorial")
    stale_revision = state["revision"]
    command(game, player["token"], "explore")
    with pytest.raises(GameError) as failure:
        game.command(
            player["token"],
            uuid.uuid4().hex,
            "explore",
            session_id=state["id"],
            revision=stale_revision,
        )
    assert failure.value.code == "wrong_location"


def test_future_tutorial_revision_is_rejected(game):
    player = game.register("Aventurier", "Knight")
    state = command(game, player["token"], "tutorial")
    with pytest.raises(GameError) as failure:
        game.command(
            player["token"],
            uuid.uuid4().hex,
            "rest",
            session_id=state["id"],
            revision=state["revision"] + 1,
        )
    assert failure.value.code == "stale_revision"
