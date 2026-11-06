import io
import json
import sqlite3
import urllib.error
from pathlib import Path

import pytest

from jeuxRPG.multiplayer.d1_client import D1Client, D1StorageError

ENV = {
    "RPG_D1_WORKER_URL": "https://example.workers.dev/",
    "RPG_D1_SERVICE_TOKEN": "x" * 40,
}


def test_client_sends_authenticated_checkpoint(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, *_):
            return b'{"ok":true}'

    def fake(request, timeout):
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake)
    D1Client(ENV).persist_checkpoint(
        42, {
            ("players", ("alice",)): {"id": "alice", "name": "Alice"},
            ("meta", ("runtime_fence",)): {"key": "runtime_fence", "value": "41"},
        }
    )
    request, timeout = calls[0]
    assert timeout == 30
    assert request.get_header("Authorization") == "Bearer " + "x" * 40
    assert json.loads(request.data) == {
        "operation": "persist_checkpoint",
        "fence": 42,
        "changes": [
            {
                "table": "players",
                "key": ["alice"],
                "row": {"id": "alice", "name": "Alice"},
            }
        ],
    }


def test_stale_writer_is_rejected(monkeypatch):
    def fake(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            ENV["RPG_D1_WORKER_URL"],
            409,
            "conflict",
            {},
            io.BytesIO(b'{"error":"stale_runtime_fence"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(RuntimeError, match="Moteur remplacé"):
        D1Client(ENV).persist_checkpoint(12, {})


def test_malformed_response_is_rejected(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, *_):
            return b'{"ok":false}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(D1StorageError):
        D1Client(ENV).persist_checkpoint(1, {})


def test_sqlite_fence_guard_is_atomic():
    db = sqlite3.connect(":memory:")
    db.executescript(
        "CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);"
        "CREATE TABLE progress(id TEXT PRIMARY KEY,value TEXT NOT NULL);"
    )
    sql = (
        Path(__file__).resolve().parents[1]
        / "cloudflare"
        / "0004_fence_guard.sql"
    ).read_text()
    db.executescript(sql)
    db.execute("INSERT INTO meta VALUES('runtime_fence','20')")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError), db:
        db.execute(
            "INSERT INTO meta VALUES('runtime_fence','19') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        )
        db.execute("INSERT INTO progress VALUES('player','unwanted')")
    assert db.execute("SELECT count(*) FROM progress").fetchone()[0] == 0
    assert db.execute("SELECT value FROM meta").fetchone()[0] == "20"
    with db:
        db.execute(
            "INSERT INTO meta VALUES('runtime_fence','21') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        )
        db.execute("INSERT INTO progress VALUES('player','saved')")
    assert db.execute("SELECT value FROM progress").fetchone()[0] == "saved"


@pytest.mark.parametrize("data", [{}, {"players": []}, {"players": "invalid"}])
def test_partial_snapshot_is_rejected(monkeypatch, data):
    monkeypatch.setattr(D1Client, "request", lambda *_args, **_kwargs: {"data": data})
    with pytest.raises(D1StorageError, match="Snapshot"):
        D1Client(ENV).load_snapshot(20)


def test_complete_snapshot_is_accepted(monkeypatch):
    from jeuxRPG.multiplayer.realtime_store import TABLES

    data = dict.fromkeys(TABLES, [])
    monkeypatch.setattr(D1Client, "request", lambda *_args, **_kwargs: {"data": data})
    assert D1Client(ENV).load_snapshot(20) == data


@pytest.mark.parametrize("body", [b"null", b"[]", b'"error"', b"invalid"])
def test_malformed_conflict_response_is_a_storage_error(monkeypatch, body):
    def fake(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            ENV["RPG_D1_WORKER_URL"], 409, "conflict", {}, io.BytesIO(body)
        )

    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(D1StorageError):
        D1Client(ENV).persist_checkpoint(12, {})
