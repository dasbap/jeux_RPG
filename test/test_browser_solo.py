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
    life = result["session"]["tutorial"]["living_world"]
    assert life["towns"] and life["merchant"]["stock"]
    saved = game.save()
    game.close()
    restored = SoloGame(saved)
    assert restored.characters() == account
    state = restored.dispatch("/api/state", token=token)
    assert state["session"]["id"] == session_id
    assert state["session"]["tutorial"]
    assert state["session"]["tutorial"]["living_world"]["towns"] == life["towns"]
    assert restored.service.world_life is not None
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
    for module in ("living_world", "living_world_catalog", "living_world_service"):
        assert f"jeuxRPG/multiplayer/{module}.py" in names
    assert all(name.endswith((".py", ".json", ".sql")) for name in names)
    assert all(name.startswith("jeuxRPG/") for name in names)
    assert "wasm-unsafe-eval" in client_csp("/solo_worker.js")
    assert "wasm-unsafe-eval" not in client_csp("/")


def test_multiple_solo_characters_keep_separate_adventures_after_reload():
    game = SoloGame()
    first = game.choose({'action': 'create', 'name': 'Premier', 'class_name': 'Knight'})
    first_token, first_id = first['token'], first['selected']
    first_session = game.dispatch('/api/commands', {
        'request_id': 'solo-first-adventure', 'action': 'tutorial', 'params': {'field_mode': True}
    }, first_token)['session']
    row = game.db.execute('SELECT data FROM tutorials WHERE session_id=?', (first_session['id'],)).fetchone()
    party = json.loads(row[0])
    party['gold'][first_id] = 123
    party['inventory'][first_id]['bois'] = 7
    game.db.execute('UPDATE tutorials SET data=? WHERE session_id=?', (json.dumps(party), first_session['id']))
    second = game.choose({'action': 'create', 'name': 'Deuxieme', 'class_name': 'Mage'})
    second_token, second_id = second['token'], second['selected']
    second_session = game.dispatch('/api/commands', {
        'request_id': 'solo-second-adventure', 'action': 'tutorial', 'params': {'field_mode': True}
    }, second_token)['session']
    assert first_session['id'] != second_session['id']
    assert first_id != second_id
    assert len(second['characters']) == 2
    with pytest.raises(GameError, match='Choisissez'):
        game.dispatch('/api/state', token=first_token)
    saved = game.save()
    game.close()
    restored = SoloGame(saved)
    try:
        assert len(restored.characters()['characters']) == 2
        assert restored.characters()['selected'] == second_id
        second_state = restored.dispatch('/api/state', token=second_token)
        assert second_state['session']['id'] == second_session['id']
        mage = next(p for p in second_state['session']['tutorial']['players'] if p['id'] == second_id)
        assert mage['inventory'].get('bois', 0) != 7
        selected = restored.choose({'action': 'select', 'player_id': first_id})
        state = restored.dispatch('/api/state', token=selected['token'])
        assert state['session']['id'] == first_session['id']
        knight = next(p for p in state['session']['tutorial']['players'] if p['id'] == first_id)
        assert knight['inventory']['bois'] == 7
        assert knight['gold'] == 123
    finally:
        restored.close()
