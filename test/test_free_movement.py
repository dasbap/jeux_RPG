import json
import math
import uuid
from copy import deepcopy

import pytest
from test_living_world import no_network  # noqa: F401
from test_tactics import act, party
from test_tutorial import game  # noqa: F401

from jeuxRPG.multiplayer import fields, free_movement, mob_abilities, tactics, tutorial
from jeuxRPG.multiplayer.service import GameError


@pytest.fixture
def arena(monkeypatch):
    data = party()
    preset = {
        "id": "continuous_test",
        "name": "Test libre",
        "width": 20,
        "height": 20,
        "cover": [],
        "blocked": [],
        "water": [],
        "bridges": [],
        "exits": [],
        "sites": [],
    }
    monkeypatch.setitem(tactics.PRESETS, "continuous_test", preset)
    data["battle"]["preset"] = "continuous_test"
    unit = data["battle"]["players"]["p0"]
    unit.update(position=[4, 4], hidden=False)
    for mob in data["mobs"]:
        mob.update(
            position=[15, 15],
            next_attack=10000,
            next_move=10000,
            calling_until=None,
            needs_call=False,
        )
    return data, unit, preset


def step(data, now):
    tactics.advance(data, now, lambda: 0.5)


def test_older_position_report_cannot_rewind_a_newer_stop(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0, position=[4, 4], position_seq=1)
    act(data, "stop_move", now=0.6, position=[4.4, 4], position_seq=3)
    stopped = deepcopy(unit)
    act(data, "move_axis", now=0.7, x=-1, y=0, position=[4.1, 4], position_seq=2)
    assert unit == stopped


def test_attack_uses_reported_position_and_old_movement_cannot_undo_it(arena):
    data, unit, _ = arena
    mob = data["mobs"][0]
    mob["position"] = [5, 4]
    act(data, "move_axis", x=0, y=1, position=[4, 4], position_seq=1)
    before = mob["stats"]["hp"]["current"]
    with pytest.raises(GameError) as failure:
        act(
            data,
            "strike",
            now=0.6,
            target=mob["combat_id"],
            position=[3, 4],
            position_seq=3,
        )
    assert failure.value.code == "out_of_range"
    assert mob["stats"]["hp"]["current"] == before
    assert unit["position"] == [3, 4]
    act(data, "move_axis", now=0.7, x=1, y=0, position=[4, 4], position_seq=2)
    assert unit["position"] == [3, 4]
    act(data, "strike", now=1, target=mob["combat_id"], position=[4, 4], position_seq=4)
    assert mob["stats"]["hp"]["current"] < before


def test_mob_waits_for_retreat_report_and_cancels_its_out_of_range_hit(arena):
    data, unit, preset = arena
    mob = data["mobs"][0]
    mob.update(position=[5, 4], windup_until=0.3, next_attack=0, attack_range=1.5)
    act(data, "move_axis", x=-1, y=0, position=[4, 4], position_seq=1)
    characters = {
        key: tutorial.unpack(actor) for key, actor in data["characters"].items()
    }
    actor = characters["p0"]
    before = actor.hp.current_value

    def resolve(now):
        tactics._resolve_mob_intent(
            data,
            mob,
            characters,
            data["battle"]["players"],
            preset,
            now,
            lambda: 0.5,
            [],
            "p0",
            [],
        )

    resolve(0.4)
    assert actor.hp.current_value == before
    act(data, "move_axis", now=0.5, x=-1, y=0, position=[3, 4], position_seq=2)
    resolve(0.5)
    assert actor.hp.current_value == before and mob["windup_until"] is None
    act(data, "stop_move", now=1.5, position=[4, 4], position_seq=3)
    mob["windup_until"] = 1.4
    resolve(1.5)
    assert actor.hp.current_value < before


def test_waiting_for_a_position_report_is_bounded_by_input_expiry(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0, position=[4, 4])
    assert free_movement.awaiting_position(unit, 0.4, 0.3)
    assert not free_movement.awaiting_position(unit, free_movement.HEARTBEAT + 0.1, 0.3)


def test_mob_cast_waits_for_new_position_and_loses_a_retreating_target(arena):
    data, unit, preset = arena
    mob = data["mobs"][0]
    mob.update(
        position=[5, 4],
        ability_cast={
            "ability": {"name": "Coup", "type": "damage", "range": 1.5},
            "target": "p0",
            "ends_at": 0.3,
        },
    )
    act(data, "move_axis", x=-1, y=0, position=[4, 4], position_seq=1)
    characters = {
        key: tutorial.unpack(actor) for key, actor in data["characters"].items()
    }
    actor = characters["p0"]
    before = actor.hp.current_value
    assert mob_abilities.advance(
        data, mob, "p0", characters, data["battle"]["players"], preset, 0.4, []
    )
    assert actor.hp.current_value == before and "ability_cast" in mob
    act(data, "move_axis", now=0.5, x=-1, y=0, position=[3, 4], position_seq=2)
    assert not mob_abilities.advance(
        data, mob, "p0", characters, data["battle"]["players"], preset, 0.5, []
    )
    assert actor.hp.current_value == before and "ability_cast" not in mob


def test_axis_moves_between_cells_and_diagonal_has_no_speed_bonus(arena):
    data, unit, _ = arena
    for vector in ([1, 0], [1, 1]):
        unit.update(position=[4, 4], motion_at=0)
        data["battle"]["next_brain"] = 0
        act(data, "move_axis", x=vector[0], y=vector[1])
        step(data, 0.3)
        assert math.dist([4, 4], unit["position"]) == pytest.approx(
            0.3 / tactics.MOVE_TIME
        )
        assert any(v != round(v) for v in unit["position"])


def test_input_expiry_and_long_disconnect_do_not_teleport(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0)
    step(data, 50)
    assert unit["position"][0] <= 4 + free_movement.MAX_CATCHUP / tactics.MOVE_TIME
    position = unit["position"][:]
    step(data, 51)
    assert unit["position"] == position


@pytest.mark.parametrize(
    "axis", [[2, 0], [True, 0], [float("inf"), 0], [float("nan"), 0], ["1", 0]]
)
def test_forged_direction_rejected_without_changing_old_order(arena, axis):
    data, _, _ = arena
    before = deepcopy(data)
    with pytest.raises(GameError) as failure:
        act(data, "move_axis", x=axis[0], y=axis[1])
    assert failure.value.code == "invalid_direction"
    assert data == before


def test_wall_collision_sliding_and_water_are_checked_by_server(arena):
    data, unit, preset = arena
    preset["cover"] = [[5, y] for y in range(20)]
    act(data, "move_axis", x=1, y=1)
    for n in range(1, 9):
        step(data, n * 0.15)
    assert unit["position"][0] < 4.5 - free_movement.RADIUS + 0.01
    assert unit["position"][1] > 4.4
    assert free_movement.fits(preset, unit["position"])
    preset["water"] = [[4, 6]]
    assert not free_movement.fits(preset, [4, 6])
    preset["bridges"] = [[4, 6]]
    assert free_movement.fits(preset, [4, 6])


def test_free_click_path_rejects_wall_and_moves_continuously(arena):
    data, unit, preset = arena
    act(data, "walk", x=6, y=4, path=[[5, 4], [6, 4]])
    step(data, 0.3)
    assert unit["position"] == pytest.approx([4.25, 4])
    before = deepcopy(data)
    preset["cover"] = [[5, 4]]
    with pytest.raises(GameError):
        act(data, "walk", now=0.3, x=6, y=4, path=[[5, 4], [6, 4]])
    assert data == before


def test_stop_and_stun_cancel_the_continuous_direction(arena):
    data, unit, preset = arena
    act(data, "move_axis", x=1, y=0)
    step(data, 0.3)
    act(data, "stop_move", now=0.3)
    position = unit["position"][:]
    step(data, 0.6)
    assert unit["position"] == position
    act(data, "move_axis", now=0.6, x=1, y=0)
    actor = tutorial.unpack(data["characters"]["p0"])
    actor.hp.current_value = 0
    free_movement.advance(unit, preset, actor, 0.9)
    assert unit["position"] == position
    assert unit["motion_axis"] == [0, 0]


def test_ai_sight_and_path_accept_fractional_positions(arena):
    data, unit, preset = arena
    unit["position"] = [4.21, 4.17]
    assert tactics.sight(preset, [6, 4], unit["position"])
    assert tactics.path(preset, [6, 4], unit["position"]) is not None
    preset["cover"] = [[5, 4]]
    assert not tactics.sight(preset, [6, 4], unit["position"])
    # Actual attack checks exact distance, not a rounded target cell.
    data["mobs"][0]["position"] = [6, 4]
    assert not tactics.allowed(data, "p0", data["mobs"][0]["combat_id"], 1.5)


def test_continuous_positions_reveal_integer_fog_cells(arena, monkeypatch):
    data, unit, preset = arena
    monkeypatch.setitem(fields.MAPS, "continuous_test", preset)
    data["field_map"] = "continuous_test"
    unit["position"] = [4.25, 4.18]
    fields.reveal(data)
    assert all(
        all(type(v) is int for v in point) for point in data["battle"]["explored"]
    )


def test_attack_while_moving_slows_instead_of_stopping_then_recovers(arena):
    data, unit, _ = arena
    data["mobs"][0]["position"] = [5, 4]
    data["mobs"][0]["stats"]["hp"] = {"current": 100, "max": 100}
    act(data, "move_axis", x=1, y=0)
    act(data, "strike", target=data["mobs"][0]["combat_id"])
    assert unit["motion_axis"] == [1, 0]
    step(data, 0.3)
    assert unit["position"][0] == pytest.approx(
        4 + 0.3 / tactics.MOVE_TIME * free_movement.ATTACK_SLOW_FACTOR
    )
    assert data["mobs"][0]["stats"]["hp"]["current"] < 100
    # A heartbeat does not erase the combat slowdown.
    act(data, "move_axis", now=0.3, x=1, y=0)
    start = unit["position"][0]
    step(data, 0.6)
    assert unit["position"][0] - start == pytest.approx(
        0.3 / tactics.MOVE_TIME * free_movement.ATTACK_SLOW_FACTOR
    )
    unit["attack_slow_until"] = 0.6
    act(data, "move_axis", now=0.6, x=0, y=1)
    start = unit["position"][1]
    step(data, 0.9)
    assert unit["position"][1] - start == pytest.approx(0.3 / tactics.MOVE_TIME)


def test_cast_does_not_discard_direction_and_accepts_redirection(arena):
    data, unit, _ = arena
    data["mobs"][0]["position"] = [5, 4]
    act(data, "move_axis", x=0, y=1)
    act(data, "skill", skill_name="Sword Slash", target=data["mobs"][0]["combat_id"])
    assert unit["casting"] and unit["motion_axis"] == [0, 1]
    act(data, "move_axis", x=-1, y=0)
    step(data, 0.3)
    assert unit["position"][0] < 4 and unit["casting"]
    assert unit["position"][0] == pytest.approx(
        4 - 0.3 / tactics.MOVE_TIME * free_movement.ATTACK_SLOW_FACTOR
    )


def test_hostile_pursuit_is_continuous_and_keeps_its_speed_across_waypoints(arena):
    data, unit, _ = arena
    mob = data["mobs"][0]
    mob.update(
        position=[8, 4],
        target="p0",
        state="chase",
        next_move=0,
        next_attack=10000,
        windup_until=None,
        alerted=True,
    )
    act(data, "move_axis", x=0, y=0)
    start = mob["position"][:]
    for n in range(1, 9):
        step(data, n * 0.15)
        assert any(v != round(v) for v in mob["position"]) or n % 8 == 0
    assert math.dist(start, mob["position"]) == pytest.approx(
        1.2 / tactics.GOBLIN_MOVE_TIME
    )
    assert mob["position"][0] < 8


def test_authenticated_command_flow_accepts_direction_without_position_or_client_clock(
    game,  # noqa: F811
):
    token = game.register("FreeMotion", "Knight")["token"]
    state = game.command(token, uuid.uuid4().hex, "tutorial")["session"]
    row = game.db.execute(
        "SELECT data FROM tutorials WHERE session_id=?", (state["id"],)
    ).fetchone()
    data = json.loads(row[0])
    tutorial.migrate(data, 0)
    tutorial.spawn(data, 0, lambda: 0.5, [], origin="explore")
    unit = data["battle"]["players"][state["me"]]
    unit["hidden"] = False
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(data), state["id"]),
    )
    result = game.command(
        token,
        uuid.uuid4().hex,
        "move_axis",
        session_id=state["id"],
        revision=state["revision"],
        x=0,
        y=-1,
    )
    assert result["session"]["tutorial"]["battle"]["movement_model"] == "continuous-v1"
    with pytest.raises(GameError) as failure:
        game.command(
            token,
            uuid.uuid4().hex,
            "move_axis",
            session_id=state["id"],
            revision=state["revision"],
            x=0,
            y=-1,
            elapsed=1000,
        )
    assert failure.value.code == "invalid_command"


def test_legal_client_positions_are_accepted_exactly_without_server_drift(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0, position=[4, 4])
    step(data, 0.3)
    assert unit["position"] == [4, 4]
    act(data, "move_axis", now=0.3, x=1, y=0, position=[4.25, 4])
    assert unit["position"] == [4.25, 4]
    step(data, 0.6)
    assert unit["position"] == [4.25, 4]
    act(data, "stop_move", now=0.6, position=[4.5, 4])
    step(data, 1.2)
    assert unit["position"] == [4.5, 4]


def test_client_reports_cannot_create_distance_by_spamming_or_switching_modes(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0, position=[4, 4])
    origin = unit["position"][:]
    for i in range(25):
        act(data, "move_axis", x=1, y=0, position=[4 + (i + 1) * 0.1, 4])
    for _ in range(10):
        act(data, "stop_move", position=unit["position"][:])
        with pytest.raises(GameError, match="Vitesse maximale"):
            act(data, "move_axis", x=1, y=0, position=[unit["position"][0] + 0.1, 4])
    assert (
        math.dist(origin, unit["position"])
        <= free_movement.POSITION_JITTER / tactics.MOVE_TIME + 1e-7
    )


def test_report_rejects_teleport_nan_and_walls_without_mutating_position(arena):
    data, unit, preset = arena
    preset["cover"] = [[5, 4]]
    for target in ([15, 15], [math.nan, 4], [4.4, 4]):
        with pytest.raises(GameError):
            act(data, "move_axis", x=1, y=0, position=target)
        assert unit["position"] == [4, 4]


def test_delayed_legal_reports_are_not_capped_to_a_heartbeat(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0, position=[4, 4])
    for n in range(1, 5):
        now = n * 2.4
        step(data, now)
        act(
            data,
            "move_axis",
            now=now,
            x=1,
            y=0,
            position=[4 + now / tactics.MOVE_TIME, 4],
        )
        assert unit["position"] == pytest.approx([4 + now / tactics.MOVE_TIME, 4])


def test_sustained_excess_speed_exhausts_jitter_allowance(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0, position=[4, 4])
    with pytest.raises(GameError, match="Vitesse maximale"):
        for n in range(1, 20):
            now = n * 0.3
            act(
                data,
                "move_axis",
                now=now,
                x=1,
                y=0,
                position=[4 + now / tactics.MOVE_TIME * 2, 4],
            )


def test_position_allowance_is_bounded_after_idle_and_uses_attack_speed(arena):
    data, unit, _ = arena
    act(data, "move_axis", x=1, y=0, position=[4, 4])
    act(data, "stop_move", position=[4, 4])
    step(data, 100)
    with pytest.raises(GameError, match="Vitesse maximale"):
        act(data, "move_axis", now=100, x=1, y=0, position=[8, 4])
    unit["position_budget"] = 0
    unit["position_budget_at"] = 100
    unit["attack_slow_until"] = 102
    step(data, 100.6)
    expected = 0.6 / tactics.MOVE_TIME * free_movement.ATTACK_SLOW_FACTOR
    with pytest.raises(GameError, match="Vitesse maximale"):
        act(data, "move_axis", now=100.6, x=1, y=0, position=[4.5, 4])
    act(data, "move_axis", now=100.6, x=1, y=0, position=[4 + expected, 4])


def test_authenticated_position_report_and_stop(game):  # noqa: F811
    token = game.register("PositionReport", "Knight")["token"]
    state = game.command(token, uuid.uuid4().hex, "tutorial")["session"]
    row = game.db.execute(
        "SELECT data FROM tutorials WHERE session_id=?", (state["id"],)
    ).fetchone()
    data = json.loads(row[0])
    tutorial.migrate(data, 0)
    tutorial.spawn(data, 0, lambda: 0.5, [], origin="explore")
    unit = data["battle"]["players"][state["me"]]
    unit["hidden"] = False
    position = unit["position"][:]
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(data), state["id"]),
    )
    for action in ("move_axis", "stop_move"):
        result = game.command(
            token,
            uuid.uuid4().hex,
            action,
            session_id=state["id"],
            revision=state["revision"],
            position=position,
            **({"x": 1, "y": 0} if action == "move_axis" else {}),
        )
        assert (
            result["session"]["tutorial"]["battle"]["players"][state["me"]]["position"]
            == position
        )
        state = result["session"]


def test_click_route_keeps_its_speed_between_online_snapshots(arena):
    from jeuxRPG.multiplayer.progression import RATIO

    data, unit, _ = arena
    unit.update(free_motion=True, route=[[8, 4]], motion_at=0)
    step(data, RATIO)
    assert unit["position"][0] == pytest.approx(4 + RATIO / tactics.MOVE_TIME)
