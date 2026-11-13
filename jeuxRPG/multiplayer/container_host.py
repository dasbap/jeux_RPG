"""Render preview entrypoint, one authoritative process and remote D1."""

import asyncio
import os
from urllib.parse import urlsplit

import uvicorn

from .host import PersistentServer
from .host_configuration import validate
from .realtime import create_app


def configuration(environment):
    environment = dict(environment)
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
