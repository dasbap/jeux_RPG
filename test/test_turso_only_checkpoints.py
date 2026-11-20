
import pytest
from test_realtime import ENV, message
from test_serverless import Transport

from jeuxRPG.multiplayer import realtime_store
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.schema import initialize
from jeuxRPG.multiplayer.turso import TursoConnection


def test_new_owner_claims_turso_generation_before_loading_and_refuses_old_writer(monkeypatch):
    transport = Transport()
    initialize(transport.db)
    monkeypatch.setattr(realtime_store, "TursoConnection", lambda *args: TursoConnection("https://test.invalid", "fixture-token", transport=transport))
    environment = {**ENV, "TURSO_DATABASE_URL": "https://test.invalid", "TURSO_AUTH_TOKEN": "fixture-token"}
    previous = RuntimeStore(environment)
    current = None
    try:
        previous.request(message("/api/register", {"name": "Alice", "class_name": "Knight"}))
        batch = previous.pending_batch()
        previous.persist(10, batch)
        current = RuntimeStore.load(environment, 20)
        assert current.db.execute("SELECT name FROM players").fetchone()[0] == "Alice"
        with pytest.raises(RuntimeError, match="remplacé"):
            previous.persist(10, batch)
        with pytest.raises(RuntimeError, match="remplacé"):
            RuntimeStore.load(environment, 19)
        assert not transport.db.in_transaction
        assert transport.db.execute("SELECT value FROM meta WHERE key='runtime_fence'").fetchone()[0] == "20"
    finally:
        previous.close()
        if current:
            current.close()
