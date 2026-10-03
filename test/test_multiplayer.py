import asyncio
import concurrent.futures
import json
import threading
from types import SimpleNamespace
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from jeuxRPG.multiplayer.clock import GameClock
from jeuxRPG.multiplayer.discord_adapter import DiscordAdapter
from jeuxRPG.multiplayer.server import RPGServer
from jeuxRPG.multiplayer.service import GameService, GameError


class Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def advance(self, real_seconds):
        self.value += real_seconds * 3


@pytest.fixture
def game(tmp_path):
    service = GameService(tmp_path / "game.sqlite3", Clock())
    yield service
    service.close()


def player(game, name="Alice", class_name="Knight"):
    return game.register(name, class_name)["token"]


def command(game, token, action, **params):
    import uuid
    return game.command(token, uuid.uuid4().hex, action, **params)


def duel(game):
    first = player(game)
    second = player(game, "Bob", "Mage")
    room = command(game, first, "create")
    joined = command(game, second, "join", invite=room["invite"])["session"]
    started = command(game, first, "start", session_id=joined["id"], revision=joined["revision"])["session"]
    return first, second, started


def test_clock_ratio_without_wall_clock_drift():
    source = {"mono": 10.0, "wall": 100.0}
    clock = GameClock(100, monotonic=lambda: source["mono"], wall=lambda: source["wall"])
    source["mono"] += 180
    source["wall"] -= 5000
    assert clock.now() == 540
    assert clock.real_seconds(60) == 20


def test_two_players_share_health_and_cooldown(game):
    first, second, room = duel(game)
    before = next(p for p in room["players"] if p["id"] != room["me"])["hp"]
    result = command(game, first, "attack", session_id=room["id"], revision=room["revision"])["session"]
    other = game.state(second, room["id"])
    assert other["players"] == result["players"]
    assert next(p for p in other["players"] if p["id"] == other["me"])["hp"] < before
    me = next(p for p in result["players"] if p["id"] == result["me"])
    assert me["cooldown_real_seconds"] == 1.2
    game.clock.advance(1.19)
    with pytest.raises(GameError, match="disponible"):
        command(game, first, "attack", session_id=room["id"], revision=result["revision"])
    game.clock.advance(0.011)
    command(game, first, "attack", session_id=room["id"], revision=result["revision"])


def test_replayed_command_is_applied_once_and_conflicting_payload_rejected(game):
    first, second, room = duel(game)
    args = {"session_id": room["id"], "revision": room["revision"]}
    once = game.command(first, "attack_request_1", "attack", **args)
    game.clock.advance(5)
    again = game.command(first, "attack_request_1", "attack", **args)
    assert again == once
    assert game.state(second, room["id"])["revision"] == once["session"]["revision"]
    with pytest.raises(GameError) as error:
        game.command(first, "attack_request_1", "leave", **args)
    assert error.value.code == "request_conflict"


def test_simultaneous_commands_are_serialized(game):
    first, second, room = duel(game)
    barrier = threading.Barrier(2)
    def attack(token):
        barrier.wait()
        try:
            return command(game, token, "attack", session_id=room["id"], revision=room["revision"])
        except GameError as error:
            return error.code
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attack, [first, second]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "stale_revision" in results
    assert game.state(first, room["id"])["revision"] == room["revision"] + 1


def test_second_database_connection_cannot_lose_updates(game, tmp_path):
    first, second, room = duel(game)
    other_service = GameService(tmp_path / "game.sqlite3", game.clock)
    try:
        command(game, first, "attack", session_id=room["id"], revision=room["revision"])
        with pytest.raises(GameError) as error:
            command(other_service, second, "attack", session_id=room["id"], revision=room["revision"])
        assert error.value.code == "stale_revision"
    finally:
        other_service.close()


def test_session_and_receipt_survive_restart(tmp_path):
    database = tmp_path / "restart.sqlite3"
    clock = Clock()
    initial = GameService(database, clock)
    first, second, room = duel(initial)
    result = initial.command(first, "persisted_attack", "attack", session_id=room["id"], revision=room["revision"])
    initial.close()
    clock.advance(.2)
    reopened = GameService(database, clock)
    try:
        restored = reopened.state(second, room["id"])
        assert restored["revision"] == result["session"]["revision"]
        assert [p["hp"] for p in restored["players"]] == [p["hp"] for p in result["session"]["players"]]
        assert reopened.command(first, "persisted_attack", "attack", session_id=room["id"], revision=room["revision"]) == result
        assert next(p for p in restored["players"] if p["id"] != restored["me"])["cooldown_real_seconds"] == 1
    finally:
        reopened.close()


def test_restart_counts_offline_time():
    clock = GameClock(100, monotonic=lambda: 50, wall=lambda: 280)
    assert clock.now() == 540


def test_restart_checkpoint_prevents_time_going_backwards():
    clock = GameClock(100, monotonic=lambda: 50, wall=lambda: 80, minimum_game=540)
    assert clock.now() == 540


def test_persisted_time_cannot_be_rewound(game):
    game.clock.advance(180)
    token = player(game)
    assert game.state(token)["game_time"] == 540
    game.clock.value = 10
    assert game.state(token)["game_time"] == 540


def test_ticker_expires_session_without_client_requests(game, http_server):
    token = player(game)
    room = command(game, token, "create")["session"]
    game.clock.advance(1801)
    import time
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with game._lock:
            state = game.db.execute("SELECT state FROM sessions WHERE id=?", (room["id"],)).fetchone()[0]
        if state == "finished":
            break
        threading.Event().wait(0.01)
    assert state == "finished"


def test_cannot_access_or_mutate_another_session(game):
    first, second, room = duel(game)
    intruder = player(game, "Intrus")
    for operation in (lambda: game.state(intruder, room["id"]),
                      lambda: command(game, intruder, "attack", session_id=room["id"], revision=room["revision"])):
        with pytest.raises(GameError) as error:
            operation()
        assert error.value.status == 404
    with pytest.raises(GameError):
        command(game, first, "attack", session_id=room["id"], revision=room["revision"], actor_id=room["players"][0]["id"])


def test_lobby_permissions_and_unique_active_session(game):
    first = player(game)
    second = player(game, "Bob")
    room = command(game, first, "create")
    with pytest.raises(GameError):
        command(game, first, "create")
    with pytest.raises(GameError):
        command(game, first, "start", session_id=room["session"]["id"], revision=1)
    joined = command(game, second, "join", invite=room["invite"])["session"]
    with pytest.raises(GameError) as error:
        command(game, second, "start", session_id=joined["id"], revision=joined["revision"])
    assert error.value.status == 403
    with pytest.raises(GameError):
        command(game, player(game, "Troisième"), "join", invite=room["invite"])


def test_expiration_and_leave_release_players(game):
    first, second, room = duel(game)
    game.clock.advance(300)
    game.tick()
    assert game.state(first, room["id"])["state"] == "finished"
    assert game.state(first)["session"] is None
    room = command(game, first, "create")["session"]
    command(game, first, "leave", session_id=room["id"], revision=room["revision"])
    command(game, first, "create")


def test_full_duel_finishes_and_persists_result(game):
    first, second, room = duel(game)
    while room["state"] == "running":
        room = command(game, first, "attack", session_id=room["id"], revision=room["revision"])["session"]
        game.clock.advance(3)
    assert room["winner"] == room["me"]
    assert game.state(second, room["id"])["winner"] == room["winner"]
    with pytest.raises(GameError):
        command(game, first, "attack", session_id=room["id"], revision=room["revision"])
    assert command(game, second, "create")["session"]["state"] == "lobby"


@pytest.mark.parametrize("name", ["", "a" * 33, "A\x00B", "\u202eab", 42])
def test_invalid_names(game, name):
    with pytest.raises(GameError):
        player(game, name)


@pytest.mark.parametrize("class_name", ["Goblin", "../../Knight", None, {}, "Mob"])
def test_only_playable_classes(game, class_name):
    with pytest.raises(GameError):
        player(game, class_name=class_name)


def test_invalid_auth_and_revision_do_not_mutate(game):
    first, second, room = duel(game)
    with pytest.raises(GameError) as error:
        game.state("x" * 43)
    assert error.value.status == 401
    with pytest.raises(GameError):
        command(game, first, "attack", session_id=room["id"], revision=True)
    assert game.state(second, room["id"])["revision"] == room["revision"]


def interaction(guild, user, request):
    return SimpleNamespace(guild_id=guild, id=request,
                           user=SimpleNamespace(id=user, display_name=f"Joueur {user}"))


def test_discord_identity_and_guild_isolation(game):
    adapter = DiscordAdapter(game)
    async def scenario():
        room = await adapter.execute(interaction(1, 10, 100000001), "create")
        joined = await adapter.execute(interaction(1, 20, 100000002), "join", {"invite": room["invite"]})
        with pytest.raises(GameError):
            await adapter.execute(interaction(2, 20, 100000003), "join", {"invite": room["invite"]})
        with pytest.raises(GameError):
            await adapter.execute(interaction(None, 20, 100000004), "state")
        assert joined["session"]["me"] != room["session"]["me"]
        with pytest.raises(GameError):
            command(game, player(game, "Local"), "join", invite=room["invite"])
        return room
    room = asyncio.run(scenario())
    replay = asyncio.run(adapter.execute(interaction(1, 10, 100000001), "create"))
    assert replay == room


@pytest.fixture
def http_server(game, tmp_path):
    server = RPGServer(("127.0.0.1", 0), game, log_directory=tmp_path / ".logs")
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, path, body=None, token=None, headers=None):
    payload = json.dumps(body).encode() if body is not None else None
    values = {"Content-Type": "application/json"} if payload else {}
    if token:
        values["Authorization"] = f"Bearer {token}"
    values.update(headers or {})
    req = Request(f"http://127.0.0.1:{server.server_address[1]}{path}", data=payload, headers=values)
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def test_http_auth_origin_host_and_payload_limits(http_server):
    assert request(http_server, "/api/state")[0] == 401
    assert request(http_server, "/api/register", {"name": "Alice", "class_name": "Knight"}, headers={"Origin": "https://evil.example"})[0] == 403
    assert request(http_server, "/api/state", headers={"Host": "evil.example"})[0] == 403
    assert request(http_server, "/api/register", {"name": "a" * 5000, "class_name": "Knight"})[0] == 413
    assert request(http_server, "/api/register", {"name": "Alice", "class_name": "Knight"}, headers={"Content-Type": "text/plain"})[0] == 415
    assert request(http_server, "/api/register", {"name": "Alice", "class_name": "Knight", "player_id": "stolen"})[0] == 400


def test_http_two_player_end_to_end(http_server):
    _, first = request(http_server, "/api/register", {"name": "Alice", "class_name": "Knight"})
    _, second = request(http_server, "/api/register", {"name": "Bob", "class_name": "Mage"})
    def send(token, identifier, action, **params):
        status, data = request(http_server, "/api/commands", {"request_id": identifier, "action": action, "params": params}, token)
        assert status == 200, data
        return data
    room = send(first["token"], "http_create", "create")
    joined = send(second["token"], "http_join", "join", invite=room["invite"])["session"]
    started = send(first["token"], "http_start", "start", session_id=joined["id"], revision=joined["revision"])["session"]
    action = send(first["token"], "http_attack", "attack", session_id=started["id"], revision=started["revision"])
    status, other = request(http_server, f"/api/sessions/{started['id']}", token=second["token"])
    assert status == 200
    assert other["players"] == action["session"]["players"]
    assert "token" not in json.dumps(other)


def test_http_rate_limit(http_server):
    for i in range(10):
        assert request(http_server, "/api/register", {"name": f"Joueur {i}", "class_name": "Knight"})[0] == 201
    assert request(http_server, "/api/register", {"name": "Encore", "class_name": "Knight"})[0] == 429


@pytest.mark.parametrize("body", [
    b'{"name":"Alice","name":"Bob","class_name":"Knight"}',
    b'{"name":NaN,"class_name":"Knight"}',
    b'[]',
    b'not-json',
])
def test_http_rejects_ambiguous_or_invalid_json(http_server, body):
    req = Request(f"http://127.0.0.1:{http_server.server_address[1]}/api/register", data=body,
                  headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as error:
        urlopen(req, timeout=3)
    assert error.value.code == 400
    assert json.loads(error.value.read())["error"] == "invalid_json"


def test_static_page_security_headers(http_server):
    with urlopen(f"http://127.0.0.1:{http_server.server_address[1]}/", timeout=3) as response:
        assert response.status == 200
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert b"app.js" in response.read()



def test_ticker_logs_failure_keeps_http_alive_and_retries(game, http_server, caplog, monkeypatch):
    succeeded = threading.Event()
    original = game.tick
    calls = []

    def flaky_tick():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("simulation-test-failure")
        original()
        succeeded.set()

    monkeypatch.setattr(game, "tick", flaky_tick)
    assert succeeded.wait(3)
    assert http_server._ticker.is_alive()
    assert not http_server._stop.is_set()
    with urlopen(f"http://127.0.0.1:{http_server.server_address[1]}/", timeout=3) as response:
        assert response.status == 200
    assert "simulation-test-failure" in caplog.text


def test_bad_saved_session_does_not_stop_other_sessions(game, caplog):
    bad = player(game, "Sauvegarde cassée")
    good = player(game, "Sauvegarde saine")
    broken = command(game, bad, "tutorial")["session"]
    healthy = command(game, good, "tutorial")["session"]
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", ("{", broken["id"]))
    game.clock.advance(2)
    game.tick()
    state = game.state(good)["session"]
    assert state["revision"] > healthy["revision"]
    assert "Simulation interrompue" in caplog.text



def test_main_process_stays_alive_after_printing_address(tmp_path):
    import os
    import queue
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    environment = {**os.environ, "PYTHONPATH": str(root.parent) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    process = subprocess.Popen([sys.executable, str(root / "main.py"), "--database", str(tmp_path / "main.sqlite3"), "--port", "0"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment, cwd=root)
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
    reader.start()
    try:
        line = lines.get(timeout=5)
        assert line.startswith("RPG multijoueur : http://127.0.0.1:")
        address = line.split(" : ", 1)[1].strip()
        for _ in range(3):
            with urlopen(address, timeout=3) as response:
                assert response.status == 200
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)
        reader.join(timeout=1)
        process.stdout.close()
        process.stderr.close()


def test_invitation_remains_valid_for_thirty_real_minutes(game):
    first = player(game)
    second = player(game, "Bob")
    created = command(game, first, "create")
    assert created["session"]["remaining_real_seconds"] == 1800
    game.clock.advance(1799)
    joined = command(game, second, "join", invite=created["invite"])
    assert len(joined["session"]["players"]) == 2


def test_expired_invitation_cannot_join_after_thirty_minutes(game):
    first = player(game)
    second = player(game, "Bob")
    created = command(game, first, "create")
    game.clock.advance(1801)
    with pytest.raises(GameError) as failure:
        command(game, second, "join", invite=created["invite"])
    assert failure.value.code == "invalid_invite"


def test_network_logger_flat_lines_and_redacts_payload(tmp_path):
    from jeuxRPG.multiplayer.network_log import create_logger, write
    logger = create_logger(tmp_path / ".logs")
    write(logger, "ACTION_REQUESTED", action="explore\nFORGED", peer="127.0.0.1")
    for handler in logger.handlers:
        handler.close()
    contents = (tmp_path / ".logs" / "network.log").read_text()
    assert len(contents.splitlines()) == 1
    assert "ACTION_REQUESTED action=explore FORGED" in contents
    assert not list((tmp_path / ".logs").glob("network.log.*"))


def test_http_network_logs_actions_failures_and_omits_combat_secrets(game, http_server):
    import uuid
    token = player(game)
    status, created = request(http_server, "/api/commands", {"request_id": uuid.uuid4().hex, "action": "create", "params": {}}, token)
    assert status == 200
    game.command(token, uuid.uuid4().hex, "tutorial")
    state = game.state(token)["session"]
    status, _ = request(http_server, "/api/commands", {"request_id": uuid.uuid4().hex, "action": "explore", "params": {"session_id": state["id"], "revision": state["revision"]}}, token)
    assert status == 200
    state = game.state(token)["session"]
    request(http_server, "/api/commands", {"request_id": uuid.uuid4().hex, "action": "strike", "params": {"session_id": state["id"], "revision": state["revision"], "target": "invalid"}}, token)
    assert request(http_server, "/api/state")[0] == 401
    contents = Path(http_server.network_log.handlers[0].baseFilename).read_text()
    assert "ACTION_REQUESTED action=create" in contents
    assert "ACTION_REQUESTED action=explore" in contents
    assert "REQUEST_REJECTED reason=unauthorized" in contents
    assert "action=strike" not in contents
    assert token not in contents
    assert created["invite"] not in contents


def test_chat_global_presence_group_privacy_and_rate_limit(game):
    alice = player(game)
    bob = player(game, "Bob")
    outsider = player(game, "Eve")
    created = command(game, alice, "create")
    room = created["session"]["id"]
    command(game, bob, "join", invite=created["invite"])
    game.state(alice)
    game.state(bob)
    game.send_chat(alice, "group", "Bonjour <script>", room)
    state = game.state(bob)
    assert state["chat"]["group"][0]["message"] == "Bonjour <script>"
    assert len(state["chat"]["online"]) == 2
    assert game.state(outsider)["chat"]["group"] == []
    with pytest.raises(GameError):
        game.send_chat(outsider, "group", "intrus", room)
    with pytest.raises(GameError) as failure:
        game.send_chat(alice, "global", "spam")
    assert failure.value.code == "chat_rate_limit"
    game.clock.advance(2)
    game.send_chat(alice, "global", "Bienvenue")
    assert game.state(outsider)["chat"]["global"][0]["message"] == "Bienvenue"
    with pytest.raises(GameError):
        game.send_chat(alice, "global", "a" * 401)
    game.clock.advance(61)
    assert len(game.state(outsider)["chat"]["online"]) == 1


def test_prepared_views_remain_private_and_invalidate_on_action(game):
    import uuid
    alice, bob = player(game), player(game, "Bob")
    for token in (alice, bob):
        game.command(token, uuid.uuid4().hex, "tutorial")
    game.tick()
    first = game.state(alice, prepared=True)
    second = game.state(bob, prepared=True)
    assert first["session"]["me"] != second["session"]["me"]
    assert first["session"]["tutorial"]["players"][0]["name"] == "Alice"
    assert second["session"]["tutorial"]["players"][0]["name"] == "Bob"
    first["session"]["tutorial"]["players"][0]["name"] = "Corrupted"
    state = game.state(alice, prepared=True)["session"]
    assert state["tutorial"]["players"][0]["name"] == "Alice"
    game.command(alice, uuid.uuid4().hex, "explore", session_id=state["id"], revision=state["revision"])
    assert game.state(alice, prepared=True)["session"]["tutorial"]["battle"] is not None


def test_state_polling_does_not_write_disk_or_move_clock_backwards(game):
    token = player(game)
    game.state(token)
    before = game.db.total_changes
    game.clock.advance(1)
    later = game.state(token)["game_time"]
    for _ in range(30):
        game.state(token)
    assert game.db.total_changes == before
    game.clock.value = 0
    assert game.state(token)["game_time"] >= later


def test_http_reuses_connection_and_closes_rejected_post(http_server):
    import http.client
    connection = http.client.HTTPConnection("127.0.0.1", http_server.server_address[1], timeout=3)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Server-Timing")
        response.read()
        socket = connection.sock
        connection.request("GET", "/app.js")
        response = connection.getresponse()
        assert response.status == 200
        response.read()
        assert connection.sock is socket
        connection.request("POST", "/api/commands", body=b'{"unconsumed":true}', headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        assert response.status == 401
        assert response.getheader("Connection") == "close"
        response.read()
        assert connection.sock is None
    finally:
        connection.close()


def test_prepared_view_failure_does_not_stop_other_sessions(game, monkeypatch):
    import uuid
    from jeuxRPG.multiplayer import tutorial
    alice, bob = player(game), player(game, "Bob")
    for token in (alice, bob):
        game.command(token, uuid.uuid4().hex, "tutorial")
    alice_id = game.state(alice)["player"]["id"]
    original = tutorial.view
    def broken(party, me, now):
        if me == alice_id:
            raise RuntimeError("Fixture view failure")
        return original(party, me, now)
    monkeypatch.setattr(tutorial, "view", broken)
    game.tick()
    assert game.state(bob, prepared=True)["session"]["tutorial"]["players"][0]["name"] == "Bob"
    assert len(game._view_errors) == 1
    assert len(game._prepared_views) == 1


def test_command_queue_rolls_back_rejected_action_and_preserves_receipts(game, monkeypatch):
    import uuid
    from jeuxRPG.multiplayer.command_queue import CommandQueue
    token = player(game)
    dispatcher = CommandQueue(game)
    original = game._execute
    def rejected(actor, action, params, now):
        game.db.execute("UPDATE players SET name='Corrupted' WHERE id=?", (actor["id"],))
        raise GameError("fixture_rejection", "Rejected")
    try:
        monkeypatch.setattr(game, "_execute", rejected)
        with pytest.raises(GameError) as failure:
            dispatcher.execute(token, uuid.uuid4().hex, "create", {})
        assert failure.value.code == "fixture_rejection"
        assert game.state(token)["player"]["name"] == "Alice"
        monkeypatch.setattr(game, "_execute", original)
        request_id = uuid.uuid4().hex
        created = dispatcher.execute(token, request_id, "create", {})
        assert dispatcher.execute(token, request_id, "create", {}) == created
        assert game.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
        assert dispatcher.worker.is_alive()
    finally:
        dispatcher.close()


def test_compact_confirmation_skips_rendering_and_keeps_action_validation(game, monkeypatch):
    game.random = lambda: .5
    import uuid
    from jeuxRPG.multiplayer import tutorial
    token = player(game)
    state = game.command(token, uuid.uuid4().hex, "tutorial")["session"]
    original = tutorial.view
    def forbidden(*args):
        raise AssertionError("Confirmation must not render the entire state")
    monkeypatch.setattr(tutorial, "view", forbidden)
    result = game.command(token, uuid.uuid4().hex, "explore", _compact=True, session_id=state["id"], revision=state["revision"])
    assert result["session"]["acknowledged"]
    assert "tutorial" not in result["session"]
    monkeypatch.setattr(tutorial, "view", original)
    latest = game.state(token)["session"]
    assert latest["tutorial"]["battle"]
    with pytest.raises(GameError) as failure:
        game.command(token, uuid.uuid4().hex, "travel", _compact=True, session_id=latest["id"], revision=latest["revision"], destination="rosee")
    assert failure.value.code == "in_combat"
