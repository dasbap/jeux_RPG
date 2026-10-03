import json
import uuid

import pytest

from jeuxRPG.multiplayer import tutorial, world
from test.test_tutorial import combat_fixture, win
from jeuxRPG.multiplayer.service import GameError, GameService


class Clock:
    value = 0

    def now(self):
        return self.value


def act(game, player, action, **params):
    state = game.state(player["token"])["session"]
    if state and action != "tutorial":
        params.update(session_id=state["id"], revision=state["revision"])
    return game.command(player["token"], uuid.uuid4().hex, action, **params)["session"]


@pytest.fixture
def game(tmp_path):
    service = GameService(tmp_path / "walking.sqlite3", Clock(), random_source=lambda: .999)
    yield service
    service.close()


def save_party(game, session_id, data):
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(data), session_id))


def load_party(game, session_id):
    return json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session_id,)).fetchone()[0])


def prepare(game, step="travel", position="rosee"):
    player = game.register("Marcheur", "Knight")
    session = act(game, player, "tutorial")
    party = load_party(game, session["id"])
    party.update(step=step, position=position, quest="completed" if step == "travel" else "active", visited=["clearing", "rosee", "lisiere"])
    party["characters"][player["player"]["id"]]["level"] = 4
    save_party(game, session["id"], party)
    return player, session


def finish_trip(game, player):
    for _ in range(100):
        state = game.state(player["token"])["session"]
        party = state["tutorial"]
        if party["mob"]:
            win(game, player["token"])
        elif party["transit"]:
            game.clock.value = party["transit"]["ready_at"]
            game.tick()
        else:
            return state
    pytest.fail("Déplacement bloqué")


def test_one_kilometre_takes_ten_game_minutes_and_random_encounter_checks(game):
    player, _ = prepare(game)
    draws = []
    game.random = lambda: draws.append(game.clock.value) or .999
    state = act(game, player, "move", destination="brume")
    assert state["tutorial"]["position"] == "rosee_brume"
    assert state["tutorial"]["moving"]
    with pytest.raises(GameError) as error:
        act(game, player, "move", destination="forge")
    assert error.value.code == "already_moving"
    game.clock.value = 599
    game.tick()
    assert game.state(player["token"])["session"]["tutorial"]["position"] != "brume"
    state = finish_trip(game, player)
    assert len(draws) >= 4
    assert state["state"] == "finished"
    assert state["tutorial"]["position"] == "brume"
    assert world.walking_seconds("rosee", "rosee_brume") + world.walking_seconds("rosee_brume", "brume") == 600


def test_trip_finishes_at_distance_deadline_when_server_ticks_regularly(game):
    player, _ = prepare(game)
    act(game, player, "move", destination="brume")
    for instant in (150, 300, 450, 599):
        game.clock.value = instant
        game.tick()
    assert game.state(player["token"])["session"]["tutorial"]["moving"]
    game.clock.value = 600
    game.tick()
    assert game.state(player["token"])["session"]["state"] == "finished"


def test_three_goblins_share_one_combat_and_attack_without_player_action(game):
    player = game.register("Marcheur", "Knight")
    act(game, player, "tutorial")
    draws = iter([.5, .2, .05, .04, 0, .25, .5])
    game.random = lambda: next(draws)
    state = act(game, player, "explore")
    assert len(state["tutorial"]["mobs"]) == 3
    assert state["tutorial"]["combat_size"] == 3
    for destination in ("rosee", "clearing_fight", "clearing"):
        with pytest.raises(GameError) as error:
            act(game, player, "move", destination=destination)
        assert error.value.code == "in_combat"
    party = combat_fixture(game, player["token"])
    party["battle"]["players"][player["player"]["id"]]["hidden"] = False
    for mob in party["mobs"]:
        mob["allies"] = []
    save_party(game, state["id"], party)
    game.random = lambda: .5
    game.clock.value = 20
    game.tick()
    game.clock.value = 22
    game.tick()
    state = game.state(player["token"])["session"]
    attacks = [e for e in state["events"] if "utilise Entaille" in e["message"]]
    assert len(attacks) == 3
    assert state["tutorial"]["encounter_number"] == 1
    assert state["tutorial"]["position"] == "clearing"


def test_combat_pauses_remaining_walk_and_blocks_local_interactions(game):
    player, _ = prepare(game)
    act(game, player, "move", destination="brume")
    game.random = lambda: .5
    game.clock.value = 180
    game.tick()
    state = game.state(player["token"])["session"]
    assert state["tutorial"]["mob"]
    assert state["tutorial"]["transit"]["paused_at"] == 180
    remaining = state["tutorial"]["transit"]["remaining"]
    for instant in (181, 182):
        game.clock.value = instant
        game.tick()
        assert game.state(player["token"])["session"]["tutorial"]["transit"]["remaining"] == remaining
    for action, params in (("move", {"destination": "forge"}), ("travel", {"destination": "brume"})):
        with pytest.raises(GameError) as error:
            act(game, player, action, **params)
        assert error.value.code == "in_combat"
    for point in state["tutorial"]["world"]["places"]:
        assert all(not p["can_interact"] for p in point["points"])
    game.random = lambda: .999
    win(game, player["token"])
    transit = game.state(player["token"])["session"]["tutorial"]["transit"]
    assert transit["ready_at"] > game.clock.value
    assert transit["remaining"] == remaining


def test_locked_forge_explains_required_quest_on_map_and_in_api(game):
    player, session = prepare(game, "hunt", "forge")
    state = game.state(player["token"])["session"]
    forge = next(p for place in state["tutorial"]["world"]["places"] for p in place["points"] if p["id"] == "forge")
    assert "rendez-la" in forge["locked_reason"]
    assert forge["can_interact"]
    with pytest.raises(GameError) as error:
        act(game, player, "craft", recipe="veste")
    assert error.value.code == "forge_locked"
    party = load_party(game, session["id"])
    party.update(step="craft", quest="completed")
    save_party(game, session["id"], party)
    state = game.state(player["token"])["session"]
    forge = next(p for place in state["tutorial"]["world"]["places"] for p in place["points"] if p["id"] == "forge")
    assert forge["locked_reason"] is None
    assert forge["action"] == "forge"


def test_merchant_stays_eight_hours_and_is_absent_during_crossing():
    assert tutorial.npc(0)["location"] == "Rosée"
    assert tutorial.npc(28799)["location"] == "Rosée"
    assert tutorial.npc(28800)["travelling"]
    assert tutorial.npc(29399)["location"] is None
    assert tutorial.npc(29400)["location"] == "Brume"
    assert tutorial.npc(58199)["location"] == "Brume"
    assert tutorial.npc(58200)["travelling"]
    assert tutorial.npc(58800)["location"] == "Rosée"


def test_merchant_talk_is_checked_against_current_zone(game):
    player, _ = prepare(game, "hunt", "rosee")
    assert "Léon" in act(game, player, "talk", npc="leon")["events"][-1]["message"]
    game.clock.value = 28800
    with pytest.raises(GameError) as error:
        act(game, player, "talk", npc="leon")
    assert error.value.code == "invalid_npc"
