import asyncio
import concurrent.futures
import json
import threading
from types import SimpleNamespace
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
        self.value += real_seconds * 20


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
    assert clock.now() == 3600
    assert clock.real_seconds(60) == 3


def test_two_players_share_health_and_cooldown(game):
    first, second, room = duel(game)
    before = next(p for p in room["players"] if p["id"] != room["me"])["hp"]
    result = command(game, first, "attack", session_id=room["id"], revision=room["revision"])["session"]
    other = game.state(second, room["id"])
    assert other["players"] == result["players"]
    assert next(p for p in other["players"] if p["id"] == other["me"])["hp"] < before
    me = next(p for p in result["players"] if p["id"] == result["me"])
    assert me["cooldown_real_seconds"] == 3
    game.clock.advance(2.99)
    with pytest.raises(GameError, match="disponible"):
        command(game, first, "attack", session_id=room["id"], revision=result["revision"])
    game.clock.advance(0.01)
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
    clock.advance(2)
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
    assert clock.now() == 3600


def test_restart_checkpoint_prevents_time_going_backwards():
    clock = GameClock(100, monotonic=lambda: 50, wall=lambda: 80, minimum_game=3600)
    assert clock.now() == 3600


def test_persisted_time_cannot_be_rewound(game):
    game.clock.advance(180)
    token = player(game)
    assert game.state(token)["game_time"] == 3600
    game.clock.value = 10
    assert game.state(token)["game_time"] == 3600


def test_ticker_expires_session_without_client_requests(game, http_server):
    token = player(game)
    room = command(game, token, "create")["session"]
    game.clock.advance(601)
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
def http_server(game):
    server = RPGServer(("127.0.0.1", 0), game)
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
