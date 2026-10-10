from fastapi.testclient import TestClient

from jeuxRPG.multiplayer.realtime import create_app


class UnavailableCoordinator:
    async def rpc(self, message):
        raise AssertionError('Le healthcheck ne doit pas accéder au moteur')

    async def close(self):
        pass


def test_asgi_health_reports_release_without_database_access():
    app = create_app({'RPG_RELEASE_SHA': 'reviewed-commit'}, UnavailableCoordinator())
    with TestClient(app) as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('application/json')
        assert response.headers['cache-control'] == 'no-store'
        assert response.json() == {'status': 'ok', 'release': 'reviewed-commit'}
        assert client.get('/missing-route').status_code == 404


def test_asgi_health_omits_unconfigured_release():
    with TestClient(create_app({}, UnavailableCoordinator())) as client:
        assert client.get('/health').json() == {'status': 'ok'}
