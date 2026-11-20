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
