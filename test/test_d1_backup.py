import sqlite3
from contextlib import closing

import pytest

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.service import GameService
from scripts.export_database_backup import export_backup


def test_d1_backup_preserves_game_and_sequences_without_turso(monkeypatch, tmp_path):
    from jeuxRPG.multiplayer import turso

    def forbid(*_args, **_kwargs):
        raise AssertionError("Aucun accès Turso en mode D1")

    monkeypatch.setattr(turso, "TursoConnection", forbid)
    store = RuntimeStore({})
    player = store.service.register("D1Backup", "Knight")
    store.service.command(player["token"], "backup-tutorial", "tutorial")
    snapshot = {table: store.rows(table) for table in store.durable}
    store.close()
    sequences = [{"name": "events", "seq": 900}]
    monkeypatch.setattr(D1Client, "health", lambda self: {"ok": True})
    monkeypatch.setattr(D1Client, "backup_snapshot", lambda self: (snapshot, sequences))
    env = {"RPG_DATABASE_BACKEND": "d1", "RPG_D1_WORKER_URL": "https://example.workers.dev", "RPG_D1_SERVICE_TOKEN": "x" * 40}
    destination = tmp_path / "backup.sqlite3"
    report = export_backup(env, destination)
    assert report["backend"] == "d1" and report["engine_reopened"]
    with closing(sqlite3.connect(destination)) as db:
        assert db.execute("SELECT seq FROM sqlite_sequence WHERE name='events'").fetchone()[0] == 900
    resumed = GameService(destination, log_directory="-")
    try:
        assert resumed.state(player["token"])["player"]["name"] == "D1Backup"
    finally:
        resumed.close()
    with pytest.raises(FileExistsError):
        export_backup(env, destination)


def test_d1_backup_removes_partial_output_on_invalid_columns(monkeypatch, tmp_path):
    from jeuxRPG.multiplayer.realtime_store import TABLES

    data = {table: [] for table in TABLES}
    data["players"] = [{"id": "p", "unknown_column": "invalid"}]
    monkeypatch.setattr(D1Client, "health", lambda self: {})
    monkeypatch.setattr(D1Client, "backup_snapshot", lambda self: (data, []))
    env = {"RPG_DATABASE_BACKEND": "d1", "RPG_D1_WORKER_URL": "https://example.workers.dev", "RPG_D1_SERVICE_TOKEN": "x" * 40}
    destination = tmp_path / "backup.sqlite3"
    with pytest.raises(ValueError, match="Colonnes"):
        export_backup(env, destination)
    assert not destination.exists()
