"""Persistent VM entrypoint: defer SIGTERM until the final D1 checkpoint succeeds."""

import asyncio
import logging
import os
import socket
from contextlib import suppress

import uvicorn

from .host_configuration import validate
from .realtime import create_app

LOG = logging.getLogger(__name__)


def notify(message):
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as transport:
            transport.connect(address)
            transport.sendall(message.encode())
    except OSError:
        LOG.warning("Notification systemd indisponible")


class PersistentServer(uvicorn.Server):
    def __init__(self, config, coordinator, retry_seconds=5):
        super().__init__(config)
        self.coordinator = coordinator
        self.stop_requested = False
        self.retry_seconds = retry_seconds

    def handle_exit(self, sig, frame):
        # Uvicorn's default handler would close the process before a D1 retry.
        # Repeated signals deliberately do not force an unconfirmed shutdown.
        self.stop_requested = True

    async def supervise(self):
        announced = False
        while True:
            await asyncio.sleep(self.retry_seconds)
            if not self.started:
                continue
            if not announced:
                notify("READY=1\nSTATUS=Moteur chargé depuis D1")
                announced = True
            notify("WATCHDOG=1")
            if self.coordinator.fenced:
                self.stop_requested = True
            if not self.stop_requested:
                continue
            notify("STATUS=Sauvegarde finale D1 avant arrêt")
            try:
                await self.coordinator.quiesce()
            except Exception:
                LOG.warning("Arrêt différé : le moteur reste en RAM pour réessayer D1")
                continue
            notify("STOPPING=1\nSTATUS=Fin du moteur après sauvegarde ou remplacement")
            self.should_exit = True
            return

    async def serve(self, sockets=None):
        monitor = asyncio.create_task(self.supervise())
        try:
            await super().serve(sockets)
        finally:
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor


def main():
    environment = dict(os.environ)
    validate(environment)
    app = create_app(environment)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8080,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        timeout_graceful_shutdown=30,
        access_log=False,
    )
    asyncio.run(PersistentServer(config, app.state.coordinator).serve())


if __name__ == "__main__":
    main()
