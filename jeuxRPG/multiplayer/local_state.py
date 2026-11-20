import threading
import time
from collections import deque


class LocalRateLimiter:
    def __init__(self, clock=None):
        self._clock = clock
        self._lock = threading.Lock()
        self._entries = {}

    def accept(self, key, limit):
        now = self._clock() if self._clock is not None else time.monotonic()
        with self._lock:
            for expired in [
                item
                for item, values in self._entries.items()
                if not values or values[-1] <= now - 60
            ]:
                del self._entries[expired]
            if key not in self._entries and len(self._entries) >= 4096:
                return False
            queue = self._entries.setdefault(key, deque())
            while queue and queue[0] <= now - 60:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(now)
            return True


class PresenceRegistry:
    def __init__(self):
        self.local = {}

    def __setitem__(self, player_id, value):
        self.local[player_id] = {
            "realm": int(value["realm"]),
            "seen": float(value["seen"]),
        }

    def get(self, player_id, default=None):
        value = self.local.get(player_id)
        return default if value is None else dict(value)

    def __getitem__(self, player_id):
        return self.local[player_id]

    def __len__(self):
        return len(self.local)

    def __contains__(self, player_id):
        return player_id in self.local

    def pop(self, player_id, default=None):
        return self.local.pop(player_id, default)

    def items(self):
        return [(key, dict(value)) for key, value in self.local.items()]

    def values(self):
        return [value for _, value in self.items()]

    def prune(self, cutoff):
        self.local = {
            key: value for key, value in self.local.items() if value["seen"] > cutoff
        }
