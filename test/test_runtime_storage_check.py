import pytest
from redis.exceptions import (
    AuthenticationError,
    ConnectionError,
    ResponseError,
    TimeoutError,
)

from scripts.verify_runtime_storage import failure_code


@pytest.mark.parametrize("error, expected", [
    (AuthenticationError("secret-token"), "redis_authentication"),
    (TimeoutError("redis://secret-host"), "redis_timeout"),
    (ConnectionError("secret-host"), "redis_connection"),
    (ResponseError("max daily request limit exceeded secret-token"), "redis_quota"),
    (ResponseError("secret-token"), "redis_command"),
    (ValueError("secret-player-data"), "runtime_storage"),
])
def test_storage_failures_do_not_disclose_connection_or_player_data(error, expected):
    assert failure_code(error) == expected


@pytest.mark.parametrize("allow, error, expected", [
    ("1", ResponseError("monthly quota exceeded"), "solo"),
    ("0", ResponseError("monthly quota exceeded"), None),
    ("1", AuthenticationError("invalid credentials"), None),
    ("1", ConnectionError("unreachable"), None),
])
def test_solo_publication_only_accepts_known_quota_failure(monkeypatch, allow, error, expected):
    from unittest.mock import Mock

    from scripts import verify_runtime_storage as storage

    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.ping.side_effect = error
    from redis import Redis

    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: client)
    store = Mock()
    load = Mock(return_value=store)
    monkeypatch.setattr(storage.RuntimeStore, "load", load)
    environment = {"REDIS_URL": "redis://localhost", "RPG_ALLOW_SOLO_RELEASE": allow}
    if expected:
        assert storage.verify(environment) == expected
        load.assert_called_once_with(environment)
        store.close.assert_called_once()
    else:
        with pytest.raises(type(error)):
            storage.verify(environment)
        load.assert_not_called()


def test_d1_worker_must_support_transactions_before_snapshot(monkeypatch, capsys):
    from unittest.mock import Mock

    from scripts import verify_runtime_storage as storage

    client = Mock()
    client.health.return_value = {"ok": True}
    monkeypatch.setattr(storage, "D1Client", lambda _: client)
    monkeypatch.setenv("RPG_RUNTIME_MODE", "d1")
    assert storage.main() == 1
    output = capsys.readouterr().out
    assert "d1_worker_upgrade_required" in output
    assert "cloudflare/d1-worker.mjs" in output
    client.runtime_snapshot.assert_not_called()
    client.health.return_value["runtime_transactions"] = 1
    assert storage.verify({"RPG_RUNTIME_MODE": "d1"}) == "online"
    client.runtime_snapshot.assert_called_once_with()


def test_d1_snapshot_failure_prevents_release_without_disclosing_details(monkeypatch, capsys):
    from unittest.mock import Mock

    from jeuxRPG.multiplayer.d1_client import D1StorageError
    from scripts import verify_runtime_storage as storage

    client = Mock()
    client.health.return_value = {"ok": True, "runtime_transactions": 1}
    client.runtime_snapshot.side_effect = D1StorageError("secret-player-data")
    monkeypatch.setattr(storage, "D1Client", lambda _: client)
    monkeypatch.setenv("RPG_RUNTIME_MODE", "d1")
    assert storage.main() == 1
    output = capsys.readouterr().out
    assert "d1_storage" in output
    assert "secret-player-data" not in output
