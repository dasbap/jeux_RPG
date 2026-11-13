"""Host automation is restricted to the isolated preview until controlled cutover."""

from urllib.parse import urlsplit

TEST_WORKER = "https://jeux-rpg-oracle-test.dasbap-jeux-rpg.workers.dev"


def validate(environment):
    if (
        environment.get("RPG_RUNTIME_MODE") != "single"
        or environment.get("RPG_DATABASE_BACKEND") != "d1"
        or environment.get("RPG_DEPLOYMENT_STAGE") != "preview"
        or environment.get("RPG_D1_WORKER_URL") != TEST_WORKER
        or environment.get("VERCEL")
    ):
        raise ValueError(
            "Cette installation est réservée au D1 fictif de préproduction"
        )
    for key in ("RPG_D1_SERVICE_TOKEN", "RPG_ADMIN_TOKEN"):
        value = environment.get(key) or ""
        if (
            len(value) < 32
            or "REPLACE" in value
            or any(char.isspace() for char in value)
        ):
            raise ValueError(f"{key} absent ou invalide")
    origin = urlsplit(environment.get("RPG_PUBLIC_ORIGIN", ""))
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.port
        or origin.path not in ("", "/")
        or origin.query
        or origin.fragment
        or "REPLACE" in origin.hostname
    ):
        raise ValueError("RPG_PUBLIC_ORIGIN doit être l'origine HTTPS du moteur")
    if environment.get("RPG_RUNTIME_REALMS") != "1":
        raise ValueError("La préproduction utilise un seul serveur logique")
