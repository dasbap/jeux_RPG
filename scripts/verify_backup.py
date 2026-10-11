import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from jeuxRPG.multiplayer.service import GameService


def table_summary(connection):
    result = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        rows = sorted(repr(tuple(row)) for row in connection.execute('SELECT * FROM ' + quoted))
        result[name] = {'rows': len(rows), 'digest': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    return result


def verify_backup(database, temporary_directory=None):
    database = Path(database).resolve(strict=True)
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source:
        with tempfile.TemporaryDirectory(dir=temporary_directory) as directory:
            restored_path = Path(directory) / 'restored.sqlite3'
            with sqlite3.connect(restored_path) as restored:
                source.backup(restored)
                if restored.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Copie SQLite invalide')
                if restored.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise RuntimeError('Relations SQLite invalides')
                summary = table_summary(restored)
            before = table_summary(source)
            if before != summary:
                raise RuntimeError('La source a changé pendant le contrôle ou la copie diffère')
            service = GameService(restored_path, log_directory='-')
            try:
                if service.db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('La reprise du moteur invalide la copie')
            finally:
                service.close()
            if table_summary(source) != before:
                raise RuntimeError('La source a changé pendant le contrôle')
    return {'integrity': 'ok', 'copied_tables': len(summary), 'rows': {key: value['rows'] for key, value in summary.items()}, 'engine_reopened': True, 'source_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('database')
    parser.add_argument('--temporary-directory')
    args = parser.parse_args()
    print(json.dumps(verify_backup(args.database, args.temporary_directory), ensure_ascii=False))
