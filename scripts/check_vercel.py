import ast
import os
from pathlib import Path
import sys
import tomllib


def check(root, environment):
    errors = []
    for name in ("app.py", "multiplayer/realtime.py", "multiplayer/realtime_store.py", "multiplayer/serverless.py", "multiplayer/turso.py", "multiplayer/schema.py", "multiplayer/admin.py", "_class/character.py"):
        path = root / name
        if not path.is_file():
            errors.append(f"Fichier requis absent : {name}")
        else:
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=name)
            except (SyntaxError, UnicodeError):
                errors.append(f"Fichier Python invalide : {name}")
    configuration = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if configuration.get("tool", {}).get("vercel", {}).get("entrypoint") != "app:app":
        errors.append("Entrée WSGI à configurer dans pyproject.toml : tool.vercel.entrypoint = app:app")
    for name in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"):
        if not environment.get(name):
            errors.append(f"Variable Vercel requise absente : {name}")
    if not (environment.get('REDIS_URL') or environment.get('KV_URL')):
        errors.append('REDIS_URL requis : connectez le stockage Redis au projet Vercel jeux-rpg')
    if len(environment.get("RPG_ADMIN_TOKEN", "")) < 32:
        errors.append("RPG_ADMIN_TOKEN requis : secret administrateur distinct de 32 caractères minimum")
    if not (root / "maps" / "world.json").is_file():
        errors.append("Catalogue maps/world.json absent")
    return errors


def main():
    errors = check(Path(__file__).resolve().parent.parent, os.environ)
    if errors:
        print("Déploiement Vercel interrompu :")
        for error in errors:
            print(f"- {error}")
        print("Le serveur local main.py ne remplace pas une entrée WSGI et une base persistante distante.")
        return 1
    print("Fichiers Vercel et variables Turso présents. La connexion distante et le parcours de jeu restent à vérifier sur une preview.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
