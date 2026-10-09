import io
import json
import sqlite3
import time
from copy import deepcopy

from .schema import initialize
from .serverless import Application, RemoteGameService
from .turso import TursoConnection
from .world import zone_of


SOCIAL_TABLES = ('accounts', 'account_characters', 'account_sessions', 'friendships', 'teams', 'team_members', 'team_invites')
TABLES = ('meta', 'accounts', 'players', 'account_characters', 'account_sessions', 'friendships', 'teams', 'team_members', 'team_invites', 'account_status', 'sessions', 'members', 'tutorials', 'events', 'receipts', 'receipt_expiry', 'admin_audit')
KEYS = {'accounts': ('id',), 'account_characters': ('account_id', 'class_name'), 'account_sessions': ('token_hash',), 'friendships': ('first_id', 'second_id'), 'teams': ('id',), 'team_members': ('account_id',), 'team_invites': ('id',), 'meta': ('key',), 'players': ('id',), 'account_status': ('player_id',), 'sessions': ('id',),
        'members': ('session_id', 'player_id'), 'tutorials': ('session_id',), 'events': ('id',),
        'receipts': ('player_id', 'request_id'), 'receipt_expiry': ('player_id', 'request_id'), 'admin_audit': ('id',)}


def progress_signature(party):
    completed = sorted(key for key, value in party.get('custom_quests', {}).items() if value.get('status') == 'completed')
    value = {'inventory': party.get('inventory'), 'equipment': party.get('equipment'),
             'characters': {key: [value.get('name'), value.get('level'), value.get('exp')] for key, value in party.get('characters', {}).items()},
             'quests': [party.get('quest'), completed],
             'zone': zone_of(party.get('position')) or zone_of(party.get('field_map')),
             'checkpoint': party.get('autosave_checkpoint')}
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


class MemoryService(RemoteGameService):
    def tick(self, session_id=None):
        if session_id is None:
            players = None if self.legacy_auth else {key for key, value in self.runtime_presence.items() if time.monotonic() - value['seen'] < 60}
            super().tick(prepare_views=False, active_players=players)

    def close(self):
        pass


class RuntimeStore:
    def __init__(self, environment, durable=None, clock=None):
        self.environment = environment
        self.db = sqlite3.connect(':memory:', check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        initialize(self.db)
        self.db.execute('PRAGMA foreign_keys=ON')
        if durable:
            for table in TABLES:
                for row in durable.get(table, []):
                    columns = list(row)
                    self.db.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', tuple(row.values()))
        self.service = MemoryService(connection=self.db, log_directory='-', clock=clock)
        self.service.legacy_auth = not bool(environment.get('VERCEL'))
        self.service.realm_count = max(1, min(3, int(environment.get('RPG_RUNTIME_REALMS', '1'))))
        self.app = Application(lambda: self.service, environment)
        self.durable = {table: self.rows(table) for table in TABLES}
        self.signatures = self.session_signatures()
        self.pending = {}
        self.due = None
        self.save_count = 0
        self.schema_ready = False
        self.last_save_error = False
        self.observed_changes = self.db.total_changes

    @classmethod
    def load(cls, environment):
        connection = TursoConnection(environment['TURSO_DATABASE_URL'], environment['TURSO_AUTH_TOKEN'])
        try:
            initialize(connection)
            reset = False
            if environment.get("RPG_RESET_TEST_PLAYERS") == "1" and not environment.get("VERCEL"):
                from .account_rollout import reset_test_players
                reset = reset_test_players(connection)
            results = connection.execute_many([(f'SELECT * FROM {table}', ()) for table in TABLES])
            store = cls(environment, {table: [dict(row) for row in rows] for table, rows in zip(TABLES, results)})
            store.reset_performed = reset
            return store
        finally:
            connection.close()

    def rows(self, table):
        return [dict(row) for row in self.db.execute(f'SELECT * FROM {table}')]

    def session_signatures(self, only=None):
        result = {}
        for row in self.db.execute('SELECT s.id,s.state,t.data FROM sessions s LEFT JOIN tutorials t ON t.session_id=s.id'):
            if only is not None and row['id'] not in only:
                continue
            members = tuple(item[0] for item in self.db.execute('SELECT player_id FROM members WHERE session_id=? ORDER BY player_id', (row['id'],)))
            result[row['id']] = (members, bool(row['data']), progress_signature(json.loads(row['data'])) if row['data'] else None)
        return result

    def capture(self, now=None, dirty_only=False):
        now = time.monotonic() if now is None else now
        social_tables = SOCIAL_TABLES if self.service.persistent_social_changed else ()
        self.service.persistent_social_changed = False
        for table in ('players', 'account_status', 'admin_audit', 'receipts', 'receipt_expiry', *social_tables):
            old = {tuple(row[key] for key in KEYS[table]): row for row in self.durable[table]}
            current = self.rows(table)
            current_keys = {tuple(row[value] for value in KEYS[table]) for row in current}
            for key in old.keys() - current_keys:
                self.pending[(table, key)] = None
                del old[key]
            for row in current:
                key = tuple(row[value] for value in KEYS[table])
                if old.get(key) != row:
                    self.pending[(table, key)] = row
                    old[key] = row
            self.durable[table] = list(old.values())
        updates = self.session_signatures(self.service.dirty_sessions if dirty_only else None)
        self.service.dirty_sessions.clear()
        signatures = {**self.signatures, **updates} if dirty_only else updates
        for session_id, signature in signatures.items():
            if self.signatures.get(session_id) == signature:
                continue
            for table in ('sessions', 'members', 'tutorials', 'events'):
                old = {tuple(row[key] for key in KEYS[table]): row for row in self.durable[table]}
                for row in self.rows(table):
                    matches = row.get('id') == session_id if table == 'sessions' else row.get('session_id') == session_id
                    if matches:
                        key = tuple(row[value] for value in KEYS[table])
                        if old.get(key) != row:
                            self.pending[(table, key)] = row
                        old[key] = row
                self.durable[table] = list(old.values())
        self.signatures = signatures
        if self.pending and (self.due is None or signatures != getattr(self, "captured_signatures", None)):
            self.captured_signatures = dict(signatures)
            self.durable['meta'] = self.rows('meta')
            for row in self.durable['meta']:
                self.pending[('meta', (row['key'],))] = row
            if self.due is None:
                self.due = now + 5
        self.observed_changes = self.db.total_changes

    def request(self, message, prepared_login=None):
        if self.db.total_changes != self.observed_changes and not self.service.dirty_sessions and not self.service.persistent_social_changed:
            self.capture()
        raw = json.dumps(message.get('body')).encode() if message.get('body') is not None else b''
        path, _, query = message['path'].partition('?')
        environment = {'PATH_INFO': path, 'QUERY_STRING': query, 'REQUEST_METHOD': message.get('method', 'GET'),
                       'HTTP_HOST': message['host'], 'REMOTE_ADDR': message['peer'], 'wsgi.url_scheme': message.get('scheme', 'https'),
                       'wsgi.input': io.BytesIO(raw), 'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(raw))}
        for key, value in message.get('headers', {}).items():
            environment['HTTP_' + key.upper().replace('-', '_')] = value
        environment['rpg.prepared_login'] = prepared_login
        result = {}
        def start(status, headers):
            result.update(status=int(status.split()[0]), headers=dict(headers))
        body = b''.join(self.app(environment, start))
        result['body'] = json.loads(body) if result['headers']['Content-Type'].startswith('application/json') else body.decode()
        result['headers']['X-RPG-Runtime'] = 'memory'
        if self.environment.get('RPG_RESET_TEST_PLAYERS') == '1' and self.db.execute("SELECT 1 FROM meta WHERE key='test_players_reset_accounts_v1' AND value='done'").fetchone():
            result['headers']['X-RPG-Legacy-Tests-Reset'] = '1'
        self.capture(dirty_only=True)
        if path == '/api/state' and result['status'] == 200:
            result['headers']['X-RPG-Save-Pending'] = '1' if self.pending else '0'
            result['headers']['X-RPG-Save-Count'] = str(self.save_count)
        return result

    def tick(self):
        if self.db.total_changes != self.observed_changes and not self.service.dirty_sessions and not self.service.persistent_social_changed:
            self.capture()
        self.service.tick()
        self.capture(dirty_only=True)

    def snapshot(self):
        return json.dumps(self.durable, separators=(',', ':'))

    def pending_batch(self):
        return deepcopy(self.pending)

    def persist(self, fence, batch):
        connection = TursoConnection(self.environment['TURSO_DATABASE_URL'], self.environment['TURSO_AUTH_TOKEN'])
        try:
            if not self.schema_ready:
                initialize(connection)
                self.schema_ready = True
            current = connection.execute_many([('BEGIN IMMEDIATE', ()), ("SELECT value FROM meta WHERE key='runtime_fence'", ())])[-1].fetchone()
            if current and int(current[0]) > fence:
                raise RuntimeError('Moteur remplacé')
            statements = [("INSERT INTO meta VALUES('runtime_fence',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(fence),))]
            for table in TABLES:
                for (target, key), row in batch.items():
                    if target != table or table == 'meta' and row and row['key'] == 'runtime_fence':
                        continue
                    if row is None:
                        where = ' AND '.join(f'{column}=?' for column in KEYS[table])
                        statements.append((f'DELETE FROM {table} WHERE {where}', key))
                        continue
                    columns = list(row)
                    updates = ','.join(f'{column}=excluded.{column}' for column in columns if column not in KEYS[table])
                    statements.append((f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)}) ON CONFLICT({",".join(KEYS[table])}) DO UPDATE SET {updates}', tuple(row.values())))
            statements.append(('COMMIT', ()))
            connection.execute_many(statements)
        finally:
            connection.close()

    def saved(self, batch):
        for key, value in batch.items():
            if key in self.pending and self.pending[key] == value:
                del self.pending[key]
        self.due = time.monotonic() + 5 if self.pending else None
        self.save_count += 1
        self.last_save_error = False

    def close(self):
        RemoteGameService.close(self.service)
