"""One authoritative process backed by D1, without Redis coordination."""

import asyncio
import logging
import time

from .d1_client import D1Client, StaleRuntimeError
from .realtime import Coordinator
from .realtime_store import RuntimeStore
from .storage_configuration import database_backend


class SingleCoordinator(Coordinator):
    def __init__(self, environment):
        if environment.get("VERCEL"):
            raise ValueError(
                "Le mode single requiert un processus persistant hors Vercel"
            )
        if database_backend(environment) != "d1":
            raise ValueError("Le mode single requiert RPG_DATABASE_BACKEND=d1")
        super().__init__(environment)
        self.local = True
        self.fenced = False
        self.draining = False
        self.shutdown_confirmed = False

    def owner(self):
        return self.store is not None and not self.fenced

    def load(self):
        client = D1Client(self.environment)
        client.health()
        fence, snapshot = client.claim_snapshot()
        return fence, RuntimeStore(self.environment, snapshot)

    async def start(self):
        async with self.start_lock:
            if self.started:
                return
            self.fence, self.store = await self.memory_call(self.load)
            self.tasks.extend(
                [
                    asyncio.create_task(self.ticker()),
                    asyncio.create_task(self.heartbeat()),
                ]
            )
            self.started = True

    async def rpc(self, message):
        await self.start()
        return await self.execute(message)

    async def quiesce(self):
        """Freeze mutations before confirming the final checkpoint for the host."""
        async with self.lock:
            self.draining = True
            if self.fenced:
                # A superseded process must retire; it cannot save its old RAM.
                return
            if not self.owner():
                raise RuntimeError("Moteur non prêt pour l'arrêt")
            async with self.save_lock:
                await self.memory_call(self.store.capture)
                await self.write_checkpoint(
                    self.store, self.store.pending_batch(), self.fence
                )
                if self.store.last_save_error or self.store.pending:
                    raise RuntimeError("Arrêt différé : sauvegarde D1 non confirmée")
                self.shutdown_confirmed = True

    async def write_checkpoint(self, store, batch, fence):
        try:
            await self.memory_call(store.persist, fence, batch)
            store.saved(batch)
        except StaleRuntimeError:
            self.fenced = True
            self.checkpoint_rejections += 1
            store.last_save_error = True
            logging.getLogger(__name__).error(
                "Moteur remplacé : commandes et simulation suspendues"
            )
        except Exception:
            self.save_failures += 1
            store.last_save_error = True
            store.due = time.monotonic() + 5
            logging.getLogger(__name__).warning(
                "D1 indisponible : sauvegarde conservée en RAM"
            )

    async def heartbeat(self):
        while True:
            await asyncio.sleep(5)
            async with self.save_lock:
                if not self.owner():
                    continue
                # Even an empty checkpoint confirms D1 and rejects an old writer.
                await self.write_checkpoint(
                    self.store, self.store.pending_batch(), self.fence
                )

    async def release(self):
        # Socket disconnects must not release the persistent engine immediately.
        return

    async def close(self):
        async with self.lock:
            if self.owner() and not self.shutdown_confirmed:
                async with self.save_lock:
                    await self.memory_call(self.store.capture)
                    await self.write_checkpoint(
                        self.store, self.store.pending_batch(), self.fence
                    )
                    if not self.fenced and (
                        self.store.last_save_error or self.store.pending
                    ):
                        raise RuntimeError("Arrêt refusé : sauvegarde D1 non confirmée")
        await super().close()
        self.store = None
