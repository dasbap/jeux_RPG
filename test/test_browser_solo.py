import io
import json
import zipfile

import pytest

from jeuxRPG.multiplayer.browser_solo import SoloGame
from jeuxRPG.multiplayer.browser_solo_assets import client_csp, engine_archive
from jeuxRPG.multiplayer.service import GameError


def test_solo_tutorial_survives_local_save():
    game = SoloGame()
    account = game.choose({"action": "create", "name": "Local", "class_name": "Knight"})
    token = account["token"]
    result = game.dispatch(
        "/api/commands",
        {"request_id": "solo-tutorial-01", "action": "tutorial", "params": {"field_mode": True}},
        token,
    )
    session_id = result["session"]["id"]
    saved = game.save()
    game.close()
    restored = SoloGame(saved)
    assert restored.characters() == account
    state = restored.dispatch("/api/state", token=token)
    assert state["session"]["id"] == session_id
    assert state["session"]["tutorial"]
    restored.close()


def test_solo_separates_characters_and_rejects_online_features():
    game = SoloGame()
    first = game.choose({"action": "create", "name": "Local", "class_name": "Knight"})
    with pytest.raises(GameError, match="déjà"):
        game.choose({"action": "create", "name": "Autre", "class_name": "Knight"})
    result = json.loads(game.request({"path": "/api/commands", "token": first["token"], "body": {"action": "join"}}))
    assert result["body"]["error"] == "online_required"
    assert json.loads(game.request({"path": "/api/state", "token": "online-token"}))["status"] == 401
    game.dispatch("/api/account/logout")
    assert game.characters()["selected"] is None
    assert len(game.characters()["characters"]) == 1
    game.close()


def test_solo_archive_contains_engine_without_runtime_secrets():
    with zipfile.ZipFile(io.BytesIO(engine_archive())) as archive:
        names = archive.namelist()
    assert "jeuxRPG/multiplayer/browser_solo.py" in names
    assert all(name.endswith((".py", ".json", ".sql")) for name in names)
    assert all(name.startswith("jeuxRPG/") for name in names)
    assert "wasm-unsafe-eval" in client_csp("/solo_worker.js")
    assert "wasm-unsafe-eval" not in client_csp("/")
