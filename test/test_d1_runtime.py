"""Independent Vercel instances must share committed gameplay, never RAM state."""

import asyncio
import sqlite3
import subprocess
import sys
import threading
import uuid

import pytest
from fastapi.testclient import TestClient

from jeuxRPG.multiplayer.d1_client import (
    D1StorageError,
    RuntimeSnapshot,
    SnapshotConflict,
)
from jeuxRPG.multiplayer.d1_runtime import RUNTIME_KEYS, D1Coordinator
from jeuxRPG.multiplayer.realtime import create_app
from jeuxRPG.multiplayer.schema import initialize

ENV = {
    "VERCEL": "1",
    "VERCEL_URL": "localhost",
    "RPG_RUNTIME_MODE": "d1",
    "RPG_DATABASE_BACKEND": "d1",
    "RPG_D1_WORKER_URL": "https://fixture.invalid",
    "RPG_D1_SERVICE_TOKEN": "d" * 40,
    "RPG_ADMIN_TOKEN": "a" * 40,
}


class Database:
    def __init__(self):
        self.db = sqlite3.connect(
            ":memory:", check_same_thread=False, isolation_level=None
        )
        self.db.row_factory = sqlite3.Row
        initialize(self.db)
        self.lock = threading.Lock()
        self.conflicts = 0
        self.unavailable = self.lose_ack = False

    def health(self):
        if self.unavailable:
            raise D1StorageError("fixture outage")
        return {"ok": True, "runtime_transactions": 1}

    def runtime_snapshot(self):
        self.health()
        with self.lock:
            data = {
                table: [dict(row) for row in self.db.execute("SELECT * FROM " + table)]
                for table in RUNTIME_KEYS
            }
            sequences = [
                dict(row)
                for row in self.db.execute("SELECT name,seq FROM sqlite_sequence")
            ]
            return RuntimeSnapshot(data, sequences)

    def commit_runtime(self, fence, batch):
        self.health()
        with self.lock:
            row = self.db.execute(
                "SELECT value FROM meta WHERE key='runtime_fence'"
            ).fetchone()
            if int(row[0] if row else 0) != fence:
                self.conflicts += 1
                raise SnapshotConflict("fixture conflict")
            self.db.execute("BEGIN")
            self.db.execute("PRAGMA defer_foreign_keys=ON")
            try:
                for (table, key), row in batch.items():
                    if table == "meta" and key == ("runtime_fence",):
                        continue
                    keys = RUNTIME_KEYS[table]
                    if row is None:
                        self.db.execute(
                            "DELETE FROM "
                            + table
                            + " WHERE "
                            + " AND ".join(k + "=?" for k in keys),
                            key,
                        )
                    else:
                        columns = list(row)
                        updates = ",".join(
                            k + "=excluded." + k for k in columns if k not in keys
                        )
                        suffix = (
                            " DO UPDATE SET " + updates if updates else " DO NOTHING"
                        )
                        self.db.execute(
                            "INSERT INTO "
                            + table
                            + " ("
                            + ",".join(columns)
                            + ") VALUES ("
                            + ",".join("?" for _ in columns)
                            + ") ON CONFLICT("
                            + ",".join(keys)
                            + ")"
                            + suffix,
                            tuple(row.values()),
                        )
                self.db.execute(
                    "INSERT INTO meta VALUES('runtime_fence',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(fence + 1),),
                )
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            if self.lose_ack:
                self.lose_ack = False
                raise D1StorageError("commit ack lost")


def message(path, body=None, token=None):
    return {
        "path": path,
        "method": "POST" if body is not None else "GET",
        "body": body,
        "host": "localhost",
        "scheme": "https",
        "peer": "127.0.0.1",
        "headers": {"authorization": "Bearer " + token} if token else {},
    }


async def character(database, name="Alice", start=True):
    async def cold(path, body=None, token=None):
        return await D1Coordinator(ENV, database).rpc(message(path, body, token))

    result = await cold(
        "/api/account/signup", {"username": name, "password": "password-123456789"}
    )
    assert result["status"] == 201, result
    token = result["body"]["token"]
    result = await cold(
        "/api/account/character",
        {"action": "create", "name": name, "class_name": "Knight"},
        token,
    )
    assert result["status"] == 200, result
    if not start:
        return token, None
    result = await cold(
        "/api/commands",
        {"request_id": uuid.uuid4().hex, "action": "tutorial", "params": {}},
        token,
    )
    assert result["status"] == 200, result
    return token, result["body"]["session"]["id"]


def test_cold_instances_resume_the_same_adventure_without_redis():
    database = Database()

    async def scenario():
        token, session_id = await character(database)
        runtime = D1Coordinator({**ENV, "REDIS_URL": "redis://forbidden"}, database)
        result = await runtime.rpc(message("/api/state", token=token))
        assert result["status"] == 200, result
        assert result["body"]["session"]["id"] == session_id
        assert result["headers"]["X-RPG-Runtime"] == "d1-transaction"
        assert result["headers"]["X-RPG-Save-Pending"] == "0"
        assert "REDIS_URL" not in runtime.environment

    asyncio.run(scenario())


def test_concurrent_instances_keep_both_accounts_and_retry_conflicts():
    database = Database()

    async def scenario():
        first, second = await asyncio.gather(
            character(database, "Alice"), character(database, "Bob")
        )
        assert first[1] != second[1]
        assert len(database.runtime_snapshot()["accounts"]) == 2
        assert database.conflicts > 0

    asyncio.run(scenario())


def test_failed_commit_never_returns_success_and_replay_does_not_duplicate():
    database = Database()

    async def scenario():
        token, _ = await character(database, start=False)
        command = message(
            "/api/commands",
            {"request_id": "same-command", "action": "tutorial", "params": {}},
            token,
        )
        database.lose_ack = True
        with pytest.raises(RuntimeError, match="non confirmee"):
            await D1Coordinator(ENV, database).rpc(command)
        result = await D1Coordinator(ENV, database).rpc(command)
        assert result["status"] == 200
        assert result["body"]["session"]["tutorial"]
        assert len(database.runtime_snapshot()["tutorials"]) == 1
        receipts = database.runtime_snapshot()["receipts"]
        assert sum(row["request_id"] == "same-command" for row in receipts) == 1

    asyncio.run(scenario())


def test_readiness_reports_d1_outage_and_static_interface_stays_available():
    database = Database()
    app = create_app(ENV, D1Coordinator(ENV, database))
    with TestClient(app, base_url="https://localhost") as client:
        assert client.get("/ready").status_code == 200
        assert client.get("/health").json()["runtime"] == "d1-transaction"
        database.unavailable = True
        assert client.get("/ready").status_code == 503
        assert client.get("/").status_code == 200


def test_vercel_app_and_build_check_import_without_redis_installed():
    script = """
import builtins
original = builtins.__import__
def guard(name, *args, **kwargs):
    if name == "redis" or name.startswith("redis."):
        raise AssertionError("Redis import forbidden")
    return original(name, *args, **kwargs)
builtins.__import__ = guard
from jeuxRPG.multiplayer.realtime import create_app
from scripts.verify_runtime_storage import failure_code
environment = ENV_PLACEHOLDER
app = create_app(environment)
assert app.state.coordinator.environment["RPG_RUNTIME_MODE"] == "d1"
assert failure_code(ValueError()) == "runtime_storage"
""".replace("ENV_PLACEHOLDER", repr(ENV))
    subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )


def test_chat_and_stream_cursors_survive_changing_instances():
    database = Database()

    async def cold(path, body=None, token=None, stream="browser-stream"):
        request = message(path, body, token)
        request["headers"]["X-RPG-Chat-Connection"] = stream
        return await D1Coordinator(ENV, database).rpc(request)

    async def scenario():
        alice, _ = await character(database, "Alice")
        bob, _ = await character(database, "Bob")
        assert (await cold("/api/state", token=bob))["status"] == 200
        sent = await cold(
            "/api/chat",
            {"channel": "global", "message": "Bonjour", "session_id": None},
            alice,
        )
        assert sent["status"] == 200, sent
        state = await cold("/api/state", token=bob)
        assert state["body"]["chat"]["global"][0]["message"] == "Bonjour"
        assert len(database.runtime_snapshot()["chat"]) == 1
        # Reconstructing a store after message expiry must preserve AUTOINCREMENT.
        with database.lock:
            database.db.execute("DELETE FROM chat")
            database.db.execute("UPDATE sqlite_sequence SET seq=100 WHERE name='chat'")
            database.db.execute("DELETE FROM request_limits")
        sent = await cold(
            "/api/chat",
            {"channel": "global", "message": "Suite", "session_id": None},
            bob,
        )
        assert sent["status"] == 200, sent
        assert database.runtime_snapshot()["chat"][0]["id"] == 101

    asyncio.run(scenario())
