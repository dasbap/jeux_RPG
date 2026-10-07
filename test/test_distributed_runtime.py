import time

from jeuxRPG.multiplayer.distributed import LocalRateLimiter, PresenceRegistry, build_rate_limiter


def test_local_rate_limiter_preserves_existing_contract():
    limiter = LocalRateLimiter()
    assert limiter.accept(("ip", "127.0.0.1"), 2) is True
    assert limiter.accept(("ip", "127.0.0.1"), 2) is True
    assert limiter.accept(("ip", "127.0.0.1"), 2) is False


def test_presence_registry_local_mapping_and_prune():
    registry = PresenceRegistry()
    now = time.time()
    registry["a"] = {"realm": 1, "seen": now - 120}
    registry["b"] = {"realm": 2, "seen": now}
    assert registry.get("b") == {"realm": 2, "seen": now}
    assert "a" in registry
    registry.prune(now - 60)
    assert "a" not in registry
    assert registry["b"]["realm"] == 2
    assert list(registry.values()) == [{"realm": 2, "seen": now}]


def test_build_rate_limiter_keeps_explicit_fallback_without_redis():
    fallback = LocalRateLimiter()
    assert build_rate_limiter({}, fallback=fallback) is fallback
