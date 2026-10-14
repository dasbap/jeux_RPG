import json
import os
from pathlib import Path

from dotenv import dotenv_values
from redis import Redis
from redis.exceptions import (
    AuthenticationError,
    ConnectionError,
    ResponseError,
    TimeoutError,
)

from jeuxRPG.multiplayer.realtime_store import RuntimeStore


def failure_code(error):
    if isinstance(error, AuthenticationError):
        return "redis_authentication"
    if isinstance(error, TimeoutError):
        return "redis_timeout"
    if isinstance(error, ConnectionError):
        return "redis_connection"
    if isinstance(error, ResponseError):
        message = str(error).lower()
        if "limit" in message or "quota" in message:
            return "redis_quota"
        return "redis_command"
    return "runtime_storage"


def verify(environment):
    url = environment.get("REDIS_URL") or environment.get("KV_URL")
    if not url:
        raise RuntimeError("missing_configuration")
    with Redis.from_url(url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5) as redis:
        redis.ping()
        saved = redis.get("jeux-rpg:runtime:v2:accounts:checkpoint")
    if saved:
        checkpoint = json.loads(saved)
        store = RuntimeStore(environment, checkpoint.get("durable", checkpoint))
    else:
        store = RuntimeStore.load(environment)
    store.close()


def main():
    environment = {**dotenv_values(Path(".vercel/.env.production.local")), **os.environ}
    environment["RPG_RESET_TEST_PLAYERS"] = "0"
    try:
        verify(environment)
    except Exception as error:
        print("Stockage du moteur indisponible : " + failure_code(error))
        return 1
    print("Connexion Redis et restauration du moteur vérifiées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
