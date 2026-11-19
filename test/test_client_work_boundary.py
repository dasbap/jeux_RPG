import json
import uuid
from copy import deepcopy

import pytest
from test_living_world import no_network  # noqa: F401
from test_tactics import act, party
from test_tutorial import game  # noqa: F401

from jeuxRPG.multiplayer import tactics
from jeuxRPG.multiplayer.service import GameError


def test_client_path_is_verified_without_a_second_server_search(monkeypatch):
    data = party()
    unit = data["battle"]["players"]["p0"]
    unit["hidden"] = False
    before = deepcopy(data["characters"])
    proposed = [[1, 5], [1, 4]]

    def forbidden(*args, **kwargs):
        raise AssertionError("Le serveur doit vérifier le chemin, pas le rechercher.")

    monkeypatch.setattr(tactics, "path", forbidden)
    act(data, "battle_move", x=1, y=4, path=proposed)
    assert unit["position"] == [1, 6]
    assert unit["route"] == proposed
    assert unit["next_move"] == pytest.approx(tactics.MOVE_TIME)
    assert data["characters"] == before
    proposed[0][0] = 99
    assert unit["route"] == [[1, 5], [1, 4]]


@pytest.mark.parametrize("field", ["hp", "gold", "damage", "next_move", "position"])
def test_client_cannot_attach_authoritative_results_to_a_move(game, field):  # noqa: F811
    token = game.register("Boundary", "Knight")["token"]
    state = game.command(token, uuid.uuid4().hex, "tutorial")["session"]
    before = game.db.execute(
        "SELECT data FROM tutorials WHERE session_id=?", (state["id"],)
    ).fetchone()[0]
    params = {
        "session_id": state["id"],
        "revision": state["revision"],
        "x": 1,
        "y": 5,
        "path": [[1, 5]],
        field: 999999,
    }
    with pytest.raises(GameError) as failure:
        game.command(token, uuid.uuid4().hex, "battle_move", **params)
    assert failure.value.code == "invalid_command"
    after = game.db.execute(
        "SELECT data FROM tutorials WHERE session_id=?", (state["id"],)
    ).fetchone()[0]
    assert json.loads(after) == json.loads(before)
