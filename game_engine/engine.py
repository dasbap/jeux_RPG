import asyncio
import math
import threading
from typing import List, Set

from jeuxRPG._class._event.confrontation.encounter.fight import Fight


class GameEngine:
    def __init__(self):
        self._active_characters: Set[str] = set()
        self._lock = threading.Lock()

    def _participants_ids(self, fight: Fight) -> Set[str]:
        ids = [c.get_id() for c in fight.get_all_individuals()]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate participant identity")
        return set(ids)

    def _reserve(self, fights):
        seen = set()
        for fight in fights:
            ids = self._participants_ids(fight)
            if seen & ids:
                raise ValueError("Character present in multiple fights")
            seen.update(ids)
        with self._lock:
            if seen & self._active_characters:
                raise ValueError("Character already in an active fight")
            self._active_characters.update(seen)
        return seen

    def _check_overlaps(self, fights):
        return self._reserve(fights)

    async def _thread(self, function, *args):
        worker = asyncio.create_task(asyncio.to_thread(function, *args))
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(worker)
                break
            except asyncio.CancelledError:
                if worker.cancelled():
                    raise
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
        return result

    async def _run_fight(self, fight):
        try:
            for _ in range(10000):
                if fight.is_over():
                    return
                await self._thread(fight.start_round, True)
                await asyncio.sleep(0)
            raise TimeoutError("Fight exceeded its round limit")
        finally:
            await self._thread(fight.end)

    async def run_fights_async(self, fights: List[Fight], timeout: float | None = None):
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("timeout must be positive and finite")
        if not fights:
            return
        participants = self._reserve(fights)
        try:
            async with asyncio.timeout(timeout):
                async with asyncio.TaskGroup() as group:
                    for fight in fights:
                        group.create_task(self._run_fight(fight))
        finally:
            with self._lock:
                self._active_characters.difference_update(participants)

    def run_fights(self, fights: List[Fight], timeout: float | None = None):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_fights_async(fights, timeout))
        raise RuntimeError("Use await run_fights_async from an asynchronous application")
