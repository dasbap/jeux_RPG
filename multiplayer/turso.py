import base64
import http.client
import json
import math
import sqlite3
from collections.abc import Mapping
from urllib.parse import urlsplit


class TursoHTTPError(sqlite3.OperationalError):
    def __init__(self, status):
        super().__init__('Accès HTTP Turso refusé')
        self.status = status


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
            for result in results:
                if result['type'] != 'ok':
                    if 'CONSTRAINT' in result.get('error', {}).get('code', ''):
                        raise sqlite3.IntegrityError('Contrainte de base de données refusée')
                    raise sqlite3.OperationalError('Requête Turso refusée')
            return results
        except (OSError, http.client.HTTPException, ValueError, KeyError):
            self.broken = True
            if self.connection:
                self.connection.close()
                self.connection = None
            raise sqlite3.OperationalError('Connexion Turso interrompue ; vérifiez votre état avant de réessayer') from None

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
        self.execute('BEGIN IMMEDIATE')
        try:
            for statement in statements:
                self.execute(statement)
            self.execute('COMMIT')
        except BaseException:
            try:
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
