import io
import json
from email.message import Message
from urllib.error import HTTPError

import pytest

from scripts import verify_deployment


BASE = 'https://jeux-test-dasbaps-projects.vercel.app'


def response(body, content_type):
    result = io.BytesIO(body)
    result.headers = Message()
    result.headers['Content-Type'] = content_type
    return result


def test_release_health_accepts_exact_commit(monkeypatch):
    monkeypatch.setattr(verify_deployment, 'urlopen', lambda *args, **kwargs: response(json.dumps({'release': 'expected'}).encode(), 'application/json; charset=utf-8'))
    verify_deployment.verify_release(BASE, 'expected')


@pytest.mark.parametrize('body,content_type,message', [
    (b'<html>private response</html>', 'text/html', 'VERCEL_AUTOMATION_BYPASS_SECRET'),
    (b'{invalid', 'application/json', 'JSON invalide'),
    (b'{"release":"other"}', 'application/json', 'commit attendu'),
    (b'[]', 'application/json', 'commit attendu'),
])
def test_release_health_refuses_invalid_response(monkeypatch, body, content_type, message):
    monkeypatch.setattr(verify_deployment, 'urlopen', lambda *args, **kwargs: response(body, content_type))
    with pytest.raises(SystemExit, match=message) as failure:
        verify_deployment.verify_release(BASE, 'expected')
    assert 'private response' not in str(failure.value)


@pytest.mark.parametrize('status', [401, 403, 500])
def test_release_health_reports_status_without_body(monkeypatch, status):
    def blocked(*args, **kwargs):
        raise HTTPError(BASE + '/health', status, 'private response', {}, None)
    monkeypatch.setattr(verify_deployment, 'urlopen', blocked)
    with pytest.raises(SystemExit, match=f'HTTP {status}') as failure:
        verify_deployment.verify_release(BASE, 'expected')
    assert 'private response' not in str(failure.value)
