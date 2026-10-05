import io
import json
import sqlite3
import uuid

import pytest

from jeuxRPG.multiplayer.serverless import Application, DatabaseLimiter, RemoteGameService
from jeuxRPG.multiplayer.service import GameError, GameService
from jeuxRPG.multiplayer.turso import TursoConnection, encode
from jeuxRPG.multiplayer.schema import initialize


def request(app, path, method="GET", body=None, token=None, **extra):
    raw = json.dumps(body).encode() if body is not None else b""
    env = {"PATH_INFO": path, "REQUEST_METHOD": method, "HTTP_HOST": "localhost", "REMOTE_ADDR": "127.0.0.1", "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(raw), "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)), **extra}
    if token:
        env["HTTP_AUTHORIZATION"] = "Bearer " + token
    response = {}
    def start(status, headers):
        response.update(status=int(status.split()[0]), headers=dict(headers))
    content = b"".join(app(env, start))
    response["body"] = json.loads(content) if response["headers"]["Content-Type"].startswith("application/json") else content
    return response


@pytest.fixture
def web(tmp_path):
    database = tmp_path / "web.db"
    app = Application(lambda: GameService(database), {"RPG_ADMIN_TOKEN": "a" * 40})
    return app, database


def test_admin_requires_separate_secret_and_never_discloses_hashes(web):
    app, _ = web
    player = request(app, "/api/register", "POST", {"name": "Alice", "class_name": "Knight"})["body"]
    assert request(app, "/api/admin/accounts")["status"] == 401
    assert request(app, "/api/admin/accounts", token=player["token"])["status"] == 401
    result = request(app, "/api/admin/accounts", token="a" * 40)
    assert result["status"] == 200
    assert result["body"]["accounts"][0]["name"] == "Alice"
    assert "token" not in json.dumps(result["body"])


def test_suspend_restore_rename_and_revoke_survive_new_instance(web):
    app, database = web
    player = request(app, "/api/register", "POST", {"name": "Alice", "class_name": "Knight"})["body"]
    identifier = request(app, "/api/state", token=player["token"])["body"]["player"]["id"]
    def action(operation, **params):
        return request(app, "/api/admin/accounts", "POST", {"player_id": identifier, "action": operation, **params}, "a" * 40)
    assert action("suspend")["status"] == 200
    assert request(app, "/api/state", token=player["token"])["status"] == 403
    assert action("restore")["status"] == 200
    assert request(app, "/api/state", token=player["token"])["status"] == 200
    assert action("rename", name="Bob")["status"] == 200
    assert request(app, "/api/state", token=player["token"])["body"]["player"]["name"] == "Bob"
    assert action("revoke")["status"] == 200
    assert request(app, "/api/state", token=player["token"])["status"] == 401
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM admin_audit").fetchone()[0] == 4
        assert db.execute("SELECT count(*) FROM players").fetchone()[0] == 1


def test_admin_origin_body_and_configuration_guards(web):
    app, _ = web
    assert request(app, "/api/admin/accounts", token="a" * 40, HTTP_ORIGIN="https://evil.test")["status"] == 403
    assert request(app, "/api/admin/accounts", token="a" * 40, HTTP_HOST="evil.test")["status"] == 403
    assert request(app, "/api/admin/accounts", "POST", {}, "a" * 40)["status"] == 400
    assert request(app, "/api/admin/accounts", "DELETE", token="a" * 40)["status"] == 405
    app.environment["RPG_ADMIN_TOKEN"] = ""
    assert request(app, "/api/admin/accounts", token="a" * 40)["status"] == 503


def test_admin_static_page_available_without_database():
    app = Application(environment={})
    assert request(app, "/admin")["status"] == 200
    assert request(app, "/api/classes")["status"] == 503


def test_vercel_hosts_and_https_origin_with_proxy_http(web):
    app, _ = web
    app.environment.update(VERCEL="1", VERCEL_URL="preview.vercel.app")
    result = request(app, "/api/classes", HTTP_HOST="preview.vercel.app", HTTP_ORIGIN="https://preview.vercel.app")
    assert result["status"] == 200
    assert request(app, "/admin", HTTP_HOST="unrelated.vercel.app")["status"] == 403


def test_database_rate_limit_is_shared_and_bounded(tmp_path):
    a, b = GameService(tmp_path / "limit.db"), GameService(tmp_path / "limit.db")
    try:
        assert DatabaseLimiter(a).accept(("admin", "peer"), 1)
        assert not DatabaseLimiter(b).accept(("admin", "peer"), 1)
        for _ in range(5):
            assert not DatabaseLimiter(b).accept(("admin", "peer"), 1)
        assert b.db.execute("SELECT count FROM request_limits").fetchone()[0] == 2
    finally:
        a.close(); b.close()


def remote_service(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    return RemoteGameService(connection=db, log_directory="-")


def test_chat_and_receipts_are_shared_across_instances(tmp_path):
    a = remote_service(tmp_path / "shared.db")
    first = a.register("Alice", "Knight")["token"]
    second = a.register("Bob", "Mage")["token"]
    a.state(second, chat_connection="stream-bob")
    a.send_chat(first, "global", "Bonjour", chat_connection="stream-alice")
    b = remote_service(tmp_path / "shared.db")
    try:
        assert b.state(second, chat_connection="stream-bob")["chat"]["global"][0]["message"] == "Bonjour"
        assert b.state(second, chat_connection="fresh-bob")["chat"]["global"] == []
        with pytest.raises(GameError) as error:
            b.send_chat(first, "global", "Encore", chat_connection="stream-alice")
        assert error.value.status == 429
        identifier = uuid.uuid4().hex
        once = a.command(first, identifier, "create")
        assert b.command(first, identifier, "create") == once
    finally:
        a.close(); b.close()


class Transport:
    def __init__(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.requests = []

    def __call__(self, payload):
        results = []
        open_stream = True
        for item in payload["requests"]:
            self.requests.append(item)
            if item["type"] == "close":
                open_stream = False
                results.append({"type": "ok", "response": {"type": "close"}})
                continue
            stmt = item["stmt"]
            values = [int(v["value"]) if v["type"] == "integer" else v.get("value") for v in stmt.get("args", [])]
            try:
                cur = self.db.execute(stmt["sql"], values)
                cols = [{"name": col[0]} for col in cur.description or []]
                result = {"cols": cols, "rows": [[encode(value) for value in row] for row in cur.fetchall()], "affected_row_count": max(0, cur.rowcount), "last_insert_rowid": None}
                results.append({"type": "ok", "response": {"result": result}})
            except sqlite3.Error:
                results.append({"type": "error", "error": {"code": "SQL_ERROR"}})
        return {"baton": "baton" if open_stream else None, "results": results}


def test_turso_migration_is_idempotent_and_rolls_back_on_error():
    transport = Transport()
    db = TursoConnection("libsql://test.turso.io", "test-token", transport=transport)
    initialize(db); initialize(db)
    assert db.execute("SELECT count(*) FROM players").fetchone()[0] == 0
    with pytest.raises(sqlite3.Error):
        db.executescript("CREATE TABLE doomed(id INTEGER); INVALID SQL;")
    assert not db.execute("SELECT name FROM sqlite_schema WHERE name='doomed'").fetchone()
    db.close()


def test_turso_unconfirmed_command_is_not_retried():
    calls = []
    def broken(payload):
        calls.append(payload)
        raise OSError()
    db = TursoConnection("libsql://test.turso.io", "test-token", transport=broken)
    with pytest.raises(sqlite3.OperationalError):
        db.execute("INSERT INTO players VALUES(1)")
    with pytest.raises(sqlite3.OperationalError):
        db.execute("INSERT INTO players VALUES(1)")
    assert len(calls) == 1


def test_game_service_uses_turso_protocol_and_keeps_receipts():
    transport = Transport()
    a = RemoteGameService(connection=TursoConnection("libsql://test.turso.io", "test-token", transport=transport), log_directory="-")
    token = a.register("Alice", "Knight")["token"]
    identifier = uuid.uuid4().hex
    once = a.command(token, identifier, "create")
    b = RemoteGameService(connection=TursoConnection("libsql://test.turso.io", "test-token", transport=transport), log_directory="-")
    try:
        assert b.command(token, identifier, "create") == once
        assert b.state(token)["player"]["name"] == "Alice"
    finally:
        a.close(); b.close()
