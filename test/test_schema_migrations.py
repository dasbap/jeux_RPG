import sqlite3

from jeuxRPG.multiplayer.schema import MIGRATIONS, current_version, initialize, validate_schema


def test_initialize_schema_is_versioned_and_idempotent():
    connection = sqlite3.connect(":memory:")
    try:
        assert initialize(connection) == 2
        assert current_version(connection) == 2
        assert validate_schema(connection) is True
        assert initialize(connection) == 2
        assert current_version(connection) == 2
    finally:
        connection.close()


def test_initialize_adopts_unversioned_legacy_database():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE players (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, scope TEXT NOT NULL, external_id TEXT, name TEXT NOT NULL, class_name TEXT NOT NULL, hp INTEGER NOT NULL, damage INTEGER NOT NULL, UNIQUE(scope, external_id))"
        )
        connection.commit()
        assert initialize(connection) == 2
        assert current_version(connection) == 2
        assert validate_schema(connection) is True
    finally:
        connection.close()


def test_receipt_migration_preserves_legacy_response_and_is_idempotent():
    connection = sqlite3.connect(':memory:')
    connection.executescript((MIGRATIONS / '0001_initial.sql').read_text())
    current_version(connection)
    connection.execute('UPDATE schema_version SET version=1')
    connection.execute("INSERT INTO players VALUES ('p','token','local',NULL,'Joueur','Knight',100,10)")
    connection.execute("INSERT INTO receipts VALUES ('p','r','fingerprint','{}')")
    connection.commit()
    assert initialize(connection) == 2
    assert connection.execute('SELECT response FROM receipts').fetchone()[0] == '{}'
    expiry = connection.execute('SELECT expires FROM receipt_expiry').fetchone()[0]
    assert initialize(connection) == 2
    assert connection.execute('SELECT expires FROM receipt_expiry').fetchone()[0] == expiry
    connection.close()
