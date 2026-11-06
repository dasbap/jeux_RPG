import sqlite3
from pathlib import Path

import pytest
from dotenv import dotenv_values

from jeuxRPG.multiplayer.storage_configuration import database_backend, runtime_prefix
from scripts.check_vercel import check
from scripts.prepare_d1_schema import schema_sql
from scripts.prepare_vercel_environment import prepare

ENV = {
    "RPG_DATABASE_BACKEND": "d1",
    "RPG_D1_WORKER_URL": "https://preview.example.workers.dev/",
    "RPG_D1_SERVICE_TOKEN": "x" * 40,
    "RPG_ADMIN_TOKEN": "a" * 40,
    "REDIS_URL": "redis://localhost",
}


def test_d1_build_has_no_turso_secret_dependency(tmp_path):
    path = tmp_path / "preview.env"
    path.write_text("TURSO_DATABASE_URL='old'\nTURSO_AUTH_TOKEN='old'\n")
    prepare(path, ENV)
    result = dotenv_values(path)
    assert result["RPG_DATABASE_BACKEND"] == "d1"
    assert result["RPG_D1_SERVICE_TOKEN"] == ENV["RPG_D1_SERVICE_TOKEN"]
    assert not any(key.startswith("TURSO_") for key in result)
    assert check(Path(__file__).resolve().parents[1], ENV) == []


def test_missing_d1_credentials_cannot_fall_back_to_turso(tmp_path):
    path = tmp_path / "preview.env"
    path.write_text("TURSO_DATABASE_URL='old'\nTURSO_AUTH_TOKEN='old'\n")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="RPG_D1_WORKER_URL"):
        prepare(path, {"RPG_DATABASE_BACKEND": "d1"})
    assert path.read_bytes() == before


def test_d1_preview_and_production_do_not_share_a_redis_owner():
    production = {**ENV, "RPG_D1_WORKER_URL": "https://production.example.workers.dev"}
    assert runtime_prefix(ENV) != runtime_prefix(production)
    assert runtime_prefix(ENV) != runtime_prefix({})
    assert runtime_prefix(ENV) == runtime_prefix({**ENV, "RPG_D1_WORKER_URL": ENV["RPG_D1_WORKER_URL"].rstrip("/")})


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError, match="RPG_DATABASE_BACKEND"):
        database_backend({"RPG_DATABASE_BACKEND": "dl"})


def test_generated_schema_has_fence_guards_and_current_version():
    with sqlite3.connect(":memory:") as db:
        db.executescript(schema_sql())
        assert db.execute("SELECT version FROM schema_version").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0] == 2


def test_d1_outage_never_connects_to_turso(monkeypatch):
    from jeuxRPG.multiplayer import realtime_store
    from jeuxRPG.multiplayer.d1_client import D1Client, D1StorageError

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Connexion Turso interdite en mode D1")

    def unavailable(*_args, **_kwargs):
        raise D1StorageError("D1 indisponible")

    monkeypatch.setattr(realtime_store, "TursoConnection", forbidden)
    monkeypatch.setattr(D1Client, "health", unavailable)
    with pytest.raises(D1StorageError):
        realtime_store.RuntimeStore.load(ENV, 12)
    store = realtime_store.RuntimeStore(ENV)
    try:
        monkeypatch.setattr(D1Client, "persist_checkpoint", unavailable)
        with pytest.raises(D1StorageError):
            store.persist(12, {})
    finally:
        store.close()


def test_legacy_wsgi_cannot_open_turso_when_d1_is_selected(monkeypatch):
    from jeuxRPG.multiplayer import serverless

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Connexion Turso interdite en mode D1")

    monkeypatch.setattr(serverless, "TursoConnection", forbidden)
    application = serverless.Application(environment={"RPG_DATABASE_BACKEND": "d1"})
    with pytest.raises(sqlite3.OperationalError, match="ASGI"):
        application.service()
