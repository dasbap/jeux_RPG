import hmac
import io
import json
import os
import sqlite3
import threading
import time
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from . import admin
from .network_log import create_logger
from .server import Handler
from .service import GameError, GameService, digest
from .turso import TursoConnection


class DatabaseLimiter:
    def __init__(self, service):
        self.service = service

    def accept(self, key, limit):
        now = time.time()
        key = digest(json.dumps(key))
        with self.service._transaction():
            row = self.service.db.execute("SELECT window,count FROM request_limits WHERE key=?", (key,)).fetchone()
            start, count = (row[0], row[1]) if row and now - row[0] < 60 else (now, 0)
            self.service.db.execute("INSERT INTO request_limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET window=excluded.window,count=excluded.count", (key, start, min(count + 1, limit + 1)))
            self.service.db.execute("DELETE FROM request_limits WHERE window<?", (now - 120,))
            return count < limit


class DirectCommands:
    def __init__(self, service):
        self.service = service

    def execute(self, token, request_id, action, params, compact=False):
        return self.service.command(token, request_id, action, _compact=compact, **params)


class RequestHandler(Handler):
    def _respond(self, status, payload, content_type="application/json; charset=utf-8"):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if isinstance(payload, (dict, list)) else payload
        self.result = (status, body, content_type)


class RemoteGameService(GameService):
    def _touch_chat(self, player, now, connection=None):
        import re
        if connection is not None and (not isinstance(connection, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", connection)):
            raise GameError("invalid_chat_connection", "Connexion de chat invalide.")
        key = (player["id"], connection or "default")
        row = self.db.execute("SELECT seen,after_id FROM chat_streams WHERE player_id=? AND connection=?", key).fetchone()
        if row is None or now - row[0] >= 60 * self.clock.ratio:
            self.db.execute("DELETE FROM chat_streams WHERE seen<?", (now - 60 * self.clock.ratio,))
            if self.db.execute("SELECT COUNT(*) FROM chat_streams WHERE player_id=?", (player["id"],)).fetchone()[0] >= 8:
                raise GameError("chat_capacity", "Trop de connexions de chat.", 429)
            after = self.db.execute("SELECT COALESCE(MAX(id),0) FROM chat").fetchone()[0]
        else:
            after = row[1]
        self.db.execute("INSERT INTO chat_streams VALUES(?,?,?,?) ON CONFLICT(player_id,connection) DO UPDATE SET seen=excluded.seen,after_id=excluded.after_id", (*key, now, after))
        return {"after_id": after}

    def chat_view(self, player, now, session_id=None, chat_connection=None):
        stream = self._touch_chat(player, now, chat_connection)
        online = [dict(row) for row in self.db.execute("SELECT p.id,p.name FROM players p JOIN presence o ON p.id=o.player_id LEFT JOIN account_status a ON a.player_id=p.id WHERE p.scope=? AND o.seen>=? AND COALESCE(a.suspended,0)=0 ORDER BY p.name", (player["scope"], now - 60 * self.clock.ratio))]
        global_messages = [dict(row) for row in reversed(self.db.execute("SELECT id,name,message FROM chat WHERE scope=? AND session_id IS NULL AND id>? ORDER BY id DESC LIMIT 50", (player["scope"], stream["after_id"])).fetchall())]
        group = [dict(row) for row in reversed(self.db.execute("SELECT id,name,message FROM chat WHERE scope=? AND session_id=? ORDER BY id DESC LIMIT 50", (player["scope"], session_id)).fetchall())] if session_id else []
        return {"online": online, "global": global_messages, "group": group}

    def send_chat(self, token, channel, message, session_id=None, chat_connection=None):
        if channel != "global":
            return super().send_chat(token, channel, message, session_id, chat_connection)
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= 400 or any(ord(c) < 32 and c not in "\n\t" for c in message):
            raise GameError("invalid_chat", "Message invalide.")
        with self._transaction():
            player = self._authenticate(token)
            now = self._now(persist=False)
            self._touch_chat(player, now, chat_connection)
            last = self.db.execute("SELECT sent FROM chat WHERE player_id=? ORDER BY id DESC LIMIT 1", (player["id"],)).fetchone()
            if last and now - last[0] < self.clock.ratio:
                raise GameError("chat_rate_limit", "Attendez une seconde entre deux messages.", 429)
            self.db.execute("INSERT INTO chat(scope,session_id,player_id,name,message,sent) VALUES(?,NULL,?,?,?,?)", (player["scope"], player["id"], player["name"], message.strip(), now))
            self.db.execute("DELETE FROM chat WHERE scope=? AND session_id IS NULL AND id NOT IN (SELECT id FROM chat WHERE scope=? AND session_id IS NULL ORDER BY id DESC LIMIT 200)", (player["scope"], player["scope"]))
            return self.chat_view(player, now, chat_connection=chat_connection)


class Application:
    def __init__(self, service_factory=None, environment=None):
        self.environment = os.environ if environment is None else environment
        self.factory = service_factory
        self.initialized = False
        self.lock = threading.Lock()

    def service(self):
        if self.factory:
            return self.factory()
        connection = TursoConnection(self.environment.get("TURSO_DATABASE_URL", ""), self.environment.get("TURSO_AUTH_TOKEN", ""))
        try:
            with self.lock:
                service = RemoteGameService(connection=connection, log_directory="-", initialize_schema=not self.initialized)
                self.initialized = True
            return service
        except BaseException:
            connection.close()
            raise

    def __call__(self, environ, start_response):
        service = None
        logger = create_logger("-")
        status, payload, mime = 503, {"error": "unavailable", "message": "Service indisponible."}, "application/json; charset=utf-8"
        try:
            path = environ.get("PATH_INFO", "/")
            method = environ.get("REQUEST_METHOD", "GET")
            if method not in ("GET", "POST"):
                raise GameError("method_not_allowed", "Méthode non autorisée.", 405)
            host = environ.get("HTTP_HOST", "")
            allowed = set(filter(None, (self.environment.get("VERCEL_URL"), self.environment.get("VERCEL_PROJECT_PRODUCTION_URL"), self.environment.get("VERCEL_BRANCH_URL"))))
            public = self.environment.get("RPG_PUBLIC_ORIGIN", "")
            if public:
                parsed = urlsplit(public)
                if parsed.scheme != "https" or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
                    raise ValueError("Origine publique invalide")
                allowed.add(parsed.netloc)
            if not self.environment.get("VERCEL"):
                allowed.update(("localhost", "127.0.0.1", "localhost:8080", "127.0.0.1:8080"))
            if host not in allowed:
                raise GameError("invalid_host", "Hôte non autorisé.", 403)
            origin = environ.get("HTTP_ORIGIN")
            if origin and origin != ("https://" if self.environment.get("VERCEL") else environ.get("wsgi.url_scheme", "http") + "://") + host:
                raise GameError("invalid_origin", "Origine non autorisée.", 403)
            navigation = method == "GET" and environ.get("HTTP_SEC_FETCH_MODE") == "navigate" and environ.get("HTTP_SEC_FETCH_DEST") == "document" and path in ("/", "/admin")
            if environ.get("HTTP_SEC_FETCH_SITE") == "cross-site" and not navigation:
                raise GameError("invalid_origin", "Origine non autorisée.", 403)
            if self.environment.get("VERCEL"):
                environ = {**environ, "wsgi.url_scheme": "https"}
            static = {"/admin": ("admin.html", "text/html; charset=utf-8"), "/admin.js": ("admin.js", "text/javascript; charset=utf-8"), "/admin.css": ("admin.css", "text/css; charset=utf-8")}
            if method == "GET" and path in static:
                name, mime = static[path]
                status, payload = 200, (Path(__file__).parent / "web" / name).read_bytes()
            else:
                service = self.service()
                limiter = DatabaseLimiter(service)
                peer = environ.get("REMOTE_ADDR", "unknown")
                if path.startswith("/api/admin/"):
                    if not limiter.accept(("admin", peer), 30):
                        raise GameError("rate_limit", "Trop de requêtes administrateur.", 429)
                    expected = self.environment.get("RPG_ADMIN_TOKEN", "")
                    provided = environ.get("HTTP_AUTHORIZATION", "")
                    if len(expected) < 32:
                        raise GameError("admin_disabled", "Administration non configurée.", 503)
                    if not hmac.compare_digest(provided.encode(), ("Bearer " + expected).encode()):
                        raise GameError("unauthorized", "Accès administrateur requis.", 401)
                    if path == "/api/admin/accounts" and method == "GET":
                        query = parse_qs(environ.get("QUERY_STRING", ""))
                        if set(query) - {"search", "offset"} or any(len(v) != 1 for v in query.values()):
                            raise GameError("invalid_search", "Recherche invalide.")
                        try:
                            offset = int(query.get("offset", ["0"])[0])
                        except ValueError:
                            raise GameError("invalid_search", "Page invalide.") from None
                        payload = admin.accounts(service, query.get("search", [""])[0], offset)
                    elif path == "/api/admin/accounts" and method == "POST":
                        handler = self.handler(environ, service, logger, limiter, host)
                        payload = admin.update_account(service, handler._body())
                    else:
                        raise GameError("not_found", "Ressource introuvable.", 404)
                    status = 200
                else:
                    token = environ.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
                    if path.startswith("/api/") and path not in ("/api/register", "/api/classes"):
                        with service._transaction():
                            player = service._authenticate(token)
                            active = service._active(player["id"])
                        if active:
                            service.tick(active["id"])
                    handler = self.handler(environ, service, logger, limiter, host)
                    handler._dispatch(method == "POST")
                    status, payload, mime = handler.result
        except GameError as error:
            status, payload = error.status, {"error": error.code, "message": str(error)}
        except (ValueError, sqlite3.Error, OSError):
            status, payload = 503, {"error": "unavailable", "message": "Service indisponible ; vérifiez l’état avant de réessayer."}
        except Exception:
            status, payload = 500, {"error": "internal_error", "message": "Erreur interne."}
        finally:
            if service:
                try:
                    service.close()
                except sqlite3.Error:
                    pass
            for handler in logger.handlers:
                handler.close()
        body = json.dumps(payload, ensure_ascii=False).encode() if isinstance(payload, (dict, list)) else payload
        headers = [("Content-Type", mime), ("Content-Length", str(len(body))), ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"), ("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]
        if status == 429:
            headers.append(("Retry-After", "60"))
        start_response(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]

    @staticmethod
    def handler(environ, service, logger, limiter, host):
        handler = RequestHandler.__new__(RequestHandler)
        handler.headers = Message()
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                handler.headers[key[5:].replace("_", "-")] = value
        for key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            if key in environ:
                handler.headers[key.replace("_", "-")] = environ[key]
        handler.path = environ.get("PATH_INFO", "/") + ("?" + environ["QUERY_STRING"] if environ.get("QUERY_STRING") else "")
        handler.rfile = environ.get("wsgi.input", io.BytesIO())
        handler.client_address = (environ.get("REMOTE_ADDR", "unknown"), 0)
        handler.close_connection = False
        scheme = environ.get("wsgi.url_scheme", "https")
        handler.server = SimpleNamespace(service=service, limiter=limiter, commands=DirectCommands(service), hosts={host}, origins={scheme + "://" + host}, network_log=logger)
        return handler
