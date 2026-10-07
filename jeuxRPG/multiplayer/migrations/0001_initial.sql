CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, username TEXT NOT NULL, username_key TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, suspended INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS account_sessions (token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id), player_id TEXT REFERENCES players(id), expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS account_characters (account_id TEXT NOT NULL REFERENCES accounts(id), class_name TEXT NOT NULL, player_id TEXT NOT NULL UNIQUE REFERENCES players(id), PRIMARY KEY(account_id,class_name));
CREATE TABLE IF NOT EXISTS friendships (first_id TEXT NOT NULL REFERENCES accounts(id), second_id TEXT NOT NULL REFERENCES accounts(id), requester TEXT NOT NULL REFERENCES accounts(id), status TEXT NOT NULL, PRIMARY KEY(first_id,second_id));
CREATE TABLE IF NOT EXISTS teams (id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES accounts(id));
CREATE TABLE IF NOT EXISTS team_members (account_id TEXT PRIMARY KEY REFERENCES accounts(id), team_id TEXT NOT NULL REFERENCES teams(id), active INTEGER NOT NULL, joined REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_invites (id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id), sender TEXT NOT NULL REFERENCES accounts(id), recipient TEXT NOT NULL REFERENCES accounts(id), status TEXT NOT NULL, expires REAL NOT NULL);
CREATE INDEX IF NOT EXISTS account_session_owner ON account_sessions(account_id,expires);
CREATE INDEX IF NOT EXISTS team_membership ON team_members(team_id,active);
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
