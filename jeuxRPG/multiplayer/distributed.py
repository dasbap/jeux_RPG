import hashlib
import json
import logging
import threading
import time
from collections import deque

from redis import Redis
from redis.exceptions import RedisError


RATE_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


class LocalRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries = {}

    def accept(self, key, limit):
        now = time.monotonic()
        with self._lock:
            for expired in [item for item, values in self._entries.items() if not values or values[-1] <= now - 60]:
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


class RedisRateLimiter:
    def __init__(self, url, prefix="jeux-rpg:rate:v1:", fallback=None):
        self.redis = Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        self.prefix = prefix
        self.fallback = fallback or LocalRateLimiter()
        self._warned_at = 0.0

    def accept(self, key, limit):
        digest = hashlib.sha256(json.dumps(key, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        try:
            count = int(self.redis.eval(RATE_SCRIPT, 1, self.prefix + digest, "60"))
            return count <= limit
        except RedisError:
            now = time.monotonic()
            if now - self._warned_at >= 60:
                logging.getLogger(__name__).warning("Rate limiting Redis indisponible ; fallback local actif")
                self._warned_at = now
            return self.fallback.accept(key, limit)

    def close(self):
        self.redis.close()


def build_rate_limiter(environment, fallback=None):
    url = environment.get("REDIS_URL") or environment.get("KV_URL")
    if url:
        return RedisRateLimiter(url, fallback=fallback)
    return fallback or LocalRateLimiter()


class PresenceRegistry:
    def __init__(self, url=None, prefix="jeux-rpg:presence:v1:"):
        self.prefix = prefix
        self.redis = Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2) if url else None
        self.local = {}

    @classmethod
    def from_environment(cls, environment):
        return cls(environment.get("REDIS_URL") or environment.get("KV_URL"))

    @property
    def _hash(self):
        return self.prefix + "entries"

    @property
    def _seen(self):
        return self.prefix + "seen"

    def __setitem__(self, player_id, value):
        data = {"realm": int(value["realm"]), "seen": float(value["seen"])}
        if self.redis is None:
            self.local[player_id] = data
            return
        payload = json.dumps(data, separators=(",", ":"))
        pipe = self.redis.pipeline()
        pipe.hset(self._hash, player_id, payload)
        pipe.zadd(self._seen, {player_id: data["seen"]})
        pipe.execute()

    def _decode(self, value):
        if value is None:
            return None
        if isinstance(value, dict):
            return dict(value)
        return json.loads(value)

    def get(self, player_id, default=None):
        if self.redis is None:
            value = self.local.get(player_id)
        else:
            value = self.redis.hget(self._hash, player_id)
        decoded = self._decode(value)
        return default if decoded is None else decoded

    def __getitem__(self, player_id):
        if self.redis is None:
            return self.local[player_id]
        value = self.get(player_id)
        if value is None:
            raise KeyError(player_id)
        return value

    def __len__(self):
        if self.redis is None:
            return len(self.local)
        return int(self.redis.hlen(self._hash))

    def __contains__(self, player_id):
        return self.get(player_id) is not None

    def pop(self, player_id, default=None):
        value = self.get(player_id, default)
        if self.redis is None:
            self.local.pop(player_id, None)
        else:
            pipe = self.redis.pipeline()
            pipe.hdel(self._hash, player_id)
            pipe.zrem(self._seen, player_id)
            pipe.execute()
        return value

    def items(self):
        if self.redis is None:
            return [(key, dict(value)) for key, value in self.local.items()]
        return [(key, json.loads(value)) for key, value in self.redis.hgetall(self._hash).items()]

    def values(self):
        return [value for _, value in self.items()]

    def prune(self, cutoff):
        if self.redis is None:
            self.local = {key: value for key, value in self.local.items() if value["seen"] > cutoff}
            return
        expired = self.redis.zrangebyscore(self._seen, "-inf", cutoff)
        if not expired:
            return
        pipe = self.redis.pipeline()
        pipe.hdel(self._hash, *expired)
        pipe.zrem(self._seen, *expired)
        pipe.execute()

    def close(self):
        if self.redis is not None:
            self.redis.close()
