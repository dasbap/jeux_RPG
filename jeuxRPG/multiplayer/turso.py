import base64
import http.client
import json
import math
import re
import sqlite3
import time
from collections.abc import Mapping
from urllib.parse import urlsplit


class TursoHTTPError(sqlite3.OperationalError):
    def __init__(self, status):
        super().__init__('Accès HTTP Turso refusé')
        self.status = status


class TursoProtocolError(sqlite3.OperationalError):
    def __init__(self, code, request_index):
        super().__init__('Requête Turso refusée')
        self.code = code if isinstance(code, str) and re.fullmatch(r'[A-Z0-9_]{1,48}', code) else 'UNKNOWN'
        self.request_index = request_index


class Row(Mapping):
    def __init__(self, names, values):
        self.names, self.values = names, values

    def __getitem__(self, key):
        return self.values[self.names.index(key)] if isinstance(key, str) else self.values[key]

    def __iter__(self):
        return iter(self.names)

    def __len__(self):
        return len(self.names)


class Cursor:
    def __init__(self, result):
        names = [col['name'] for col in result['cols']]
        self.rows = iter(Row(names, [decode(v) for v in row]) for row in result['rows'])
        self.rowcount = result['affected_row_count']
        self.lastrowid = int(result['last_insert_rowid']) if result.get('last_insert_rowid') else None

    def fetchone(self):
        return next(self.rows, None)

    def fetchall(self):
        return list(self.rows)

    def __iter__(self):
        return self.rows


def encode(value):
    if value is None:
        return {'type': 'null'}
    if isinstance(value, (bool, int)):
        return {'type': 'integer', 'value': str(int(value))}
    if isinstance(value, float) and math.isfinite(value):
        return {'type': 'float', 'value': value}
    if isinstance(value, str):
        return {'type': 'text', 'value': value}
    if isinstance(value, bytes):
        return {'type': 'blob', 'base64': base64.b64encode(value).decode('ascii')}
    raise ValueError('Paramètre SQL non pris en charge')


def decode(value):
    kind = value['type']
    if kind == 'null':
        return None
    if kind == 'blob':
        return base64.b64decode(value['base64'])
    if kind == 'integer':
        return int(value['value'])
    if kind == 'float':
        return float(value['value'])
    if kind == 'text':
        return value['value']
    raise sqlite3.DatabaseError('Type de réponse Turso invalide')


class TursoConnection:
    def __init__(self, url, token, timeout=5, transport=None):
        parsed = urlsplit(url)
        if parsed.scheme not in ('https', 'libsql') or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            raise ValueError('TURSO_DATABASE_URL doit être une URL HTTPS ou libsql sans chemin')
        if not isinstance(token, str) or not token or any(ord(c) < 33 for c in token):
            raise ValueError('TURSO_AUTH_TOKEN est requis')
        if parsed.port not in (None, 443):
            raise ValueError('Port Turso non autorisé')
        self.host, self.port = parsed.hostname, 443
        self.token, self.timeout, self.transport = token, timeout, transport
        self.connection = None
        self.baton = None
        self.in_transaction = False
        self.closed = False
        self.broken = False

    def _send(self, requests):
        if self.closed:
            raise sqlite3.ProgrammingError('Connexion Turso fermée')
        self.round_trips = getattr(self, 'round_trips', 0) + 1
        started = time.perf_counter()
        payload = {'baton': self.baton, 'requests': requests}
        try:
            if self.transport:
                data = self.transport(payload)
            else:
                if self.connection is None:
                    self.connection = http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout)
                self.connection.request('POST', '/v2/pipeline', json.dumps(payload, allow_nan=False).encode(), {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
                response = self.connection.getresponse()
                body = response.read(16 * 1024 * 1024 + 1)
                if response.status != 200:
                    self.broken = True
                    raise TursoHTTPError(response.status)
                if len(body) > 16 * 1024 * 1024:
                    raise OSError('Base indisponible')
                data = json.loads(body)
            self.baton = data.get('baton')
            results = data['results']
            if len(results) != len(requests):
                raise ValueError('Réponse incomplète')
            for request_index, result in enumerate(results):
                if result['type'] != 'ok':
                    if 'CONSTRAINT' in result.get('error', {}).get('code', ''):
                        raise sqlite3.IntegrityError('Contrainte de base de données refusée')
                    raise TursoProtocolError(result.get('error', {}).get('code'), request_index)
            return results
        except (OSError, http.client.HTTPException, ValueError, KeyError) as error:
            self.broken = True
            if self.connection:
                self.connection.close()
                self.connection = None
            reason = 'timeout' if isinstance(error, TimeoutError) else 'network' if isinstance(error, (OSError, http.client.HTTPException)) else 'response_format'
            raise sqlite3.OperationalError('Connexion Turso interrompue : ' + reason) from None
        finally:
            self.duration = getattr(self, 'duration', 0) + time.perf_counter() - started

    def execute_many(self, statements):
        if self.broken:
            raise sqlite3.OperationalError('Connexion Turso à rétablir')
        transaction = self.in_transaction
        requests = []
        if self.baton is None:
            requests.append({'type': 'execute', 'stmt': {'sql': 'PRAGMA foreign_keys=ON', 'want_rows': False}})
        offset = len(requests)
        steps = []
        for index, (sql, params) in enumerate(statements):
            command = sql.strip().upper()
            if command.startswith('BEGIN'):
                transaction = True
            elif command in ('COMMIT', 'ROLLBACK', 'END'):
                transaction = False
            step = {'stmt': {'sql': sql, 'args': [encode(v) for v in params], 'want_rows': True}}
            if index:
                step['condition'] = {'type': 'ok', 'step': index - 1}
            steps.append(step)
        requests.append({'type': 'batch', 'batch': {'steps': steps}})
        self.in_transaction = transaction
        if not transaction:
            requests.append({'type': 'close'})
        results = self._send(requests)
        if transaction and not self.baton:
            self.broken = True
            raise sqlite3.DatabaseError('Transaction Turso non confirmée')
        batch = results[offset]['response']['result']
        for index, error in enumerate(batch['step_errors']):
            if error:
                if 'CONSTRAINT' in error.get('code', ''):
                    raise sqlite3.IntegrityError('Contrainte de base de données refusée')
                raise TursoProtocolError(error.get('code'), index)
        if len(batch['step_results']) != len(statements) or any(item is None for item in batch['step_results']):
            raise sqlite3.DatabaseError('Réponse de lot Turso incomplète')
        return [Cursor(item) for item in batch['step_results']]

    def execute(self, sql, params=()):
        statement = sql.strip().upper()
        if self.broken and statement != 'ROLLBACK':
            raise sqlite3.OperationalError('Connexion Turso à rétablir')
        beginning = statement.startswith('BEGIN')
        ending = statement in ('COMMIT', 'ROLLBACK', 'END')
        requests = []
        if self.baton is None:
            requests.append({'type': 'execute', 'stmt': {'sql': 'PRAGMA foreign_keys=ON', 'want_rows': False}})
        index = len(requests)
        requests.append({'type': 'execute', 'stmt': {'sql': sql, 'args': [encode(v) for v in params], 'want_rows': True}})
        if ending or not self.in_transaction and not beginning:
            requests.append({'type': 'close'})
        results = self._send(requests)
        if beginning:
            if not self.baton:
                self.broken = True
                raise sqlite3.DatabaseError('Transaction Turso non confirmée')
            self.in_transaction = True
        elif ending:
            self.in_transaction = False
        return Cursor(results[index]['response']['result'])

    def executescript(self, script):
        if self.in_transaction:
            raise sqlite3.ProgrammingError('Migration pendant une transaction')
        statements, pending = [], ''
        for char in script:
            pending += char
            if char == ';' and sqlite3.complete_statement(pending):
                statements.append(pending)
                pending = ''
        if pending.strip():
            statements.append(pending)
        explicit = bool(statements) and statements[0].strip().upper().startswith('BEGIN')
        if not explicit:
            self.execute('BEGIN IMMEDIATE')
        try:
            for statement in statements:
                self.execute(statement)
            if not explicit:
                self.execute('COMMIT')
        except BaseException:
            try:
                if self.in_transaction:
                    self.execute('ROLLBACK')
            except sqlite3.Error:
                pass
            raise

    def close(self):
        try:
            if self.baton:
                self._send([{'type': 'close'}])
        finally:
            self.baton = None
            self.in_transaction = False
            self.closed = True
            if self.connection:
                self.connection.close()
