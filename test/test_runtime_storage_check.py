import pytest
from redis.exceptions import (
    AuthenticationError,
    ConnectionError,
    ResponseError,
    TimeoutError,
)

from scripts.verify_runtime_storage import failure_code


@pytest.mark.parametrize("error, expected", [
    (AuthenticationError("secret-token"), "redis_authentication"),
    (TimeoutError("redis://secret-host"), "redis_timeout"),
    (ConnectionError("secret-host"), "redis_connection"),
    (ResponseError("max daily request limit exceeded secret-token"), "redis_quota"),
    (ResponseError("secret-token"), "redis_command"),
    (ValueError("secret-player-data"), "runtime_storage"),
])
def test_storage_failures_do_not_disclose_connection_or_player_data(error, expected):
    assert failure_code(error) == expected
