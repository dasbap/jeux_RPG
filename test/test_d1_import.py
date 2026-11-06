import sqlite3

import pytest

from jeuxRPG.multiplayer.realtime_store import TABLES
from jeuxRPG.multiplayer.schema import initialize
from jeuxRPG.multiplayer.service import GameService
from scripts.prepare_d1_import import generate_import


def backup(tmp_path):
    path = tmp_path / "sauvegarde #1.sqlite3"
    service = GameService(path, log_directory="-")
    player = service.register("L'Éclaireur", "Knight")
    service.command(player["token"], "migration-tutorial", "tutorial")
    service.close()
    return path, player


def test_import_preserves_rows_and_resumes_game(tmp_path):
    source, player = backup(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE sqlite_sequence SET seq=900 WHERE name='events'")
    before = source.read_bytes()
    sql = tmp_path / "d1-private-import.sql"
    report = generate_import(source, sql)
    target = tmp_path / "d1.sqlite3"
    with sqlite3.connect(target, isolation_level=None) as db:
        initialize(db)
        db.execute("PRAGMA foreign_keys=ON")
        # D1 executes imports inside a transaction.
        db.executescript("BEGIN;\n" + sql.read_text(encoding="utf-8") + "\nCOMMIT;")
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT seq FROM sqlite_sequence WHERE name='events'").fetchone()[0] == 900
        with sqlite3.connect(source) as original:
            for table in TABLES:
                assert db.execute(f"SELECT * FROM {table}").fetchall() == original.execute(
                    f"SELECT * FROM {table}"
                ).fetchall()
    resumed = GameService(target, log_directory="-")
    try:
        assert resumed.state(player["token"])["player"]["name"] == "L'Éclaireur"
    finally:
        resumed.close()
    assert source.read_bytes() == before
    assert report["rows"]["players"] == 1
    assert report["rows"]["tutorials"] == 1
    with pytest.raises(FileExistsError):
        generate_import(source, sql)
    with pytest.raises(ValueError):
        generate_import(source, source)


@pytest.mark.parametrize("version", [0, 2, 999, None])
def test_import_rejects_incompatible_schema_before_creating_output(tmp_path, version):
    source, _ = backup(tmp_path)
    with sqlite3.connect(source) as db:
        if version is None:
            db.execute("DROP TABLE schema_version")
        else:
            db.execute("UPDATE schema_version SET version=?", (version,))
    sql = tmp_path / "d1-private-import.sql"
    with pytest.raises(RuntimeError, match="schéma"):
        generate_import(source, sql)
    assert not sql.exists()


def test_import_rejects_broken_foreign_keys(tmp_path):
    source, _ = backup(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("INSERT INTO account_status VALUES('missing-player',0)")
    sql = tmp_path / "d1-private-import.sql"
    with pytest.raises(RuntimeError, match="Relations invalides"):
        generate_import(source, sql)
    assert not sql.exists()


def test_remote_import_comparison_does_not_modify_source_or_claim_fence(monkeypatch, tmp_path):
    from jeuxRPG.multiplayer.d1_client import D1Client
    from scripts.verify_d1_import import verify

    source, _ = backup(tmp_path)
    before = source.read_bytes()
    with sqlite3.connect(source) as db:
        db.row_factory = sqlite3.Row
        data = {table: [dict(row) for row in db.execute(f"SELECT * FROM {table}")] for table in TABLES}
        sequences = [dict(row) for row in db.execute("SELECT name,seq FROM sqlite_sequence")]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Le contrôle d'import ne doit pas prendre le contrôle du moteur")

    monkeypatch.setattr(D1Client, "load_snapshot", forbidden)
    monkeypatch.setattr(D1Client, "persist_checkpoint", forbidden)
    monkeypatch.setattr(D1Client, "health", lambda self: {})
    monkeypatch.setattr(D1Client, "backup_snapshot", lambda self: (data, sequences))
    env = {"RPG_DATABASE_BACKEND": "d1", "RPG_D1_WORKER_URL": "https://example.workers.dev", "RPG_D1_SERVICE_TOKEN": "x" * 40}
    assert verify(source, env)["tables_match"]
    assert source.read_bytes() == before
    data["players"][0]["name"] = "modified"
    with pytest.raises(RuntimeError, match="players"):
        verify(source, env)
