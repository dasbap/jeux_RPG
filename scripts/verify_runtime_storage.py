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
from jeuxRPG.multiplayer.redis_configuration import redis_url


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
    mode = "online"
    url = redis_url(environment)
    if not url:
        raise RuntimeError("missing_configuration")
    print("Vérification de la connexion Redis.", flush=True)
    try:
        with Redis.from_url(url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5) as redis:
            redis.ping()
            redis.eval("return 1", 0)
            with redis.pubsub() as pubsub:
                pubsub.subscribe("jeux-rpg:runtime:v2:accounts:diagnostic")
                pubsub.get_message(timeout=5)
    except ResponseError as error:
        if environment.get("RPG_ALLOW_SOLO_RELEASE") != "1" or failure_code(error) != "redis_quota":
            raise
        mode = "solo"
        print("Quota Redis épuisé : publication du mode solo uniquement.", flush=True)
    print("Vérification de la restauration depuis Turso.", flush=True)
    store = RuntimeStore.load(environment)
    store.close()
    return mode


def main():
    environment = {**dotenv_values(Path(".vercel/.env.production.local")), **os.environ}
    environment["RPG_RESET_TEST_PLAYERS"] = "0"
    try:
        mode = verify(environment)
    except Exception as error:
        print("Stockage du moteur indisponible : " + failure_code(error))
        return 1
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"mode={mode}\n")
    print("Restauration du moteur vérifiée ; mode de publication : " + mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
