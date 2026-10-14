import json
import sqlite3
from urllib.parse import urlsplit

from .catalogue import catalogue
from .distributed import PresenceRegistry
from .service import GameError, GameService


class SoloGame:
    def __init__(self, saved=None):
        self.db = sqlite3.connect(
            ":memory:", isolation_level=None, check_same_thread=False
        )
        self.db.row_factory = sqlite3.Row
        if saved:
            self.db.deserialize(bytes(saved))
        self.service = GameService(
            connection=self.db, log_directory="-", presence_registry=PresenceRegistry()
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS browser_characters(player_id TEXT PRIMARY KEY, token TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS browser_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )

    def selected_token(self):
        row = self.db.execute(
            "SELECT value FROM browser_settings WHERE key='selected'"
        ).fetchone()
        return row[0] if row else ""

    def characters(self):
        rows = self.db.execute(
            "SELECT p.id,p.name,p.class_name,c.token FROM browser_characters c JOIN players p ON p.id=c.player_id ORDER BY p.name,p.id"
        ).fetchall()
        token = self.selected_token()
        selected = next((row["id"] for row in rows if row["token"] == token), None)
        return {
            "account": {"id": "browser-solo", "username": "Solo sur cet appareil"},
            "characters": [
                {"id": row["id"], "name": row["name"], "class_name": row["class_name"]}
                for row in rows
            ],
            "selected": selected,
            "token": token,
        }

    def choose(self, body):
        action = body.get("action")
        if action == "create":
            if self.db.execute(
                "SELECT 1 FROM browser_characters c JOIN players p ON p.id=c.player_id WHERE p.class_name=?",
                (body.get("class_name"),),
            ).fetchone():
                raise GameError(
                    "character_exists",
                    "Vous avez déjà un personnage solo de cette classe.",
                )
            result = self.service.register(body.get("name"), body.get("class_name"))
            token = result["token"]
            self.db.execute(
                "INSERT INTO browser_characters VALUES(?,?)",
                (result["player"]["id"], token),
            )
        elif action == "select":
            row = self.db.execute(
                "SELECT token FROM browser_characters WHERE player_id=?",
                (body.get("player_id"),),
            ).fetchone()
            if row is None:
                raise GameError("not_found", "Personnage solo introuvable.", 404)
            token = row[0]
        else:
            raise GameError("invalid_action", "Choix de personnage invalide.")
        self.db.execute(
            "INSERT INTO browser_settings VALUES('selected',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (token,),
        )
        return self.characters()

    def dispatch(self, path, body=None, token=""):
        path = urlsplit(path).path
        if path == "/api/classes":
            return catalogue()
        if path == "/api/account/me":
            return self.characters()
        if path == "/api/account/character":
            return self.choose(body or {})
        if path == "/api/account/logout":
            self.db.execute("DELETE FROM browser_settings WHERE key='selected'")
            return {"ok": True}
        if not token or token != self.selected_token():
            raise GameError("unauthorized", "Choisissez votre personnage solo.", 401)
        player = self.service._authenticate(token)
        active = self.service._active(player["id"])
        if active:
            self.service.tick(active["id"])
        if path == "/api/state":
            return self.service.state(token)
        if path.startswith("/api/sessions/"):
            return self.service.state(token, session_id=path.rsplit("/", 1)[-1])[
                "session"
            ]
        if path == "/api/commands":
            body = body or {}
            if body.get("action") in ("create", "join", "start", "attack"):
                raise GameError(
                    "online_required", "Cette action est disponible en mode en ligne."
                )
            return self.service.command(
                token,
                body.get("request_id"),
                body.get("action"),
                **body.get("params", {}),
            )
        raise GameError(
            "online_required", "Cette fonction est disponible en mode en ligne.", 404
        )

    def request(self, message):
        try:
            payload = self.dispatch(
                message["path"], message.get("body"), message.get("token", "")
            )
            return json.dumps({"status": 200, "body": payload}, ensure_ascii=False)
        except GameError as error:
            return json.dumps(
                {
                    "status": error.status,
                    "body": {"error": error.code, "message": str(error)},
                },
                ensure_ascii=False,
            )

    def save(self):
        return self.db.serialize()

    def close(self):
        self.service.close()
