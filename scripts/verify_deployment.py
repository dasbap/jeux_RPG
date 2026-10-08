import asyncio
import json
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from websockets.asyncio.client import connect


async def verify_realtime(base, catalogue, token):
    async with connect(base.replace('https://', 'wss://') + '/api/ws', origin=base, open_timeout=30) as socket:
        await socket.send(json.dumps({'type': 'authenticate', 'headers': {'Authorization': 'Bearer ' + token}}))
        if json.loads(await asyncio.wait_for(socket.recv(), 15)).get('type') != 'authenticated':
            raise RuntimeError('Authentification WebSocket refusée')
        sequence = 0
        async def rpc(path, body=None, token=None):
            nonlocal sequence
            sequence += 1
            identifier = str(sequence)
            await socket.send(json.dumps({'id': identifier, 'path': path, 'method': 'POST' if body else 'GET', 'body': body,
                                          'headers': {'authorization': 'Bearer ' + token} if token else {}}))
            while True:
                result = json.loads(await asyncio.wait_for(socket.recv(), 30))
                if result.get('id') == identifier:
                    return result['result']
        tutorial = await rpc('/api/commands', {'request_id': uuid.uuid4().hex, 'action': 'tutorial', 'params': {}}, token)
        if tutorial['status'] != 200:
            raise RuntimeError('Tutoriel WebSocket refusé')
        for _ in range(4):
            state = await rpc('/api/state', token=token)
            timing = state['headers'].get('Server-Timing', '')
            if state['status'] != 200 or state['headers'].get('X-RPG-Runtime') != 'memory' or 'trips;desc="0"' not in timing:
                raise RuntimeError('Le rafraîchissement utilise encore la base distante')
        for attempt in range(12):
            await asyncio.sleep(1)
            state = await rpc('/api/state', token=token)
            if state['headers'].get('X-RPG-Save-Pending') == '0':
                break
        if state['headers'].get('X-RPG-Save-Pending') != '0':
            raise RuntimeError('Sauvegarde initiale du tutoriel non terminée')
        print('WebSocket, tutoriel, sauvegarde regroupée et rafraîchissements sans accès Turso vérifiés.')


def main():
    url = Path("deployment-url.txt").read_text().strip().splitlines()[-1]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith("-dasbaps-projects.vercel.app") or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit("URL de déploiement inattendue")
    base = "https://jeux-rpg.vercel.app"
    for route, expected in (("/", 200), ("/app.js", 200), ("/mobile_controls.js", 200), ("/admin", 200), ("/admin.js", 200), ("/api/classes", 200), ("/api/admin/accounts", 401)):
        status = None
        for attempt in range(3):
            try:
                headers = {"Origin": base}
                if route in ("/", "/admin"):
                    headers.update({"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document", "Referer": "https://vercel.com/"})
                with urlopen(Request(base + route, headers=headers), timeout=30) as response:
                    status = response.status
                    body = response.read(2 * 1024 * 1024)
                    if route == "/api/classes":
                        if "application/json" not in response.headers.get("Content-Type", ""):
                            raise SystemExit("API de classes inaccessible : réponse non JSON")
                        catalogue = json.loads(body)
                        if not isinstance(catalogue, list) or not catalogue:
                            raise SystemExit("Catalogue de classes invalide")
            except HTTPError as error:
                status = error.code
            except (URLError, TimeoutError):
                status = None
            if status == expected:
                break
            if attempt < 2:
                time.sleep(5)
        if status != expected:
            raise SystemExit(f"Vérification échouée : {route}, HTTP {status}, attendu {expected}")
        print(f"Route vérifiée : {route}, HTTP {status}")
    username = "verify_" + uuid.uuid4().hex[:12]
    password = uuid.uuid4().hex + uuid.uuid4().hex
    registration = json.dumps({"username": username, "password": password}).encode()
    with urlopen(Request(base + "/api/account/signup", data=registration, headers={"Content-Type": "application/json", "Origin": base}), timeout=30) as response:
        if response.status != 201:
            raise SystemExit("Inscription en production refusée")
        account = json.load(response)
    character = json.dumps({"action": "create", "name": "Vérification", "class_name": catalogue[0]["id"]}).encode()
    with urlopen(Request(base + "/api/account/character", data=character, headers={"Authorization": "Bearer " + account["token"], "Content-Type": "application/json", "Origin": base}), timeout=30) as response:
        selected = json.load(response)
        if not selected.get("selected"):
            raise SystemExit("Création de personnage refusée")
    with urlopen(Request(base + "/api/state", headers={"Authorization": "Bearer " + account["token"], "Origin": base}), timeout=30) as response:
        state = json.load(response)
        if response.status != 200 or not state.get("player"):
            raise SystemExit("Reprise du compte en production refusée")
    print("Comptes par mot de passe et personnage vérifiés, sans afficher les identifiants secrets.")
    print("Jeu et panneau admin disponibles ; accès admin anonyme refusé.")
    asyncio.run(verify_realtime(base, catalogue, account["token"]))


if __name__ == "__main__":
    main()
