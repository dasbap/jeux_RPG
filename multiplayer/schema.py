SCHEMA = """
            CREATE TABLE IF NOT EXISTS presence (player_id TEXT PRIMARY KEY, seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, session_id TEXT, player_id TEXT NOT NULL, name TEXT NOT NULL, message TEXT NOT NULL, sent REAL NOT NULL);

            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
                scope TEXT NOT NULL, external_id TEXT, name TEXT NOT NULL,
                class_name TEXT NOT NULL, hp INTEGER NOT NULL, damage INTEGER NOT NULL,
                UNIQUE(scope, external_id)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, owner TEXT NOT NULL REFERENCES players(id),
                invite_hash TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
                revision INTEGER NOT NULL, deadline REAL NOT NULL, winner TEXT,
                created REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS members (
                session_id TEXT NOT NULL REFERENCES sessions(id),
                player_id TEXT NOT NULL REFERENCES players(id), hp INTEGER NOT NULL,
                ready_at REAL NOT NULL DEFAULT 0, PRIMARY KEY(session_id, player_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id),
                game_time REAL NOT NULL, message TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts (
                player_id TEXT NOT NULL REFERENCES players(id), request_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, response TEXT NOT NULL,
                PRIMARY KEY(player_id, request_id)
            );
            CREATE INDEX IF NOT EXISTS member_player ON members(player_id);
            CREATE INDEX IF NOT EXISTS session_events ON events(session_id, id);
            CREATE TABLE IF NOT EXISTS tutorials (
                session_id TEXT PRIMARY KEY REFERENCES sessions(id), data TEXT NOT NULL
            );

CREATE TABLE IF NOT EXISTS account_status (player_id TEXT PRIMARY KEY REFERENCES players(id), suspended INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS admin_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT NOT NULL REFERENCES players(id), action TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS request_limits (key TEXT PRIMARY KEY, window REAL NOT NULL, count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS chat_streams (player_id TEXT NOT NULL REFERENCES players(id), connection TEXT NOT NULL, seen REAL NOT NULL, after_id INTEGER NOT NULL, PRIMARY KEY(player_id, connection));
CREATE INDEX IF NOT EXISTS chat_scope ON chat(scope, session_id, id);
"""


def initialize(connection):
    connection.executescript(SCHEMA)
