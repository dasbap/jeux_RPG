import sqlite3

from jeuxRPG.multiplayer.schema import current_version, initialize, validate_schema


def test_initialize_schema_is_versioned_and_idempotent():
    connection = sqlite3.connect(":memory:")
    try:
        assert initialize(connection) == 1
        assert current_version(connection) == 1
        assert validate_schema(connection) is True
        assert initialize(connection) == 1
        assert current_version(connection) == 1
    finally:
        connection.close()


def test_initialize_adopts_unversioned_legacy_database():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE players (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, scope TEXT NOT NULL, external_id TEXT, name TEXT NOT NULL, class_name TEXT NOT NULL, hp INTEGER NOT NULL, damage INTEGER NOT NULL, UNIQUE(scope, external_id))"
        )
        connection.commit()
        assert initialize(connection) == 1
        assert current_version(connection) == 1
        assert validate_schema(connection) is True
    finally:
        connection.close()
