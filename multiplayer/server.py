import argparse
import json
import logging
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .network_log import create_logger, write
from .service import GameService, GameError, digest


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries = {}

    def accept(self, key, limit):
        now = time.monotonic()
        with self._lock:
            for expired in [k for k, v in self._entries.items() if not v or v[-1] <= now - 60]:
                del self._entries[expired]
            if key not in self._entries and len(self._entries) >= 4096:
                return False
            queue = self._entries.setdefault(key, deque())
            while queue and queue[0] <= now - 60:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(now)
            return True


class RPGServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, address, service, public_origin=None, log_directory=".logs"):
        self.network_log = create_logger(log_directory)
        self.service = service
        self.limiter = RateLimiter()
        self._slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)
        port = self.server_address[1]
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if public_origin:
            parsed = urlsplit(public_origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                self.server_close()
                raise ValueError("L'origine publique doit être une URL HTTPS sans chemin")
            self.hosts.add(parsed.netloc)
            self.origins.add(f"https://{parsed.netloc}")
        self._stop = threading.Event()
        self._ticker = threading.Thread(target=self._tick, daemon=True)
        self._ticker.start()

    def _tick(self):
        while not self._stop.wait(0.1):
            try:
                self.service.tick()
            except Exception:
                logging.getLogger(__name__).exception("Erreur de simulation : le serveur reste accessible, nouvel essai dans une seconde.")
                if self._stop.wait(1):
                    return

    def server_close(self):
        if hasattr(self, "_stop"):
            self._stop.set()
            self._ticker.join(timeout=5)
        super().server_close()
        for handler in self.network_log.handlers:
            handler.close()

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            write(self.network_log, "CONNECTION_REJECTED", reason="capacity", peer=client_address[0])
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "RPG"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        if "timed out" in format:
            write(self.server.network_log, "HANDSHAKE_FAILED", reason="socket_timeout", peer=self.client_address[0])

    def log_error(self, format, *args):
        write(self.server.network_log, "HANDSHAKE_FAILED", reason="http_protocol", peer=self.client_address[0])

    def _respond(self, status, payload, content_type="application/json; charset=utf-8"):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8") if isinstance(payload, (dict, list)) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if status == 429:
            self.send_header("Retry-After", "60")
        self.end_headers()
        self.wfile.write(body)
        if not getattr(self, "_network_combat", False):
            write(self.server.network_log, "HTTP_RESPONSE", route=getattr(self, "_network_route", "unknown"), status=status, bytes=len(body), milliseconds=int((time.monotonic() - getattr(self, "_network_started", time.monotonic())) * 1000))

    def _guard(self):
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0] not in self.server.hosts:
            raise GameError("invalid_host", "Hôte non autorisé.", 403)
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1 or origins and origins[0] not in self.server.origins:
            raise GameError("invalid_origin", "Origine non autorisée.", 403)
        if not self.server.limiter.accept(("ip", self.client_address[0]), 600):
            raise GameError("rate_limit", "Trop de requêtes. Réessayez dans une minute.", 429)

    def _token(self):
        headers = self.headers.get_all("Authorization", [])
        if len(headers) != 1 or not headers[0].startswith("Bearer "):
            raise GameError("unauthorized", "Connexion requise.", 401)
        return headers[0][7:]

    def _body(self):
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise GameError("invalid_content_type", "Le corps doit être au format JSON.", 415)
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit() or self.headers.get("Transfer-Encoding"):
            raise GameError("invalid_length", "Taille de requête invalide.")
        length = int(lengths[0])
        if not 1 <= length <= 4096:
            raise GameError("too_large", "Requête trop volumineuse.", 413)
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result
        try:
            body = json.loads(self.rfile.read(length), object_pairs_hook=pairs,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (ValueError, UnicodeError, RecursionError):
            raise GameError("invalid_json", "JSON invalide.") from None
        if not isinstance(body, dict):
            raise GameError("invalid_json", "Un objet JSON est attendu.")
        return body

    def do_GET(self):
        self._dispatch(False)

    def do_POST(self):
        self._dispatch(True)

    def _dispatch(self, post):
        started = time.monotonic()
        self._network_started = started
        self._network_combat = False
        self._network_route = "unknown"
        combat = False
        action = "none"
        try:
            self._guard()
            parsed = urlsplit(self.path)
            if parsed.query or parsed.fragment:
                raise GameError("invalid_path", "URL invalide.", 404)
            path = parsed.path
            self._network_route = path if path in ("/", "/app.js", "/style.css", "/api/register", "/api/state", "/api/commands") else "session" if path.startswith("/api/sessions/") else "unknown"
            if path.startswith("/api/") and path != "/api/register":
                token = self._token()
                with self.server.service._lock:
                    player = self.server.service._authenticate(token)
                    session = self.server.service._active(player["id"])
                    if session:
                        row = self.server.service.db.execute("SELECT data FROM tutorials WHERE session_id=?", (session["id"],)).fetchone()
                        combat = bool(row and json.loads(row[0]).get("battle")) or bool(not row and session["state"] == "running")
            self._network_combat = combat
            if not combat:
                write(self.server.network_log, "CONNECTION", peer=self.client_address[0], method="POST" if post else "GET", route=self._network_route)
            if not post:
                static = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path in static:
                    name, mime = static[path]
                    self._respond(200, (Path(__file__).parent / "web" / name).read_bytes(), mime)
                elif path == "/api/state":
                    self._respond(200, self.server.service.state(self._token()))
                elif path.startswith("/api/sessions/"):
                    self._respond(200, self.server.service.state(self._token(), path.removeprefix("/api/sessions/")))
                else:
                    raise GameError("not_found", "Ressource introuvable.", 404)
                return
            body = self._body()
            if path == "/api/register":
                if set(body) != {"name", "class_name"}:
                    raise GameError("invalid_command", "Paramètres invalides.")
                if not self.server.limiter.accept(("register", self.client_address[0]), 10):
                    raise GameError("rate_limit", "Trop de créations de personnages.", 429)
                self._respond(201, self.server.service.register(body["name"], body["class_name"]))
            elif path == "/api/commands":
                token = self._token()
                if not self.server.limiter.accept(("command", digest(token)), 60):
                    raise GameError("rate_limit", "Trop de commandes.", 429)
                if set(body) != {"request_id", "action", "params"} or not isinstance(body["params"], dict) or set(body["params"]) & {"token", "request_id", "action"}:
                    raise GameError("invalid_command", "Paramètres invalides.")
                action = body["action"] if isinstance(body["action"], str) else "invalid"
                combat = combat or action in ("strike", "skill", "battle_move", "hide", "harvest", "leave_battle", "control_units", "unit_order", "unit_skill", "attack")
                self._network_combat = combat
                if not combat:
                    write(self.server.network_log, "ACTION_REQUESTED", action=action, peer=self.client_address[0])
                self._respond(200, self.server.service.command(token, body["request_id"], body["action"], **body["params"]))
                if not combat:
                    write(self.server.network_log, "ACTION_COMPLETED", action=action, milliseconds=int((time.monotonic() - started) * 1000))
            else:
                raise GameError("not_found", "Ressource introuvable.", 404)
        except GameError as error:
            if not combat:
                write(self.server.network_log, "REQUEST_REJECTED", reason=error.code, status=error.status, action=action, peer=self.client_address[0])
            self._respond(error.status, {"error": error.code, "message": str(error)})
        except (ConnectionError, TimeoutError):
            if not combat:
                write(self.server.network_log, "CONNECTION_FAILED", reason="disconnected_or_timeout", action=action, peer=self.client_address[0])
            self.close_connection = True
        except Exception:
            if not combat:
                write(self.server.network_log, "REQUEST_FAILED", reason="internal_error", action=action, peer=self.client_address[0])
            self._respond(500, {"error": "internal_error", "message": "Erreur interne. La commande n'a pas été confirmée."})


def main():
    parser = argparse.ArgumentParser(description="RPG multijoueur : tutoriel de la clairière à Brume")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log-directory", default=".logs")
    parser.add_argument("--database", default=".data/multiplayer.sqlite3")
    parser.add_argument("--public-origin", help="Origine HTTPS du proxy, par exemple https://rpg.example.com")
    args = parser.parse_args()
    service = GameService(args.database)
    server = RPGServer(("127.0.0.1", args.port), service, args.public_origin, args.log_directory)
    print(f"RPG multijoueur : http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()


if __name__ == "__main__":
    main()
