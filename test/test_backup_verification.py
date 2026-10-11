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
