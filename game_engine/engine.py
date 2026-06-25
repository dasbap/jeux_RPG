import asyncio
import threading
from typing import List, Set

from jeuxRPG._class._event.confrontation.encounter.fight import Fight


class GameEngine:
    """Manage concurrent fights asynchronously and prevent unit overlap."""

    def __init__(self):
        self._active_characters: Set[str] = set()
        self._lock = threading.Lock()

    def _participants_ids(self, fight: Fight) -> Set[str]:
        return {c.get_id() for c in fight.get_all_individuals()}

    def _check_overlaps(self, fights: List[Fight]):
        seen = set()
        for f in fights:
            ids = self._participants_ids(f)
            for i in ids:
                if i in seen:
                    raise ValueError(f"Character {i} present in multiple fights in the same run")
                seen.add(i)
        # check against currently active characters
        with self._lock:
            overlap = seen & self._active_characters
            if overlap:
                raise ValueError(f"Characters already in active fights: {', '.join(overlap)}")
        return seen

    async def _run_fight(self, fight: Fight):
        # Run fight rounds in a thread to avoid blocking the event loop
        try:
            while not fight.is_over():
                await asyncio.to_thread(fight.start_round, True)
                await asyncio.sleep(0)
        finally:
            # ensure fight end cleanup
            try:
                await asyncio.to_thread(fight.end)
            except Exception:
                pass

    async def _run_all(self, fights: List[Fight]):
        tasks = [asyncio.create_task(self._run_fight(f)) for f in fights]
        await asyncio.gather(*tasks)

    def run_fights(self, fights: List[Fight], timeout: float | None = None):
        """
        Run multiple fights concurrently until completion.

        - Validates that no character is present in more than one fight.
        - Prevents starting fights that include characters already active in previous runs.
        """
        if not fights:
            return

        participants = self._check_overlaps(fights)

        # register participants
        with self._lock:
            self._active_characters.update(participants)

        try:
            # Use asyncio.run to provide an event loop for this call
            if timeout:
                asyncio.run(asyncio.wait_for(self._run_all(fights), timeout))
            else:
                asyncio.run(self._run_all(fights))
        finally:
            # unregister participants
            with self._lock:
                for p in participants:
                    self._active_characters.discard(p)
