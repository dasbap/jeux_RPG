FENCE_FLOOR = 4_000_000_000_000_000
RESET_KEY = 'test_players_reset_accounts_v1'


def reset_test_players(connection):
    connection.execute('BEGIN IMMEDIATE')
    try:
        if connection.execute('SELECT value FROM meta WHERE key=?', (RESET_KEY,)).fetchone():
            connection.execute('COMMIT')
            return False
        tables = ('chat_streams', 'presence', 'chat', 'receipts', 'events', 'tutorials', 'members', 'sessions',
                  'admin_audit', 'account_status', 'team_invites', 'team_members', 'teams', 'friendships',
                  'account_sessions', 'account_characters', 'players', 'accounts', 'request_limits')
        for table in tables:
            connection.execute(f'DELETE FROM {table}')
        connection.execute("INSERT INTO meta VALUES('runtime_fence',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(FENCE_FLOOR),))
        connection.execute('INSERT INTO meta VALUES(?,?)', (RESET_KEY, 'done'))
        connection.execute('COMMIT')
        return True
    except BaseException:
        connection.execute('ROLLBACK')
        raise
