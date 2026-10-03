import json
import uuid

import pytest

from jeuxRPG.multiplayer import encounters, tutorial, world, tactics
from test_tutorial import combat_fixture, win
from jeuxRPG.multiplayer.service import GameError, GameService


class Clock:
    value = 0

    def now(self):
        return self.value


@pytest.mark.parametrize("draws,expected", [([.91], 0), ([.5, .31], 1), ([.5, .2, .11], 2), ([.5, .2, .05, .04], 3), ([.5, .2, .05, .02, .002], 4), ([.5, .2, .05, .02, .0005], 5)])
def test_sequential_group_draws_stop_at_first_failure(draws, expected):
    iterator = iter(draws)
    assert encounters.group_size("D", 2, 2, lambda: next(iterator)) == expected
    assert list(iterator) == []


def test_ranks_limit_and_level_difference():
    assert encounters.probabilities("D", 2, 2) == encounters.GOBLIN_CHAIN
    for rank in tuple(encounters.RANKS)[:-1]:
        assert encounters.group_size(rank, 2, 2, lambda: 0) == 5
    assert encounters.group_size("E", 2, 2, lambda: pytest.fail("Passive creatures must not attack")) == 0
    assert encounters.probabilities("D", 10, 2)[0] < .9
    assert encounters.probabilities("D", 1, 5)[0] > .9
    assert encounters.probabilities("S", 2, 2)[1] < encounters.probabilities("D", 2, 2)[1]
    with pytest.raises(ValueError):
        encounters.probabilities("Z", 2, 2)


@pytest.fixture
def service(tmp_path):
    game = GameService(tmp_path / "encounters.sqlite3", Clock(), random_source=lambda: .5)
    yield game
    game.close()


def act(game, player, action, **params):
    state = game.state(player["token"])["session"]
    if state and action != "tutorial":
        params.update(session_id=state["id"], revision=state["revision"])
    return game.command(player["token"], uuid.uuid4().hex, action, **params)["session"]


def test_enemy_attacks_without_player_command_with_jitter_and_no_catchup_burst(service):
    player = service.register("Knight", "Knight")
    act(service, player, "tutorial")
    state = act(service, player, "explore")
    initial = state["tutorial"]["players"][0]["hp"]
    service.clock.value = 20
    service.tick()
    assert service.state(player["token"])["session"]["tutorial"]["players"][0]["hp"] == initial
    party = combat_fixture(service, player["token"])
    party["battle"]["players"][player["player"]["id"]]["hidden"] = False
    service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    service.clock.value = 22
    service.tick()
    service.clock.value = 24
    service.tick()
    state = service.state(player["token"])["session"]
    damage = initial - state["tutorial"]["players"][0]["hp"]
    assert damage > 0
    assert state["tutorial"]["mobs"][0]["next_attack"] == 36
    service.clock.value = 100000
    service.tick()
    assert service.state(player["token"])["session"]["tutorial"]["players"][0]["hp"] == initial
    service.clock.value += 2
    service.tick()
    assert service.state(player["token"])["session"]["tutorial"]["players"][0]["hp"] == initial - damage
    service.tick()
    assert service.state(player["token"])["session"]["tutorial"]["players"][0]["hp"] == initial - damage


def test_five_enemies_have_distinct_targets_and_cannot_reward_twice(service):
    player = service.register("Knight", "Knight")
    act(service, player, "tutorial")
    service.random = lambda: 0
    state = act(service, player, "explore")
    enemies = combat_fixture(service, player["token"])["mobs"]
    assert len(enemies) == 5
    assert len({m["combat_id"] for m in enemies}) == 5
    assert state["tutorial"]["players"][0]["skills"][0]["targets"] == []
    combat_fixture(service, player["token"])
    for target in ([], {}, None):
        with pytest.raises(GameError) as failure:
            act(service, player, "skill", skill_name="Sword Slash", target=target)
        assert failure.value.code == "invalid_target"
    target = enemies[-1]["combat_id"]
    for _ in range(30):
        service.clock.value += 61
        state = act(service, player, "strike", target=target)
        if not any(m["combat_id"] == target for m in state["tutorial"]["mobs"]):
            break
    assert len(state["tutorial"]["mobs"]) == 4
    inventory = state["tutorial"]["players"][0]["inventory"]
    assert inventory == {}
    assert len(state["tutorial"]["battle"]["corpses"]) == 1
    assert state["tutorial"]["players"][0]["exp"] == 50
    service.clock.value += 61
    with pytest.raises(GameError) as failure:
        act(service, player, "strike", target=target)
    assert failure.value.code == "invalid_target"
    assert service.state(player["token"])["session"]["tutorial"]["players"][0]["inventory"] == inventory


def test_trip_stops_at_each_encounter_and_resumes_after_victory(service, monkeypatch):
    monkeypatch.setattr(tutorial, "TRAVEL_ENCOUNTER_CHANCE", 1)
    player = service.register("Knight", "Knight")
    state = act(service, player, "tutorial")
    row = service.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()
    party = json.loads(row[0])
    party.update(step="hunt", quest="active", position="mira", visited=["clearing", "rosee"])
    party["characters"][player["player"]["id"]]["level"] = 2
    service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    state = act(service, player, "move", destination="hunt")
    assert state["tutorial"]["moving"]
    stops = []
    for _ in range(100):
        adventure = state["tutorial"]
        if adventure["battle"]:
            stops.append(adventure["position"])
            state = win(service, player["token"])
        elif adventure["transit"]:
            service.clock.value = adventure["transit"]["ready_at"]
            service.tick()
            state = service.state(player["token"])["session"]
        else:
            break
    assert set(stops) == {"rosee_lisiere", "lisiere"}
    assert state["tutorial"]["position"] == "hunt"
    assert state["tutorial"]["journey"] == []
    assert state["tutorial"]["transit"] is None
    assert 1 <= state["tutorial"]["kills"] <= 3


def test_server_rejects_remote_actions_and_unknown_paths(service):
    player = service.register("Knight", "Knight")
    act(service, player, "tutorial")
    for action, params in (("talk", {"npc": "mira"}), ("craft", {"recipe": "veste"}), ("move", {"destination": "brume"}), ("move", {"destination": []})):
        with pytest.raises(GameError):
            act(service, player, action, **params)
    assert service.state(player["token"])["session"]["tutorial"]["position"] == "clearing"


def test_old_single_enemy_save_migrates_and_keeps_cooldown():
    party = tutorial.new_party([{"id": "p", "name": "Knight", "class_name": "Knight"}])
    tutorial.spawn(party, 0, lambda: .5, [])
    party.pop("mobs")
    party.pop("position")
    party.pop("journey")
    tutorial.migrate(party, 50)
    assert party["position"] == "clearing"
    assert len(party["mobs"]) == 1
    assert party["mobs"][0]["next_attack"] == 90
    assert world.path("clearing", "rosee", {"clearing", "rosee"}) == ["clearing_rosee", "rosee"]


def test_group_defeat_cancels_trip_and_recovers_in_safe_place(service):
    player = service.register("Knight", "Knight")
    act(service, player, "tutorial")
    service.random = lambda: 0
    state = act(service, player, "explore")
    party = json.loads(service.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()[0])
    party["characters"][player["player"]["id"]]["stats"]["hp"]["current"] = 1
    party["journey"] = ["rosee"]
    service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    party = combat_fixture(service, player["token"])
    party["battle"]["players"][player["player"]["id"]]["hidden"] = False
    party["mobs"][0]["allies"] = []
    service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    service.tick()
    service.clock.value = 2
    service.tick()
    adventure = service.state(player["token"])["session"]["tutorial"]
    assert adventure["mobs"] == []
    assert adventure["mob"] is None
    assert adventure["journey"] == []
    assert adventure["position"] == "clearing"
    assert adventure["step"] == "clearing"
    assert adventure["players"][0]["hp"] == adventure["players"][0]["max_hp"]


def test_pending_journey_and_enemy_deadline_survive_restart(service, monkeypatch):
    monkeypatch.setattr(tutorial, "TRAVEL_ENCOUNTER_CHANCE", 1)
    player = service.register("Knight", "Knight")
    state = act(service, player, "tutorial")
    party = json.loads(service.db.execute("SELECT data FROM tutorials WHERE session_id=?", (state["id"],)).fetchone()[0])
    party.update(step="road", visited=["clearing"], position="clearing")
    service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), state["id"]))
    state = act(service, player, "move", destination="rosee")
    service.clock.value = state["tutorial"]["transit"]["ready_at"]
    service.tick()
    state = service.state(player["token"])["session"]
    before = state["tutorial"]
    assert before["battle"]["hostiles_alive"]
    assert before["position"] == "clearing_rosee"
    assert before["journey"] == ["rosee"]
    database = service.db.execute("PRAGMA database_list").fetchone()[2]
    reopened = GameService(database, service.clock, random_source=lambda: .5)
    try:
        assert reopened.state(player["token"])["session"]["tutorial"] == before
    finally:
        reopened.close()


def test_rank_order_and_group_difficulty():
    ranks = ("SSS", "SS", "S", "AA", "A", "B", "C", "D", "E")
    assert tuple(encounters.RANKS) == ranks
    for stronger, weaker in zip(ranks[:-2], ranks[1:-1]):
        high = encounters.probabilities(stronger, 2, 2)
        low = encounters.probabilities(weaker, 2, 2)
        assert all(a < b for a, b in zip(high[1:], low[1:]))
