"""Render preview entrypoint, one authoritative process and remote D1."""

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn

from .host import PersistentServer
from .host_configuration import validate
from .realtime import create_app

SECRET_FILE = Path("/etc/secrets/rpg-runtime.json")
SECRET_KEYS = {"RPG_D1_SERVICE_TOKEN", "RPG_ADMIN_TOKEN"}


def configuration(environment):
    environment = dict(environment)
    if SECRET_FILE.exists():
        secrets = json.loads(SECRET_FILE.read_text(encoding="utf-8"))
        if not isinstance(secrets, dict) or set(secrets) != SECRET_KEYS:
            raise ValueError("Le fichier secret Render doit contenir les deux jetons")
        for key, value in secrets.items():
            if environment.get(key) and environment[key] != value:
                raise ValueError("Jeton Render défini avec deux valeurs différentes")
            environment[key] = value
    # Render injects its generated hostname before the first start.
    if not environment.get("RPG_PUBLIC_ORIGIN") and environment.get(
        "RENDER_EXTERNAL_HOSTNAME"
    ):
        environment["RPG_PUBLIC_ORIGIN"] = (
            "https://" + environment["RENDER_EXTERNAL_HOSTNAME"]
        )
    # Keep the production database unreachable until a controlled cutover.
    validate(environment)
    hostname = urlsplit(environment["RPG_PUBLIC_ORIGIN"]).hostname
    if not hostname.endswith(".onrender.com"):
        raise ValueError("La recette Render requiert le domaine HTTPS onrender.com")
    if environment.get("WEB_CONCURRENCY", "1") != "1":
        raise ValueError("Le moteur autoritaire requiert exactement un worker")
    port = int(environment.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT hors limites")
    return uvicorn.Config(
        create_app(environment),
        host="0.0.0.0",
        port=port,
        workers=1,
        # Only Render's HTTP ingress is public. It terminates TLS and
        # forwards the HTTPS scheme; application host/origin checks still apply.
        proxy_headers=True,
        forwarded_allow_ips="*",
        timeout_graceful_shutdown=20,
        access_log=False,
    )


def main():
    config = configuration(dict(os.environ))
    asyncio.run(
        PersistentServer(
            config, config.app.state.coordinator, retry_seconds=0.5
        ).serve()
    )


if __name__ == "__main__":
    main()
