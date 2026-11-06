import sqlite3
from copy import deepcopy

import pytest

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.realtime_store import TABLES
from scripts.database_admin import inspect

ENV = {"RPG_DATABASE_BACKEND": "d1", "RPG_D1_WORKER_URL": "https://example.workers.dev", "RPG_D1_SERVICE_TOKEN": "x" * 40}


@pytest.mark.parametrize("operation", ["connexion", "schema", "integrite"])
def test_d1_administration_is_read_only_without_turso(monkeypatch, operation):
    from jeuxRPG.multiplayer import turso

    data = {table: [] for table in TABLES}
    before = deepcopy(data)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Aucune écriture distante ni connexion Turso autorisée")

    monkeypatch.setattr(turso, "TursoConnection", forbidden)
    monkeypatch.setattr(D1Client, "load_snapshot", forbidden)
    monkeypatch.setattr(D1Client, "persist_checkpoint", forbidden)
    monkeypatch.setattr(D1Client, "health", lambda self: {"ok": True, "version": 3})
    monkeypatch.setattr(D1Client, "read_snapshot", lambda self: data)
    assert inspect(ENV, operation)["ok"]
    assert data == before


def test_legacy_administration_never_initializes_a_schema(monkeypatch):
    from test_serverless import Transport

    from jeuxRPG.multiplayer import turso

    transport = Transport()
    mutations = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE}
    transport.db.set_authorizer(lambda action, *_args: sqlite3.SQLITE_DENY if action in mutations else sqlite3.SQLITE_OK)
    monkeypatch.setattr(turso, "TursoConnection", lambda *_args: transport.db)
    assert inspect({"TURSO_DATABASE_URL": "https://fixture.invalid", "TURSO_AUTH_TOKEN": "fixture"}, "integrite")["ok"]
