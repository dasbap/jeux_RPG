import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main():
    url = Path("deployment-url.txt").read_text().strip().splitlines()[-1]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith("-dasbaps-projects.vercel.app") or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit("URL de déploiement inattendue")
    base = "https://jeux-rpg.vercel.app"
    for route, expected in (("/", 200), ("/app.js", 200), ("/admin", 200), ("/admin.js", 200), ("/api/classes", 200), ("/api/admin/accounts", 401)):
        status = None
        for attempt in range(3):
            try:
                with urlopen(Request(base + route, headers={"Origin": base}), timeout=30) as response:
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
    print("Jeu et panneau admin disponibles ; accès admin anonyme refusé.")


if __name__ == "__main__":
    main()
