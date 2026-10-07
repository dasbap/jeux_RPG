from pathlib import Path


MIGRATIONS = Path(__file__).with_name("migrations")
REQUIRED_TABLES = {
    "accounts",
    "account_sessions",
    "account_characters",
    "friendships",
    "teams",
    "team_members",
    "team_invites",
    "presence",
    "chat",
    "meta",
    "players",
    "sessions",
    "members",
    "events",
    "receipts",
    "tutorials",
    "account_status",
    "admin_audit",
    "request_limits",
    "chat_streams",
}


def available_migrations():
    result = []
    for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        version = int(path.name.split("_", 1)[0])
        result.append((version, path))
    if not result:
        raise RuntimeError("Aucune migration de base de données disponible.")
    versions = [version for version, _ in result]
    if versions != list(range(1, versions[-1] + 1)):
        raise RuntimeError("La suite de migrations doit être continue à partir de 0001.")
    return result


def current_version(connection):
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL)"
    )
    row = connection.execute("SELECT version FROM schema_version WHERE id=1").fetchone()
    if row is None:
        connection.execute("INSERT INTO schema_version(id,version) VALUES(1,0)")
        return 0
    return int(row[0])


def validate_schema(connection, expected_version=None):
    migrations = available_migrations()
    latest = migrations[-1][0]
    expected = latest if expected_version is None else expected_version
    version = current_version(connection)
    if version != expected:
        raise RuntimeError(f"Version de schéma invalide : {version}, attendu {expected}.")
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    missing = REQUIRED_TABLES - tables
    if missing:
        raise RuntimeError("Tables manquantes : " + ", ".join(sorted(missing)))
    return True


def initialize(connection):
    if connection.in_transaction:
        raise RuntimeError("Les migrations doivent être exécutées hors transaction.")
    migrations = available_migrations()
    version = current_version(connection)
    latest = migrations[-1][0]
    if version > latest:
        raise RuntimeError(
            f"Base plus récente que le serveur : schéma {version}, serveur {latest}."
        )
    for target, path in migrations:
        if target <= version:
            continue
        script = path.read_text(encoding="utf-8")
        try:
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + script
                + "\nUPDATE schema_version SET version="
                + str(target)
                + " WHERE id=1;\nCOMMIT;"
            )
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        version = target
    validate_schema(connection, latest)
    return version
