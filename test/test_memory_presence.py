import time

from jeuxRPG.multiplayer.distributed import PresenceRegistry
from jeuxRPG.multiplayer.realtime_store import RuntimeStore


def test_runtime_presence_and_ticks_never_use_redis_even_with_production_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://configured-production:6379")
    def forbidden(*args, **kwargs):
        raise AssertionError("Le moteur en RAM ne doit pas créer une présence Redis")
    monkeypatch.setattr(PresenceRegistry, "from_environment", forbidden)
    store = RuntimeStore({"VERCEL": "1", "REDIS_URL": "redis://configured-production:6379"})
    try:
        registry = store.service.runtime_presence
        assert registry.redis is None
        for _ in range(20):
            store.tick()
        now = time.time()
        registry["active"] = {"realm": 1, "seen": now}
        registry["expired"] = {"realm": 1, "seen": now - 120}
        registry.prune(now - 60)
        assert len(registry) == 1
        assert registry.get("active") == {"realm": 1, "seen": now}
        for _ in range(20):
            store.tick()
        assert list(registry.items()) == [("active", {"realm": 1, "seen": now})]
    finally:
        store.close()
