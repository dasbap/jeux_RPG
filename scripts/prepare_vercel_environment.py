import os
from pathlib import Path

from dotenv import dotenv_values, set_key


def prepare(path, environment):
    values = {key: value for key, value in dotenv_values(path).items() if value and value != "[SENSITIVE]"}
    required = ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "RPG_ADMIN_TOKEN")
    for key in required:
        value = environment.get(key)
        if not value or value == "[SENSITIVE]":
            raise ValueError("Configuration CI requise absente : " + key)
        values[key] = value
    values.update(RPG_RESET_TEST_PLAYERS="0", RPG_RUNTIME_REALMS="1")
    path.write_text("", encoding="utf-8")
    path.chmod(0o600)
    for key, value in values.items():
        set_key(path, key, value)


def main():
    try:
        prepare(Path(".vercel/.env.production.local"), os.environ)
    except ValueError as error:
        print(str(error))
        return 1
    print("Configuration du build préparée avec les secrets CI et sans placeholders.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
