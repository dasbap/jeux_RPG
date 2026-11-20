import urllib.error
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.update_oracle_dns import update

ENV = {"RPG_DUCKDNS_SUBDOMAIN": "jeux-rpg", "RPG_DUCKDNS_TOKEN": "test-token-" * 4}


@pytest.mark.parametrize(
    "tokens,expected_token",
    [
        ({"RPG_DUCKDNS_TOKEN": "primary-token-" * 3}, "primary-token-" * 3),
        ({"DUCKDNS_TOKEN": "local-token-" * 3}, "local-token-" * 3),
        (
            {
                "RPG_DUCKDNS_TOKEN": "primary-token-" * 3,
                "DUCKDNS_TOKEN": "local-token-" * 3,
            },
            "primary-token-" * 3,
        ),
    ],
)
def test_update_uses_oracle_ip_instead_of_controller_ip(
    monkeypatch, tokens, expected_token
):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, _):
            return b"OK\n1.2.3.4\n\nUPDATED\n"

    def request(value, timeout):
        calls.append((value, timeout))
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", request)
    result = update({"RPG_DUCKDNS_SUBDOMAIN": "jeux-rpg", **tokens}, "1.2.3.4")
    request, timeout = calls[0]
    target = urlsplit(request.full_url)
    assert (target.scheme, target.hostname) == ("https", "www.duckdns.org")
    assert parse_qs(target.query)["ip"] == ["1.2.3.4"]
    assert parse_qs(target.query)["token"] == [expected_token]
    assert timeout == 20
    assert result["provider_confirmed"] is True
    assert result["dns_propagation_verified"] is False
    assert expected_token not in str(result)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "::1", ""])
def test_non_public_or_missing_ip_refused(address):
    with pytest.raises(ValueError):
        update(ENV, address)


def test_transport_failure_does_not_expose_token(monkeypatch):
    def failed(*_, **__):
        raise urllib.error.URLError("URL with token=" + ENV["RPG_DUCKDNS_TOKEN"])

    monkeypatch.setattr("urllib.request.urlopen", failed)
    with pytest.raises(RuntimeError) as error:
        update(ENV, "1.2.3.4")
    assert ENV["RPG_DUCKDNS_TOKEN"] not in str(error.value)
    assert error.value.__suppress_context__ is True
