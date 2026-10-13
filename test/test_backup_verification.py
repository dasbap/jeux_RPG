from jeuxRPG.multiplayer.service import GameService
from scripts.verify_backup import verify_backup


def test_backup_reopens_copy_without_modifying_source(tmp_path):
    database = tmp_path / 'original.sqlite3'
    service = GameService(database, log_directory='-')
    player = service.register('Restauration', 'Knight')
    service.command(player['token'], 'restore-command', 'tutorial')
    service.close()
    original = database.read_bytes()
    report = verify_backup(database, tmp_path)
    assert report['integrity'] == 'ok'
    assert report['engine_reopened'] and report['source_unchanged']
    assert report['rows']['players'] == 1
    assert report['rows']['tutorials'] == 1
    assert database.read_bytes() == original
    resumed = GameService(database, log_directory='-')
    try:
        assert resumed.state(player['token'])['player']['name'] == 'Restauration'
    finally:
        resumed.close()


def test_turso_export_restores_consistent_private_copy(tmp_path):
    import os
    from scripts.export_turso_backup import export_backup
    from jeuxRPG.multiplayer.schema import initialize
    from jeuxRPG.multiplayer.turso import TursoConnection
    from test_serverless import Transport
    transport = Transport()
    remote = TursoConnection('https://test.invalid', 'fixture-only', transport=transport)
    initialize(remote)
    remote.execute("INSERT INTO players VALUES('fixture','hash','local',NULL,'Backup','Knight',100,10)")
    remote.execute("INSERT INTO chat VALUES(500,'world',NULL,'fixture','Backup','temporary',1)")
    remote.execute("DELETE FROM chat WHERE id=500")
    destination = tmp_path / 'export.sqlite3'
    report = export_backup(remote, destination)
    assert report['source_unchanged'] and report['engine_reopened']
    assert report['rows']['players'] == 1
    import sqlite3
    with sqlite3.connect(destination) as copy:
        assert copy.execute("SELECT seq FROM sqlite_sequence WHERE name='chat'").fetchone()[0] == 500
        copy.execute("INSERT INTO chat(scope,player_id,name,message,sent) VALUES('world','fixture','Backup','resumed',2)")
        assert copy.execute('SELECT id FROM chat').fetchone()[0] == 501
    assert not remote.in_transaction
    assert os.stat(destination).st_mode & 0o777 == 0o600
    assert transport.db.execute('SELECT name FROM players').fetchone()[0] == 'Backup'
    remote.close()


def test_export_failure_removes_partial_copy_and_rolls_back(tmp_path):
    import pytest
    from scripts.export_turso_backup import export_backup
    class BrokenSource:
        in_transaction = False
        def execute(self, sql):
            if sql == 'BEGIN':
                self.in_transaction = True
                return []
            if sql == 'ROLLBACK':
                self.in_transaction = False
                return []
            raise OSError('isolated failure')
    source = BrokenSource()
    destination = tmp_path / 'incomplete.sqlite3'
    with pytest.raises(OSError):
        export_backup(source, destination)
    assert not source.in_transaction and not destination.exists()


def test_export_removes_private_partial_file_even_if_rollback_fails(tmp_path):
    import pytest
    from scripts.export_turso_backup import export_backup
    class DisconnectedSource:
        in_transaction = False
        def execute(self, sql):
            if sql == 'BEGIN':
                self.in_transaction = True
                return []
            raise OSError('isolated disconnected source')
    destination = tmp_path / 'private-partial.sqlite3'
    with pytest.raises(OSError):
        export_backup(DisconnectedSource(), destination)
    assert not destination.exists()
