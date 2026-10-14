import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jeuxRPG.multiplayer import distributed, realtime
from jeuxRPG.multiplayer.redis_configuration import RedisConfigurationError, redis_url
from jeuxRPG.multiplayer.serverless import Application


def environment(index="1"):
    return {
        "REDIS_URLS": json.dumps(["redis://first:6379", "rediss://second:6380"]),
        "RPG_REDIS_ACTIVE_INDEX": index,
        "REDIS_URL": "redis://old:6379",
    }


def test_active_redis_overrides_legacy_url_and_is_shared_by_all_clients(monkeypatch):
    selected = []
    client = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(
        distributed,
        "redis_client",
        lambda url, **kwargs: selected.append(url) or client,
    )
    limiter = distributed.build_rate_limiter(environment())
    presence = distributed.PresenceRegistry.from_environment(environment())
    app = Application(environment=environment())
    assert selected == ["rediss://second:6380"] * 3
    limiter.close()
    presence.close()
    app.redis_limiter.close()


def test_async_coordinator_uses_same_selected_endpoint(monkeypatch):
    async def run():
        selected = []
        pubsub = SimpleNamespace(subscribe=AsyncMock(), aclose=AsyncMock())
        client = SimpleNamespace(pubsub=lambda: pubsub, aclose=AsyncMock())
        monkeypatch.setattr(
            realtime.Redis,
            "from_url",
            lambda url, **kwargs: selected.append(url) or client,
        )
        coordinator = realtime.Coordinator(environment())
        monkeypatch.setattr(coordinator, "elect", AsyncMock())
        try:
            await coordinator.start()
            assert selected == ["rediss://second:6380"]
            pubsub.subscribe.assert_awaited_once()
        finally:
            await coordinator.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "values, index",
    [
        ("broken-secret", "0"),
        ('{"url":"secret"}', "0"),
        ("[]", "0"),
        ("[null]", "0"),
        ('["https://secret"]', "0"),
        ('["redis://[secret"]', "0"),
        ('["redis://secret:wrong"]', "0"),
        ('["redis://secret"]', "-1"),
        ('["redis://secret"]', "1"),
        ('["redis://secret"]', "abc"),
    ],
)
def test_invalid_configuration_fails_without_disclosing_urls(values, index):
    with pytest.raises(RedisConfigurationError) as caught:
        redis_url({"REDIS_URLS": values, "RPG_REDIS_ACTIVE_INDEX": index})
    assert "secret" not in str(caught.value)


def test_default_index_and_legacy_settings():
    assert redis_url(environment("0")) == "redis://first:6379"
    assert (
        redis_url({"REDIS_URLS": environment()["REDIS_URLS"]}) == "redis://first:6379"
    )
    assert redis_url({"REDIS_URL": "primary", "KV_URL": "legacy"}) == "primary"
    assert redis_url({"KV_URL": "legacy"}) == "legacy"
    assert redis_url({}) is None
