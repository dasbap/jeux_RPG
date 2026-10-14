import os
from pathlib import Path

from dotenv import dotenv_values, set_key

from jeuxRPG.multiplayer.redis_configuration import RedisConfigurationError, redis_url


def prepare(path, environment):
    pulled = dotenv_values(path)
    values = {key: value for key, value in pulled.items() if value and value != "[SENSITIVE]"}
    required = ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "RPG_ADMIN_TOKEN")
    for key in required:
        value = environment.get(key)
        if not value or value == "[SENSITIVE]":
            raise ValueError("Configuration CI requise absente : " + key)
        values[key] = value
    values.update(RPG_RESET_TEST_PLAYERS="0", RPG_RUNTIME_REALMS="1")
    redis_urls = environment.get("REDIS_URLS")
    if redis_urls:
        values["REDIS_URLS"] = redis_urls
        values["RPG_REDIS_ACTIVE_INDEX"] = environment.get("RPG_REDIS_ACTIVE_INDEX") or "0"
    elif pulled.get("REDIS_URLS") == "[SENSITIVE]":
        raise ValueError("Configuration CI requise absente : REDIS_URLS")
    if environment.get("RPG_REDIS_ACTIVE_INDEX"):
        values["RPG_REDIS_ACTIVE_INDEX"] = environment["RPG_REDIS_ACTIVE_INDEX"]
    redis_url(values)
    path.write_text("", encoding="utf-8")
    path.chmod(0o600)
    for key, value in values.items():
        set_key(path, key, value)


def main():
    try:
        prepare(Path(".vercel/.env.production.local"), os.environ)
    except (ValueError, RedisConfigurationError) as error:
        print(str(error))
        return 1
    print("Configuration du build préparée avec les secrets CI et sans placeholders.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
