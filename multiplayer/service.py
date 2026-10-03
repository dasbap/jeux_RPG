import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from jeuxRPG._class.character import Character
from .clock import GameClock
from . import tutorial


class GameError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GameService:
    classes = ("Knight", "Mage", "Archer", "Priest", "Necromancien")
    cooldown = 3.6
    match_duration = 3 * 300.0
    lobby_duration = 3 * 600.0

    def __init__(self, database=".data/multiplayer.sqlite3", clock=None, random_source=None):
        self.random = random_source or secrets.SystemRandom().random
        path = Path(database)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError("La base ne peut pas être un lien symbolique")
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=10)
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
                scope TEXT NOT NULL, external_id TEXT, name TEXT NOT NULL,
                class_name TEXT NOT NULL, hp INTEGER NOT NULL, damage INTEGER NOT NULL,
                UNIQUE(scope, external_id)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, owner TEXT NOT NULL REFERENCES players(id),
                invite_hash TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
                revision INTEGER NOT NULL, deadline REAL NOT NULL, winner TEXT,
                created REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS members (
                session_id TEXT NOT NULL REFERENCES sessions(id),
                player_id TEXT NOT NULL REFERENCES players(id), hp INTEGER NOT NULL,
                ready_at REAL NOT NULL DEFAULT 0, PRIMARY KEY(session_id, player_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id),
                game_time REAL NOT NULL, message TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts (
                player_id TEXT NOT NULL REFERENCES players(id), request_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, response TEXT NOT NULL,
                PRIMARY KEY(player_id, request_id)
            );
            CREATE INDEX IF NOT EXISTS member_player ON members(player_id);
            CREATE INDEX IF NOT EXISTS session_events ON events(session_id, id);
            CREATE TABLE IF NOT EXISTS tutorials (
                session_id TEXT PRIMARY KEY REFERENCES sessions(id), data TEXT NOT NULL
            );
        """)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('epoch_wall', ?)", (str(time.time()),))
        epoch = float(self.db.execute("SELECT value FROM meta WHERE key='epoch_wall'").fetchone()[0])
        checkpoint = self.db.execute("SELECT value FROM meta WHERE key='last_game'").fetchone()
        anchor_row = self.db.execute("SELECT value FROM meta WHERE key='epoch_game'").fetchone()
        ratio_row = self.db.execute("SELECT value FROM meta WHERE key='clock_ratio'").fetchone()
        anchor = float(anchor_row[0]) if anchor_row else 0
        if checkpoint and (not ratio_row or float(ratio_row[0]) != GameClock.ratio):
            epoch = time.time()
            anchor = float(checkpoint[0])
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('epoch_wall', ?)", (str(epoch),))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('epoch_game', ?)", (str(anchor),))
        self.db.execute("INSERT OR REPLACE INTO meta VALUES ('clock_ratio', ?)", (str(GameClock.ratio),))
        self.clock = clock or GameClock(epoch, epoch_game=anchor, minimum_game=float(checkpoint[0]) if checkpoint else 0)

    def close(self):
        with self._lock:
            self.db.close()

    def tick(self):
        with self._transaction():
            now = self._now()
            self._expire(now)
            rows = self.db.execute("SELECT t.session_id, t.data FROM tutorials t JOIN sessions s ON s.id=t.session_id WHERE s.state='running'").fetchall()
            for row in rows:
                party = json.loads(row["data"])
                before = json.dumps(party, sort_keys=True)
                messages = tutorial.advance(party, now, self.random)
                if json.dumps(party, sort_keys=True) != before:
                    self.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
                    self.db.execute("UPDATE sessions SET revision=revision+1, state=? WHERE id=?", ("finished" if party["step"] == "complete" and not party.get("battle") and not party.get("transit") else "running", row["session_id"]))
                    for message in messages:
                        self._event(row["session_id"], now, message)

    @contextmanager
    def _transaction(self):
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def _now(self):
        now = self.clock.now()
        if not math.isfinite(now) or now < 0:
            raise RuntimeError("Horloge invalide")
        checkpoint = self.db.execute("SELECT value FROM meta WHERE key='last_game'").fetchone()
        now = max(now, float(checkpoint[0]) if checkpoint else 0)
        self.db.execute("INSERT INTO meta VALUES ('last_game', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(now),))
        return now

    @staticmethod
    def _name(value):
        if not isinstance(value, str):
            raise GameError("invalid_name", "Le nom doit être un texte.")
        name = unicodedata.normalize("NFC", value).strip()
        if not 1 <= len(name) <= 32 or any(unicodedata.category(c).startswith("C") for c in name):
            raise GameError("invalid_name", "Le nom doit contenir 1 à 32 caractères sans caractères de contrôle.")
        return name

    def _register(self, name, class_name, scope, external_id=None):
        name = self._name(name)
        if class_name not in self.classes:
            raise GameError("invalid_class", "Choisissez une classe jouable.")
        if self.db.execute("SELECT COUNT(*) FROM players").fetchone()[0] >= 1000:
            raise GameError("capacity", "Capacité du POC atteinte.", 429)
        player_id = secrets.token_hex(16)
        token = secrets.token_urlsafe(32)
        character = Character.create(class_name, player_id, name)
        damage = max(8, min(25, 8 + max(character.force.value, character.intelligence.value, character.sagesse.value) // 4))
        hp = max(80, min(150, character.hp.value))
        self.db.execute("INSERT INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (player_id, digest(token), scope, external_id, name, class_name, hp, damage))
        return {"token": token, "player": {"id": player_id, "name": name, "class_name": class_name, "max_hp": hp, "damage": damage}}

    def register(self, name, class_name):
        with self._transaction():
            return self._register(name, class_name, "local")

    def _authenticate(self, token):
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise GameError("unauthorized", "Identité invalide.", 401)
        player = self.db.execute("SELECT * FROM players WHERE token_hash=?", (digest(token),)).fetchone()
        if player is None:
            raise GameError("unauthorized", "Identité invalide.", 401)
        return player

    def _active(self, player_id):
        return self.db.execute("""SELECT s.* FROM sessions s JOIN members m ON m.session_id=s.id
            WHERE m.player_id=? AND s.state IN ('lobby', 'running')""", (player_id,)).fetchone()

    def _event(self, session_id, now, message):
        self.db.execute("INSERT INTO events(session_id, game_time, message) VALUES (?, ?, ?)", (session_id, now, message))
        self.db.execute("DELETE FROM events WHERE session_id=? AND id NOT IN (SELECT id FROM events WHERE session_id=? ORDER BY id DESC LIMIT 100)", (session_id, session_id))

    def _expire(self, now):
        due = self.db.execute("SELECT id FROM sessions WHERE state IN ('lobby','running') AND deadline<=? AND id NOT IN (SELECT session_id FROM tutorials)", (now,)).fetchall()
        for row in due:
            self.db.execute("UPDATE sessions SET state='finished', winner=NULL, revision=revision+1 WHERE id=?", (row[0],))
            self._event(row[0], now, "Session expirée : aucun vainqueur.")

    def _session(self, player, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{32}", session_id):
            raise GameError("not_found", "Session introuvable.", 404)
        session = self.db.execute("""SELECT s.* FROM sessions s JOIN members m ON m.session_id=s.id
            WHERE s.id=? AND s.scope=? AND m.player_id=?""", (session_id, player["scope"], player["id"])).fetchone()
        if session is None:
            raise GameError("not_found", "Session introuvable.", 404)
        return session

    def _snapshot(self, player, session, now):
        members = self.db.execute("""SELECT p.id, p.name, p.class_name, p.hp AS max_hp, p.damage,
            m.hp, m.ready_at FROM members m JOIN players p ON p.id=m.player_id
            WHERE m.session_id=? ORDER BY p.id""", (session["id"],)).fetchall()
        result = {
            "id": session["id"], "state": session["state"], "revision": session["revision"],
            "owner": session["owner"], "winner": session["winner"], "me": player["id"],
            "game_time": now, "ratio": GameClock.ratio,
            "remaining_real_seconds": max(0, session["deadline"] - now) / GameClock.ratio,
            "players": [{**dict(m), "cooldown_real_seconds": max(0, m["ready_at"] - now) / GameClock.ratio} for m in members],
            "events": [dict(e) for e in self.db.execute("SELECT id, game_time, message FROM events WHERE session_id=? ORDER BY id", (session["id"],))],
        }
        adventure = self.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()
        if adventure:
            result["tutorial"] = tutorial.view(json.loads(adventure[0]), player["id"], now)
        return result

    def state(self, token, session_id=None):
        with self._transaction():
            player = self._authenticate(token)
            now = self._now()
            self._expire(now)
            if session_id is not None:
                return self._snapshot(player, self._session(player, session_id), now)
            session = self._active(player["id"])
            if session is None:
                session = self.db.execute("""SELECT s.* FROM sessions s JOIN members m ON m.session_id=s.id
                    JOIN tutorials t ON t.session_id=s.id WHERE m.player_id=?
                    ORDER BY s.created DESC LIMIT 1""", (player["id"],)).fetchone()
            return {"player": {"id": player["id"], "name": player["name"], "class_name": player["class_name"]},
                    "game_time": now, "ratio": GameClock.ratio,
                    "session": self._snapshot(player, session, now) if session else None}

    def command(self, token, request_id, action, **params):
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
            raise GameError("invalid_request", "Identifiant de commande invalide.")
        allowed = {"create": set(), "join": {"invite"}, "start": {"session_id", "revision"},
                   "attack": {"session_id", "revision"}, "leave": {"session_id", "revision"},
                   "tutorial": set(), "explore": {"session_id", "revision"},
                   "strike": {"session_id", "revision", "target"}, "rest": {"session_id", "revision"},
                   "skill": {"session_id", "revision", "skill_name", "target"},
                   "travel": {"session_id", "revision", "destination"},
                   "move": {"session_id", "revision", "destination"},
                   "talk": {"session_id", "revision", "npc"},
                   "craft": {"session_id", "revision", "recipe"},
                   "upgrade": {"session_id", "revision", "recipe"},
                   "battle_move": {"session_id", "revision", "x", "y", "path"},
                   "hide": {"session_id", "revision"},
                   "harvest": {"session_id", "revision", "target"},
                   "leave_battle": {"session_id", "revision"}}
        if not isinstance(action, str) or action not in allowed or (set(params) != allowed[action] and not (action == "attack" and set(params) == allowed[action] | {"target"})):
            raise GameError("invalid_command", "Commande ou paramètres invalides.")
        if "revision" in params and (type(params["revision"]) is not int or params["revision"] < 0):
            raise GameError("invalid_revision", "Version invalide.")
        try:
            fingerprint = digest(json.dumps([action, params], sort_keys=True, allow_nan=False))
        except (TypeError, ValueError):
            raise GameError("invalid_command", "Paramètres invalides.") from None
        with self._transaction():
            player = self._authenticate(token)
            old = self.db.execute("SELECT * FROM receipts WHERE player_id=? AND request_id=?", (player["id"], request_id)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise GameError("request_conflict", "Cet identifiant correspond à une autre commande.", 409)
                return json.loads(old["response"])
            now = self._now()
            self._expire(now)
            if self.db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] >= 100000:
                raise GameError("capacity", "Capacité du journal des commandes atteinte.", 429)
            result = self._execute(player, action, params, now)
            self.db.execute("INSERT INTO receipts VALUES (?, ?, ?, ?)", (player["id"], request_id, fingerprint, json.dumps(result)))
            return result

    def _bind_discord(self, guild_id, user_id, name, class_name):
        if not all(isinstance(v, str) and re.fullmatch(r"[0-9]{1,20}", v) for v in (guild_id, user_id)):
            raise GameError("invalid_identity", "Identité Discord invalide.")
        scope = f"discord:{guild_id}"
        with self._transaction():
            existing = self.db.execute("SELECT id FROM players WHERE scope=? AND external_id=?", (scope, user_id)).fetchone()
            if existing is None:
                return self._register(name, class_name, scope, user_id)["token"]
            token = secrets.token_urlsafe(32)
            self.db.execute("UPDATE players SET token_hash=? WHERE id=?", (digest(token), existing["id"]))
            return token

    def _execute(self, player, action, params, now):
        player_id = player["id"]
        if action == "tutorial":
            session = self._active(player_id)
            if session is None:
                created = self._execute(player, "create", {}, now)
                session = self._session(player, created["session"]["id"])
            if session["state"] != "lobby" or session["owner"] != player_id:
                raise GameError("not_ready", "Le créateur peut commencer le tutoriel depuis son salon.", 409)
            players = self.db.execute("SELECT p.* FROM players p JOIN members m ON m.player_id=p.id WHERE m.session_id=?", (session["id"],)).fetchall()
            self.db.execute("INSERT INTO tutorials VALUES (?, ?)", (session["id"], json.dumps(tutorial.new_party(players))))
            self.db.execute("UPDATE sessions SET state='running', revision=revision+1 WHERE id=?", (session["id"],))
            self._event(session["id"], now, "Bienvenue dans la clairière. Le tutoriel peut se jouer seul ou avec un compagnon.")
            return {"session": self._snapshot(player, self._session(player, session["id"]), now)}
        if action in ("explore", "strike", "skill", "rest", "travel", "move", "talk", "craft", "upgrade", "battle_move", "hide", "harvest", "leave_battle"):
            session = self._session(player, params["session_id"])
            if session["state"] != "running" and not (session["state"] == "finished" and self.db.execute("SELECT 1 FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()):
                raise GameError("not_running", "Le tutoriel n'est pas en cours.", 409)
            if session["revision"] != params["revision"]:
                raise GameError("stale_revision", "L'état a changé. Actualisez avant de réessayer.", 409)
            row = self.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()
            if row is None:
                raise GameError("not_tutorial", "Cette session n'est pas un tutoriel.", 409)
            party = json.loads(row[0])
            messages, finished = tutorial.execute(party, player_id, action, params, now, GameError, self.random)
            self.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), session["id"]))
            self.db.execute("UPDATE sessions SET revision=revision+1, state=? WHERE id=?", ("finished" if party["step"] == "complete" and not party.get("battle") and not party.get("transit") else "running", session["id"]))
            for message in messages:
                self._event(session["id"], now, message)
            return {"session": self._snapshot(player, self._session(player, session["id"]), now)}
        if action in ("create", "join") and self._active(player_id):
            raise GameError("already_active", "Quittez votre session actuelle avant d'en rejoindre une autre.", 409)
        if action == "create":
            if self.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] >= 2000:
                raise GameError("capacity", "Capacité des sessions atteinte.", 429)
            session_id = secrets.token_hex(16)
            invite = secrets.token_urlsafe(16)
            self.db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, 'lobby', 1, ?, NULL, ?)",
                            (session_id, player["scope"], player_id, digest(invite), now + self.lobby_duration, now))
            self.db.execute("INSERT INTO members VALUES (?, ?, ?, 0)", (session_id, player_id, player["hp"]))
            self._event(session_id, now, "Salon créé. Partagez l'invitation avec le second joueur.")
            session = self._session(player, session_id)
            return {"session": self._snapshot(player, session, now), "invite": invite}
        if action == "join":
            invite = params["invite"]
            if not isinstance(invite, str) or not 16 <= len(invite) <= 64:
                raise GameError("invalid_invite", "Invitation invalide.", 404)
            session = self.db.execute("SELECT * FROM sessions WHERE invite_hash=? AND scope=? AND state='lobby'", (digest(invite), player["scope"])).fetchone()
            if session is None:
                raise GameError("invalid_invite", "Invitation invalide ou expirée.", 404)
            count = self.db.execute("SELECT COUNT(*) FROM members WHERE session_id=?", (session["id"],)).fetchone()[0]
            if count >= 2:
                raise GameError("full", "Le salon contient déjà deux joueurs.", 409)
            self.db.execute("INSERT INTO members VALUES (?, ?, ?, 0)", (session["id"], player_id, player["hp"]))
            self.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (session["id"],))
            self._event(session["id"], now, f"{player['name']} a rejoint le salon.")
        else:
            session = self._session(player, params["session_id"])
            if action in ("attack", "start") and self.db.execute("SELECT 1 FROM tutorials WHERE session_id=?", (session["id"],)).fetchone():
                raise GameError("not_duel", "Utilisez les actions du tutoriel.", 409)
            if session["state"] == "finished":
                raise GameError("finished", "La session est terminée.", 409)
            if session["revision"] != params["revision"]:
                raise GameError("stale_revision", "L'état a changé. Actualisez avant de réessayer.", 409)
            if action == "start":
                if session["owner"] != player_id:
                    raise GameError("forbidden", "Seul le créateur peut démarrer le duel.", 403)
                count = self.db.execute("SELECT COUNT(*) FROM members WHERE session_id=?", (session["id"],)).fetchone()[0]
                if session["state"] != "lobby" or count != 2:
                    raise GameError("not_ready", "Deux joueurs doivent rejoindre le salon.", 409)
                self.db.execute("UPDATE sessions SET state='running', deadline=?, revision=revision+1 WHERE id=?", (now + self.match_duration, session["id"]))
                self._event(session["id"], now, "Le duel commence. Une action toutes les 1,2 seconde réelle.")
            elif action == "leave":
                opponent = self.db.execute("SELECT player_id FROM members WHERE session_id=? AND player_id<>?", (session["id"], player_id)).fetchone()
                winner = opponent[0] if session["state"] == "running" and opponent else None
                self.db.execute("UPDATE sessions SET state='finished', winner=?, revision=revision+1 WHERE id=?", (winner, session["id"]))
                self._event(session["id"], now, f"{player['name']} quitte la session.")
            elif action == "attack":
                if session["state"] != "running":
                    raise GameError("not_running", "Le duel n'a pas commencé.", 409)
                actor = self.db.execute("SELECT * FROM members WHERE session_id=? AND player_id=?", (session["id"], player_id)).fetchone()
                target = self.db.execute("SELECT * FROM members WHERE session_id=? AND player_id<>?", (session["id"], player_id)).fetchone()
                if actor["hp"] <= 0 or not target or target["hp"] <= 0:
                    raise GameError("invalid_target", "Aucune cible vivante.", 409)
                if "target" in params and params["target"] != target["player_id"]:
                    raise GameError("invalid_target", "Cet adversaire n'est pas une cible valide de votre duel.")
                if actor["ready_at"] > now:
                    raise GameError("cooldown", "Votre attaque n'est pas encore disponible.", 409)
                hp = max(0, target["hp"] - player["damage"])
                self.db.execute("UPDATE members SET hp=? WHERE session_id=? AND player_id=?", (hp, session["id"], target["player_id"]))
                self.db.execute("UPDATE members SET ready_at=? WHERE session_id=? AND player_id=?", (now + self.cooldown, session["id"], player_id))
                self.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (session["id"],))
                self._event(session["id"], now, f"{player['name']} attaque : {min(player['damage'], target['hp'])} dégâts.")
                if hp == 0:
                    self.db.execute("UPDATE sessions SET state='finished', winner=? WHERE id=?", (player_id, session["id"]))
                    self._event(session["id"], now, f"{player['name']} remporte le duel.")
        session = self._session(player, session["id"])
        return {"session": self._snapshot(player, session, now)}
