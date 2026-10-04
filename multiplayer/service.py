import hashlib
import json
import logging
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from collections import OrderedDict, deque
from contextlib import contextmanager
from pathlib import Path

from jeuxRPG._class.character import Character
from jeuxRPG._class.res.character.class_models import playable
from .clock import GameClock
from .network_log import create_chat_logger
from . import tutorial


class GameError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def world_context(party):
    return digest(json.dumps([party.get("position"), party.get("step"), party.get("quest"), party.get("encounter_number", 0),
                              bool(party.get("battle")), (party.get("transit") or {}).get("destination"), party.get("journey", [])]))


class GameService:
    from jeuxRPG._class.res.character.class_models import playable
    classes = tuple(playable())
    cooldown = 3.6
    match_duration = 3 * 300.0
    lobby_duration = GameClock.ratio * 1800.0

    def __init__(self, database=".data/multiplayer.sqlite3", clock=None, random_source=None, log_directory=None):
        from .skill_catalog import install
        from .content import DATA
        from .map_building import MOBS
        from .content import validate_references
        from .fields import MAPS
        validate_references(DATA, MOBS, MAPS)
        extra_classes = install(DATA,MOBS)
        self.classes = (*playable(DATA.get('templates')), *extra_classes)
        self._tick_errors = {}
        self._prepared_views = OrderedDict()
        self._view_errors = {}
        self.random = random_source or secrets.SystemRandom().random
        path = Path(database)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError("La base ne peut pas être un lien symbolique")
        self._lock = threading.RLock()
        self._chat_connections = {}
        self._chat_sent = {}
        self._chat_cleanup_at = 0
        self.chat_log = create_chat_logger(log_directory or path.parent / ".logs")
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=10)
        os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS presence (player_id TEXT PRIMARY KEY, seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, session_id TEXT, player_id TEXT NOT NULL, name TEXT NOT NULL, message TEXT NOT NULL, sent REAL NOT NULL);

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
        self._last_game = float(checkpoint[0]) if checkpoint else 0
        with self._transaction():
            for row in self.db.execute("SELECT id,scope,player_id,name,message,sent FROM chat WHERE session_id IS NULL"):
                self._log_global_chat(dict(row), "legacy_global_chat")
            self.db.execute("DELETE FROM chat WHERE session_id IS NULL")

    def close(self):
        with self._lock:
            self.db.close()
            for handler in self.chat_log.handlers:
                handler.close()

    def tick(self):
        with self._transaction():
            now = self._now()
            self._expire(now)
            rows = self.db.execute("SELECT t.session_id FROM tutorials t JOIN sessions s ON s.id=t.session_id WHERE s.state='running'").fetchall()
            active = {row["session_id"] for row in rows}
            self._tick_errors = {key: value for key, value in self._tick_errors.items() if key in active}
            self._view_errors = {key: value for key, value in self._view_errors.items() if key[0] in active}
        for row in rows:
            with self._transaction():
                current = self.db.execute("SELECT t.data FROM tutorials t JOIN sessions s ON s.id=t.session_id WHERE t.session_id=? AND s.state='running'", (row["session_id"],)).fetchone()
                if current is None:
                    continue
                now = self._now()
                try:
                    party = json.loads(current["data"])
                    before = json.dumps(party, sort_keys=True)
                    messages = tutorial.advance(party, now, self.random)
                except Exception:
                    last = self._tick_errors.get(row["session_id"], -60)
                    if time.monotonic() - last >= 60:
                        logging.getLogger(__name__).exception("Simulation interrompue pour la session %s ; les autres sessions restent actives.", row["session_id"])
                        self._tick_errors[row["session_id"]] = time.monotonic()
                    continue
                self._tick_errors.pop(row["session_id"], None)
                if json.dumps(party, sort_keys=True) != before:
                    self.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
                    self.db.execute("UPDATE sessions SET revision=revision+1, state=? WHERE id=?", ("finished" if party["step"] == "complete" and not party.get("battle") and not party.get("transit") else "running", row["session_id"]))
                    for message in messages:
                        self._event(row["session_id"], now, message)
                revision = self.db.execute("SELECT revision FROM sessions WHERE id=?", (row["session_id"],)).fetchone()[0]
                for player_id in party["characters"]:
                    key = (row["session_id"], player_id)
                    try:
                        view = tutorial.view(party, player_id, now)
                    except Exception:
                        self._prepared_views.pop(key, None)
                        if time.monotonic() - self._view_errors.get(key, -60) >= 60:
                            logging.getLogger(__name__).exception("Préparation de vue interrompue pour la session %s ; les autres vues restent actives.", row["session_id"])
                            self._view_errors[key] = time.monotonic()
                        continue
                    self._view_errors.pop(key, None)
                    view["world_context"] = world_context(party)
                    self._prepared_views[key] = (revision, now, json.dumps(view, ensure_ascii=False, separators=(",", ":")))
                    self._prepared_views.move_to_end(key)
                while len(self._prepared_views) > 256:
                    self._prepared_views.popitem(last=False)
            time.sleep(0)

    @contextmanager
    def _transaction(self):
        with self._lock:
            nested = self.db.in_transaction
            self.db.execute("SAVEPOINT rpg_command" if nested else "BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("RELEASE SAVEPOINT rpg_command" if nested else "COMMIT")
            except BaseException:
                if nested:
                    self.db.execute("ROLLBACK TO SAVEPOINT rpg_command")
                    self.db.execute("RELEASE SAVEPOINT rpg_command")
                else:
                    self.db.execute("ROLLBACK")
                raise

    def _now(self, persist=True):
        now = self.clock.now()
        if not math.isfinite(now) or now < 0:
            raise RuntimeError("Horloge invalide")
        checkpoint = self.db.execute("SELECT value FROM meta WHERE key='last_game'").fetchone()
        now = max(now, self._last_game, float(checkpoint[0]) if checkpoint else 0)
        self._last_game = now
        if persist:
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

    def _snapshot(self, player, session, now, prepared=False, compact=False):
        if compact:
            return {"id": session["id"], "state": session["state"], "revision": session["revision"], "owner": session["owner"], "me": player["id"], "acknowledged": True}
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
            cached = self._prepared_views.get((session["id"], player["id"])) if prepared else None
            if cached and cached[0] == session["revision"] and 0 <= now - cached[1] <= .6:
                result["tutorial"] = json.loads(cached[2])
            else:
                party = json.loads(adventure[0])
                result["tutorial"] = tutorial.view(party, player["id"], now)
                result["tutorial"]["world_context"] = world_context(party)
        return result

    def state(self, token, session_id=None, prepared=False, chat_connection=None):
        with self._transaction():
            player = self._authenticate(token)
            now = self._now(persist=False)
            self._touch_chat(player, now, chat_connection)
            self._expire(now)
            seen = self.db.execute("SELECT seen FROM presence WHERE player_id=?", (player["id"],)).fetchone()
            if seen is None or now - seen[0] >= 10 * GameClock.ratio:
                self.db.execute("INSERT INTO presence VALUES(?,?) ON CONFLICT(player_id) DO UPDATE SET seen=excluded.seen", (player["id"], now))
            if session_id is not None:
                return self._snapshot(player, self._session(player, session_id), now, prepared)
            session = self._active(player["id"])
            if session is None:
                session = self.db.execute("""SELECT s.* FROM sessions s JOIN members m ON m.session_id=s.id
                    JOIN tutorials t ON t.session_id=s.id WHERE m.player_id=?
                    ORDER BY s.created DESC LIMIT 1""", (player["id"],)).fetchone()
            return {"player": {"id": player["id"], "name": player["name"], "class_name": player["class_name"]},
                    "game_time": now, "ratio": GameClock.ratio,
                    "chat": self.chat_view(player, now, session["id"] if session else None, chat_connection),
                    "session": self._snapshot(player, session, now, prepared) if session else None}

    def configure_chat_log(self, directory):
        with self._lock:
            destination = Path(directory).resolve() / "chat.log"
            if Path(self.chat_log.handlers[0].baseFilename) != destination:
                for handler in self.chat_log.handlers:
                    handler.close()
                self.chat_log = create_chat_logger(directory)

    def _log_global_chat(self, item, event="global_chat"):
        self.chat_log.info(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "event": event, **item}, ensure_ascii=False))

    def _touch_chat(self, player, now, connection=None):
        if connection is not None and (not isinstance(connection, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", connection)):
            raise GameError("invalid_chat_connection", "Connexion de chat invalide.")
        if now >= self._chat_cleanup_at:
            self._chat_connections = {key: value for key, value in self._chat_connections.items() if now - value["seen"] < 60 * GameClock.ratio}
            self._chat_sent = {key: value for key, value in self._chat_sent.items() if now - value < 60 * GameClock.ratio}
            self._chat_cleanup_at = now + GameClock.ratio
        key = (player["id"], connection or "default")
        stream = self._chat_connections.get(key)
        if stream is None or now - stream["seen"] >= 60 * GameClock.ratio:
            owned = [key for key in self._chat_connections if key[0] == player["id"]]
            if len(owned) >= 8:
                oldest = min(owned, key=lambda key: self._chat_connections[key]["seen"])
                del self._chat_connections[oldest]
            if key not in self._chat_connections and len(self._chat_connections) >= 2048:
                raise GameError("chat_capacity", "Trop de connexions de chat actives.", 429)
            stream = {"scope": player["scope"], "seen": now, "messages": deque(maxlen=50)}
            self._chat_connections[key] = stream
        stream["seen"] = now
        return stream

    def chat_view(self, player, now, session_id=None, chat_connection=None):
        stream = self._touch_chat(player, now, chat_connection)
        online = [dict(row) for row in self.db.execute("SELECT p.id,p.name FROM players p JOIN presence o ON o.player_id=p.id WHERE p.scope=? AND o.seen>=? ORDER BY p.name", (player["scope"], now - 60 * GameClock.ratio))]
        group = [dict(row) for row in reversed(self.db.execute("SELECT id,name,message FROM chat WHERE scope=? AND session_id=? ORDER BY id DESC LIMIT 50", (player["scope"], session_id)).fetchall())] if session_id else []
        return {"online": online, "global": [dict(item) for item in stream["messages"]], "group": group}

    def send_chat(self, token, channel, message, session_id=None, chat_connection=None):
        if channel not in ("global", "group") or not isinstance(message, str) or not 1 <= len(message.strip()) <= 400 or any(ord(c) < 32 and c not in "\n\t" for c in message):
            raise GameError("invalid_chat", "Message invalide (1 à 400 caractères).")
        with self._transaction():
            player = self._authenticate(token)
            now = self._now(persist=False)
            if channel == "group":
                if not isinstance(session_id, str):
                    raise GameError("not_in_group", "Rejoignez un groupe avant de discuter.", 409)
                self._session(player, session_id)
            else:
                session_id = None
            self._touch_chat(player, now, chat_connection)
            saved = self.db.execute("SELECT sent FROM chat WHERE player_id=? ORDER BY id DESC LIMIT 1", (player["id"],)).fetchone()
            last = max(self._chat_sent.get(player["id"], -math.inf), saved[0] if saved else -math.inf)
            if now - last < GameClock.ratio:
                raise GameError("chat_rate_limit", "Attendez une seconde entre deux messages.", 429)
            if channel == "global":
                item = {"id": uuid.uuid4().hex, "name": player["name"], "message": message.strip()}
                self._log_global_chat({**item, "scope": player["scope"], "player_id": player["id"]})
                for stream in self._chat_connections.values():
                    if stream["scope"] == player["scope"] and now - stream["seen"] < 60 * GameClock.ratio:
                        stream["messages"].append(item)
            else:
                self.db.execute("INSERT INTO chat(scope,session_id,player_id,name,message,sent) VALUES(?,?,?,?,?,?)", (player["scope"], session_id, player["id"], player["name"], message.strip(), now))
                self.db.execute("DELETE FROM chat WHERE id NOT IN (SELECT id FROM chat WHERE scope=? AND session_id=? ORDER BY id DESC LIMIT 200) AND scope=? AND session_id=?", (player["scope"], session_id, player["scope"], session_id))
            self._chat_sent[player["id"]] = now
            return self.chat_view(player, now, session_id, chat_connection)

    def command(self, token, request_id, action, _compact=False, **params):
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
            raise GameError("invalid_request", "Identifiant de commande invalide.")
        allowed = {"create": set(), "join": {"invite"}, "start": {"session_id", "revision"},
                   "attack": {"session_id", "revision"}, "leave": {"session_id", "revision"},
                   "tutorial": {"field_mode"}, "enter_zone": {"session_id", "revision"}, "explore": {"session_id", "revision", "world_context"},
                   "strike": {"session_id", "revision", "target"}, "rest": {"session_id", "revision"},
                   "skill": {"session_id", "revision", "skill_name", "target"},
                   "travel": {"session_id", "revision", "destination", "world_context"},
                   "move": {"session_id", "revision", "destination", "world_context"},
                   "talk": {"session_id", "revision", "npc"},
                   "craft": {"session_id", "revision", "recipe"},
                   "upgrade": {"session_id", "revision", "recipe"},
                   "battle_move": {"session_id", "revision", "encounter", "x", "y", "path"},
                   "hide": {"session_id", "revision"},
                   "harvest": {"session_id", "revision", "target"},
                   "control_units": {"session_id", "revision", "units"},
                   "unit_skill": {"session_id", "revision", "units", "skill_name", "target"},
                   "unit_order": {"session_id", "revision", "encounter", "units", "order", "target", "paths"},
                   "leave_battle": {"session_id", "revision"}}
        if not isinstance(action, str) or action not in allowed or (set(params) != allowed[action] and not (action in ("battle_move", "unit_order") and set(params) == allowed[action] - {"encounter"}) and not (action in ("move", "travel") and set(params) in (allowed[action] | {"paths"}, (allowed[action] - {"world_context"}) | {"paths"})) and not (action in ("move", "travel", "explore") and set(params) == allowed[action] - {"world_context"}) and not (action == "tutorial" and not params) and not (action == "attack" and set(params) == allowed[action] | {"target"})):
            raise GameError("invalid_command", "Commande ou paramètres invalides.")
        if "field_mode" in params and type(params["field_mode"]) is not bool:
            raise GameError("invalid_command", "Mode de zone invalide.")
        if "encounter" in params and (type(params["encounter"]) is not int or params["encounter"] < 1):
            raise GameError("invalid_encounter", "Combat invalide.")
        if "revision" in params and (type(params["revision"]) is not int or params["revision"] < 0):
            raise GameError("invalid_revision", "Version invalide.")
        try:
            fingerprint = digest(json.dumps([action, params, "compact"] if _compact else [action, params], sort_keys=True, allow_nan=False))
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
            result = self._execute(player, action, params, now, compact=True) if _compact else self._execute(player, action, params, now)
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

    def _execute(self, player, action, params, now, compact=False):
        player_id = player["id"]
        if action == "tutorial":
            session = self._active(player_id)
            if session is None:
                created = self._execute(player, "create", {}, now)
                session = self._session(player, created["session"]["id"])
            if session["state"] != "lobby" or session["owner"] != player_id:
                raise GameError("not_ready", "Le créateur peut commencer le tutoriel depuis son salon.", 409)
            players = self.db.execute("SELECT p.* FROM players p JOIN members m ON m.player_id=p.id WHERE m.session_id=?", (session["id"],)).fetchall()
            party = tutorial.new_party(players)
            if params.get("field_mode"):
                tutorial.fields.start(party, now)
            self.db.execute("INSERT INTO tutorials VALUES (?, ?)", (session["id"], json.dumps(party)))
            self.db.execute("UPDATE sessions SET state='running', revision=revision+1 WHERE id=?", (session["id"],))
            self._event(session["id"], now, "Bienvenue dans la clairière. Le tutoriel peut se jouer seul ou avec un compagnon.")
            return {"session": self._snapshot(player, self._session(player, session["id"]), now, compact=compact)}
        if action in ("enter_zone", "explore", "strike", "skill", "rest", "travel", "move", "talk", "craft", "upgrade", "battle_move", "hide", "harvest", "leave_battle", "control_units", "unit_order", "unit_skill"):
            session = self._session(player, params["session_id"])
            if session["state"] != "running" and not (session["state"] == "finished" and self.db.execute("SELECT 1 FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()):
                raise GameError("not_running", "Le tutoriel n'est pas en cours.", 409)
            row = self.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()
            if row is None:
                raise GameError("not_tutorial", "Cette session n'est pas un tutoriel.", 409)
            party = json.loads(row[0])
            movement = action == "battle_move" or action == "unit_order" and params.get("order") == "move"
            same_encounter = type(params.get("encounter")) is int and params["encounter"] == party.get("encounter_number") and party.get("battle")
            world_action = action in ("move", "travel", "explore") and isinstance(params.get("world_context"), str) and params["world_context"] == world_context(party)
            if session["revision"] != params["revision"] and not ((movement and same_encounter or world_action) and params["revision"] < session["revision"]):
                raise GameError("stale_revision", "L'état a changé. Actualisez avant de réessayer.", 409)
            if "encounter" in params and not same_encounter:
                raise GameError("stale_encounter", "Ce combat n’est plus actif.", 409)
            messages, finished = tutorial.execute(party, player_id, action, params, now, GameError, self.random)
            self.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), session["id"]))
            self.db.execute("UPDATE sessions SET revision=revision+1, state=? WHERE id=?", ("finished" if party["step"] == "complete" and not party.get("battle") and not party.get("transit") else "running", session["id"]))
            for message in messages:
                self._event(session["id"], now, message)
            return {"session": self._snapshot(player, self._session(player, session["id"]), now, compact=compact)}
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
            return {"session": self._snapshot(player, session, now, compact=compact), "invite": invite}
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
        return {"session": self._snapshot(player, session, now, compact=compact)}
