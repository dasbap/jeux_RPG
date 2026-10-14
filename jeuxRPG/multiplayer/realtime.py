import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from collections import OrderedDict, defaultdict
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .browser_solo_assets import client_csp
from .distributed import build_rate_limiter
from .json_protocol import object_json
from .protocol_types import PendingBatch, RuntimeMessage, RuntimeResponse
from .realtime_store import KEYS, RuntimeStore
from .server import CLIENT_STATIC
from .serverless import Application, validate_request_origin
from .service import GameError

LEASE = """
local current = redis.call('GET', KEYS[1])
if not current then
  local previous = tonumber(redis.call('GET', KEYS[2]) or '0')
  local fence = math.max(previous + 1, tonumber(ARGV[2]))
  redis.call('SET', KEYS[2], string.format('%.0f', fence))
  redis.call('SET', KEYS[1], ARGV[1] .. ':' .. string.format('%.0f', fence), 'PX', 30000)
  return string.format('%.0f', fence)
end
if string.sub(current, 1, string.len(ARGV[1]) + 1) == ARGV[1] .. ':' then
  redis.call('PEXPIRE', KEYS[1], 30000)
  return string.sub(current, string.len(ARGV[1]) + 2)
end
return false
"""
OWNER = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return 1
end
return 0
"""
RETIRE_CHECKPOINT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('DEL', KEYS[2])
  return 1
end
return 0
"""
RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""
HIDDEN_REFRESH_SECONDS = 20


class Coordinator:
    def __init__(self, environment, redis=None, store=None):
        self.environment = environment
        self.redis = redis
        self.store = store
        self.local = store is not None
        self.uid = uuid.uuid4().hex
        self.prefix = "jeux-rpg:runtime:v2:accounts:"
        self.fence = 0
        self.deadline = 0
        self.tasks = []
        self.pending = {}
        self.messages = {}
        self.next_election = 0
        self.outgoing = defaultdict(list)
        self.received = asyncio.Queue(maxsize=256)
        self.seen = OrderedDict()
        self.relay_tasks = {}
        self.lock = asyncio.Lock()
        self.save_lock = asyncio.Lock()
        self.start_lock = asyncio.Lock()
        self.started = False
        self.saving = None
        self.pubsub = None
        self.connections = 0
        self.handshakes = 0
        self.auth_slots = asyncio.Semaphore(2)
        self.password_limiter = build_rate_limiter(environment)
        self.save_failures = 0
        self.checkpoint_rejections = 0
        self.owner_recoveries = 0
        self.owner_pending_drops = 0

    def owner(self):
        return self.local or self.store is not None and time.monotonic() < self.deadline

    async def start(self):
        async with self.start_lock:
            if self.started:
                return
            if not self.local:
                from .redis_configuration import redis_url

                url = redis_url(self.environment)
                if not url and self.redis is None:
                    raise RuntimeError("Stockage temps réel absent")
                if self.redis is None:
                    self.redis = Redis.from_url(
                        url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                    )
                self.pubsub = self.redis.pubsub()
                await self.pubsub.subscribe(
                    self.prefix + "requests", self.prefix + "reply:" + self.uid
                )
                await self.elect()
                self.tasks.extend(
                    [
                        asyncio.create_task(self.listen()),
                        asyncio.create_task(self.leases()),
                        asyncio.create_task(self.pump()),
                    ]
                )
            self.tasks.append(asyncio.create_task(self.ticker()))
            self.started = True

    async def elect(self):
        self.next_election = time.monotonic() + 8
        result = await self.redis.eval(
            LEASE,
            2,
            self.prefix + "lease",
            self.prefix + "fence",
            self.uid,
            str(4_000_000_000_000_000 + time.time_ns() // 1000),
        )
        if not result:
            self.deadline = 0
            if self.store is not None:
                async with self.lock:
                    if self.store is None:
                        return
                    count = len(self.store.pending)
                    if count:
                        self.owner_pending_drops += count
                        logging.getLogger(__name__).error(
                            "Propriété perdue ; %d mutations locales en attente ; reprise depuis le dernier checkpoint accepté",
                            count,
                        )
                    self.store.close()
                    self.store = None
            return
        self.fence = int(result)
        self.deadline = time.monotonic() + 25
        if self.store is None:
            self.owner_recoveries += 1
            self.seen.clear()
            saved = await self.redis.get(self.prefix + "checkpoint")
            if saved and not await self.restore_legacy_checkpoint(saved):
                self.deadline = 0
                return
            loaded = await asyncio.to_thread(
                RuntimeStore.load, self.environment, self.fence
            )
            try:
                if getattr(loaded, "reset_performed", False):
                    await self.redis.set(
                        "jeux-rpg:runtime:v1:lease",
                        "retired-accounts-v1",
                        px=600000,
                    )
                    await self.redis.delete(
                        "jeux-rpg:runtime:v1:checkpoint",
                        "jeux-rpg:runtime:v1:fence",
                    )
            except BaseException:
                loaded.close()
                raise
            self.store = loaded
            for identifier, message in list(self.messages.items()):
                future = self.pending.get(identifier)
                if future is not None and not future.done():
                    future.set_result(await self.execute(message))

    async def restore_legacy_checkpoint(self, saved):
        checkpoint = json.loads(saved)
        pending = checkpoint.get("pending", [])
        if pending:
            legacy = RuntimeStore(
                self.environment, checkpoint.get("durable", checkpoint)
            )
            try:
                for item in pending:
                    table, row = item["table"], item["row"]
                    key = (
                        tuple(item.get("key", ()))
                        if row is None
                        else tuple(row[column] for column in KEYS[table])
                    )
                    legacy.pending[(table, key)] = row
                accepted = await self.redis.eval(
                    OWNER, 1, self.prefix + "lease", self.uid + ":" + str(self.fence)
                )
                if not accepted:
                    return False
                await asyncio.to_thread(
                    legacy.persist, self.fence, legacy.pending_batch()
                )
            finally:
                legacy.close()
        return bool(
            await self.redis.eval(
                RETIRE_CHECKPOINT,
                2,
                self.prefix + "lease",
                self.prefix + "checkpoint",
                self.uid + ":" + str(self.fence),
            )
        )

    async def leases(self):
        while True:
            await asyncio.sleep(8)
            if not self.connections and not self.pending:
                continue
            try:
                await self.elect()
            except Exception:
                logging.getLogger(__name__).warning("Coordination Redis indisponible")

    async def listen(self):
        while True:
            try:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1
                )
                if message is None:
                    await asyncio.sleep(0.02)
                    continue
                items = json.loads(message["data"])
                if message["channel"] == self.prefix + "requests":
                    if self.owner():
                        for item in items:
                            if not self.received.full():
                                self.received.put_nowait(item)
                else:
                    for item in items:
                        future = self.pending.get(item["id"])
                        if future is not None and not future.done():
                            future.set_result(item["result"])
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger(__name__).warning("Relais temps réel indisponible")
                await asyncio.sleep(1)

    async def pump(self):
        while True:
            await asyncio.sleep(0.5)
            try:
                while not self.received.empty():
                    item = self.received.get_nowait()
                    if not self.owner():
                        continue
                    if item["id"] in self.seen:
                        self.outgoing["reply:" + item["source"]].append(
                            {"id": item["id"], "result": self.seen[item["id"]]}
                        )
                    elif (
                        item["id"] not in self.relay_tasks
                        and len(self.relay_tasks) < 256
                    ):
                        self.relay_tasks[item["id"]] = asyncio.create_task(
                            self.relay(item)
                        )
                for target in list(self.outgoing):
                    queue = self.outgoing[target]
                    if target == "requests":
                        queue[:] = [
                            item for item in queue if item["id"] in self.pending
                        ]
                    if not queue:
                        self.outgoing.pop(target, None)
                        continue
                    items = queue[:64]
                    payload = json.dumps(items, separators=(",", ":"))
                    while len(payload.encode()) > 4 * 1024 * 1024 and len(items) > 1:
                        items = items[: len(items) // 2]
                        payload = json.dumps(items, separators=(",", ":"))
                    await self.redis.publish(self.prefix + target, payload)
                    del queue[: len(items)]
                    if not queue:
                        self.outgoing.pop(target, None)
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger(__name__).warning("Lot temps réel non livré")

    async def relay(self, item):
        try:
            try:
                result = await self.execute(item["message"])
            except Exception:
                logging.getLogger(__name__).warning("Commande relayée interrompue")
                result = {
                    "status": 503,
                    "headers": {},
                    "body": {
                        "error": "unavailable",
                        "message": "Réessayez avec le même identifiant de commande.",
                    },
                }
            self.seen[item["id"]] = result
            if len(self.seen) > 256:
                self.seen.popitem(last=False)
            self.outgoing["reply:" + item["source"]].append(
                {"id": item["id"], "result": result}
            )
        finally:
            self.relay_tasks.pop(item["id"], None)

    async def memory_call(self, function, *args):
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            with suppress(Exception):
                await task
            raise

    async def execute(self, message: RuntimeMessage) -> RuntimeResponse:
        prepared = None
        store = None
        body = message.get("body")
        login = message.get("method") == "POST" and message.get("path") in (
            "/api/account/login",
            "/api/account/signup",
        )
        if login and isinstance(body, dict) and set(body) == {"username", "password"}:
            from .service import GameError

            async with self.auth_slots:
                async with self.lock:
                    if self.owner():
                        store = self.store
                if store is not None:
                    accepted = await self.memory_call(
                        self.password_limiter.accept,
                        ("password_work", message.get("peer", "unknown")),
                        10,
                    )
                    if not accepted:
                        return {
                            "status": 429,
                            "headers": {},
                            "body": {
                                "error": "rate_limit",
                                "message": "Trop de connexions. Réessayez dans une minute.",
                            },
                        }
                    try:
                        prepared = await self.memory_call(
                            store.service.prepare_account_login,
                            body["username"],
                            body["password"],
                            message["path"].endswith("signup"),
                        )
                    except GameError as error:
                        return {
                            "status": error.status,
                            "headers": {},
                            "body": {"error": error.code, "message": str(error)},
                        }
        async with self.lock:
            if not self.owner() or store is not None and self.store is not store:
                return {
                    "status": 503,
                    "headers": {},
                    "body": {
                        "error": "unavailable",
                        "message": "Reconnexion du moteur en cours.",
                    },
                }
            result = await self.memory_call(self.store.request, message, prepared)
            result["headers"].update(
                {
                    "X-RPG-Save-Failures": str(self.save_failures),
                    "X-RPG-Checkpoint-Rejections": str(self.checkpoint_rejections),
                    "X-RPG-Owner-Recoveries": str(self.owner_recoveries),
                    "X-RPG-Owner-Pending-Drops": str(self.owner_pending_drops),
                }
            )
            return result

    async def rpc(self, message: RuntimeMessage) -> RuntimeResponse:
        await self.start()
        if not self.owner() and time.monotonic() >= self.next_election:
            await self.elect()
        if self.owner():
            return await self.execute(message)
        if len(self.pending) >= 256:
            raise RuntimeError("Relais saturé")
        identifier = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        self.messages[identifier] = message
        try:
            self.outgoing["requests"].append(
                {"id": identifier, "source": self.uid, "message": message}
            )
            return await asyncio.wait_for(future, 25)
        finally:
            self.pending.pop(identifier, None)
            self.messages.pop(identifier, None)

    async def save(self, store, fence):
        async with self.save_lock:
            batch = store.pending_batch()
            if not batch:
                return
            await self.write_checkpoint(store, batch, fence)

    async def write_checkpoint(
        self, store: RuntimeStore, batch: PendingBatch, fence: int
    ) -> None:
        try:
            if not self.local:
                accepted = await self.redis.eval(
                    OWNER,
                    1,
                    self.prefix + "lease",
                    self.uid + ":" + str(fence),
                )
                if not accepted:
                    self.checkpoint_rejections += 1
                    store.last_save_error = bool(store.pending)
                    store.due = time.monotonic() + 5 if store.pending else None
                    logging.getLogger(__name__).warning(
                        "Checkpoint refusé ; changements encore en attente"
                    )
                    return
            await asyncio.to_thread(store.persist, fence, batch)
            store.saved(batch)
        except Exception:
            self.save_failures += 1
            store.last_save_error = bool(store.pending)
            store.due = time.monotonic() + 5 if store.pending else None
            logging.getLogger(__name__).warning(
                "Sauvegarde différée ; changements conservés pour nouvelle tentative"
            )

    async def ticker(self):
        while True:
            await asyncio.sleep(0.2)
            if not self.owner():
                continue
            try:
                async with self.lock:
                    if not self.owner():
                        continue
                    await self.memory_call(self.store.tick)
                    if (
                        self.store.due is not None
                        and self.store.due <= time.monotonic()
                        and (self.saving is None or self.saving.done())
                    ):
                        self.saving = asyncio.create_task(
                            self.save(self.store, self.fence)
                        )
            except Exception:
                logging.getLogger(__name__).warning(
                    "Simulation interrompue ; nouvelle tentative au prochain tick"
                )

    async def close(self):
        tasks = [*self.tasks, *self.relay_tasks.values()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        if self.saving is not None:
            with suppress(Exception):
                await self.saving
        if not self.local:
            await self.flush()
        if self.pubsub:
            await self.pubsub.aclose()
        if self.redis:
            await self.redis.aclose()
        if hasattr(self.password_limiter, "close"):
            await asyncio.to_thread(self.password_limiter.close)
        async with self.lock:
            if self.store:
                self.store.close()
        self.started = False

    async def flush(self):
        if self.saving is not None and not self.saving.done():
            await self.saving
        async with self.lock:
            if not self.owner() or not self.store.pending:
                return
            store, fence = self.store, self.fence
        await self.save(store, fence)

    async def release(self):
        if self.local or not self.owner() or self.connections:
            return
        await self.flush()
        async with self.lock:
            if not self.owner() or self.connections or self.store.pending:
                return
            try:
                await self.redis.eval(
                    RELEASE, 1, self.prefix + "lease", self.uid + ":" + str(self.fence)
                )
            except RedisError:
                logging.getLogger(__name__).warning(
                    "Libération Redis différée ; moteur conservé jusqu’à expiration du bail"
                )
                return
            self.deadline = 0
            self.next_election = 0
            self.store.close()
            self.store = None


def _socket_origin_allowed(websocket, environment):
    host = websocket.headers.get("host", "")
    origin = websocket.headers.get("origin")
    scheme = "https" if environment.get("VERCEL") else "http"
    allowed = {
        value
        for value in (
            environment.get("VERCEL_URL"),
            environment.get("VERCEL_PROJECT_PRODUCTION_URL"),
            environment.get("VERCEL_BRANCH_URL"),
            environment.get("RPG_PUBLIC_ORIGIN", "").removeprefix("https://"),
        )
        if value
    }
    if not environment.get("VERCEL"):
        allowed.add(
            host
            if host.startswith(("localhost:", "127.0.0.1:"))
            or host in ("testserver", "localhost", "127.0.0.1")
            else ""
        )
    return host in allowed and origin == scheme + "://" + host


async def _authenticate_socket(websocket, coordinator, trusted):
    raw = await asyncio.wait_for(websocket.receive_text(), 10)
    if len(raw.encode()) > 4096:
        await websocket.close(code=1009)
        return
    item = object_json(raw)
    headers = item.get("headers", {})
    if (
        item.get("type") != "authenticate"
        or not isinstance(headers, dict)
        or set(headers) != {"Authorization"}
        or not isinstance(headers["Authorization"], str)
    ):
        await websocket.close(code=1008)
        return
    identity = await coordinator.rpc(
        trusted(websocket, "/api/account/me", "GET", headers=headers)
    )
    if identity["status"] != 200:
        await websocket.close(code=1008)
        return
    authenticated = headers["Authorization"]
    await websocket.send_json({"type": "authenticated"})
    return authenticated


@dataclass
class SubscriptionState:
    subscription: dict | None = None
    paused: bool = False
    hidden_refresh_at: float = field(
        default_factory=lambda: time.monotonic() + HIDDEN_REFRESH_SECONDS
    )


async def _push_socket_state(state, websocket, coordinator, send):
    while True:
        fast = (
            coordinator.owner()
            and len(coordinator.store.service.runtime_presence) <= 16
        )
        small = fast and len(coordinator.store.service.runtime_presence) <= 4
        await asyncio.sleep(0.15 if small else 0.5 if fast else 1)
        if state.subscription is not None and (
            not state.paused or time.monotonic() >= state.hidden_refresh_at
        ):
            try:
                result = await coordinator.rpc(state.subscription)
            except (TimeoutError, RuntimeError, OSError):
                with suppress(RuntimeError, WebSocketDisconnect):
                    await websocket.close(code=1012)
                return
            if result["status"] in (401, 403):
                await websocket.close(code=1008)
                return
            if state.paused:
                state.hidden_refresh_at = time.monotonic() + HIDDEN_REFRESH_SECONDS
                continue
            await send(
                {
                    "type": "state",
                    "subscription": state.subscription["subscription"],
                    "result": result,
                }
            )
            if result["body"].get("bundle_protocol") == 1:
                state.subscription["headers"]["x-rpg-bundle-hashes"] = json.dumps(
                    result["body"]["hashes"]
                )


async def _socket_connection(websocket, coordinator, environment, trusted):
    if not _socket_origin_allowed(websocket, environment):
        await websocket.close(code=1008)
        return
    if (
        coordinator.connections >= RuntimeStore.runtime_capacity()
        or coordinator.handshakes >= 16
    ):
        await websocket.close(code=1013)
        return
    coordinator.handshakes += 1
    authenticated = None
    try:
        await websocket.accept()
        if environment.get("VERCEL"):
            authenticated = await _authenticate_socket(websocket, coordinator, trusted)
            if authenticated is None:
                return
        if coordinator.connections >= RuntimeStore.runtime_capacity():
            await websocket.close(code=1013)
            return
    except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close(code=1008)
        return
    finally:
        coordinator.handshakes -= 1
    coordinator.connections += 1
    send_lock = asyncio.Lock()
    state = SubscriptionState()

    async def send(value):
        async with send_lock:
            await websocket.send_json(value)

    pusher = asyncio.create_task(
        _push_socket_state(state, websocket, coordinator, send)
    )
    started = time.monotonic()
    window, count = started, 0
    try:
        while time.monotonic() - started < 280:
            raw = await asyncio.wait_for(websocket.receive_text(), 30)
            if len(raw.encode()) > 65536:
                await websocket.close(code=1009)
                return
            if time.monotonic() - window > 1:
                window, count = time.monotonic(), 0
            count += 1
            if count > 20:
                await websocket.close(code=1008)
                return
            item = object_json(raw)
            if item.get("type") == "visibility" and type(item.get("active")) is bool:
                state.paused = not item["active"]
                state.hidden_refresh_at = time.monotonic() + HIDDEN_REFRESH_SECONDS
                await send({"type": "visibility", "active": not state.paused})
                continue
            if item.get("type") == "ping":
                await send({"type": "pong"})
                continue
            path = item.get("path", "")
            headers = item.get("headers", {})
            if (
                not isinstance(path, str)
                or len(path) > 256
                or not path.startswith("/api/")
                or path.startswith("/api/admin/")
                or path == "/api/ws"
                or not isinstance(headers, dict)
                or any(
                    not isinstance(k, str)
                    or len(k) > 64
                    or not isinstance(v, str)
                    or len(v) > 8192
                    for k, v in headers.items()
                )
            ):
                await websocket.close(code=1008)
                return
            if (
                item.get("method", "GET") not in ("GET", "POST")
                or authenticated
                and headers.get("Authorization", headers.get("authorization"))
                != authenticated
            ):
                await websocket.close(code=1008)
                return
            request = trusted(
                websocket,
                path,
                item.get("method", "GET"),
                item.get("body"),
                headers,
            )
            result = await coordinator.rpc(request)
            await send({"id": item.get("id"), "result": result})
            if path == "/api/state" and result["status"] == 200:
                state.subscription = {
                    **request,
                    "subscription": item.get("id"),
                    "headers": {
                        **request["headers"],
                        "x-rpg-bundles": "1",
                        "x-rpg-bundle-hashes": "",
                    },
                }
    except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
        pass
    finally:
        pusher.cancel()
        with suppress(
            asyncio.CancelledError, WebSocketDisconnect, RuntimeError, TimeoutError
        ):
            await pusher
        coordinator.connections -= 1
        if coordinator.connections == 0:
            await coordinator.flush()
            await coordinator.release()
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close(code=1012)


def _register_socket(app, coordinator, environment, trusted):
    @app.websocket("/api/ws")
    async def socket(websocket: WebSocket):
        await _socket_connection(websocket, coordinator, environment, trusted)


def relay_request_origin(environment, host, headers):
    if not environment.get("VERCEL"):
        return host, headers
    public = environment.get("RPG_PUBLIC_ORIGIN", "")
    canonical = (
        urlsplit(public).netloc
        if public
        else environment.get("VERCEL_PROJECT_PRODUCTION_URL")
    )
    if not canonical:
        return host, headers
    return canonical, {
        **headers,
        **({"origin": "https://" + canonical} if "origin" in headers else {}),
    }


async def request_origin_error(request, error):
    return JSONResponse(
        {"error": error.code, "message": str(error)}, status_code=error.status
    )


def _trusted_request(connection, path, method, body, headers, environment):
    incoming = dict(connection.headers)
    forwarded = {
        key.lower(): value
        for key, value in (headers or incoming).items()
        if key.lower()
        in (
            "authorization",
            "x-rpg-chat-connection",
            "x-rpg-command-ack",
            "x-rpg-bundles",
            "x-rpg-bundle-hashes",
        )
    }
    for key in ("origin", "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest"):
        if key in incoming:
            forwarded[key] = incoming[key]
    host, forwarded = relay_request_origin(
        environment, incoming.get("host", ""), forwarded
    )
    return {
        "path": path,
        "method": method,
        "body": body,
        "headers": forwarded,
        "host": host,
        "peer": connection.client.host if connection.client else "unknown",
        "scheme": "https" if environment.get("VERCEL") else "http",
    }


def _static_response(request, path, result, content):
    if result["status"] == 200:
        web = Path(__file__).parent / "web"
        if path in ("", "admin"):
            assets = {
                value[0]
                for value in CLIENT_STATIC.values()
                if value[0].endswith((".js", ".css"))
            }
            assets.update({"admin.js", "admin.css"})
            for asset in sorted(assets):
                digest = hashlib.sha256((web / asset).read_bytes()).hexdigest()[:16]
                content = content.replace(
                    ('"/' + asset + '"').encode(),
                    ('"/' + asset + "?v=" + digest + '"').encode(),
                )
            result["headers"]["Content-Length"] = str(len(content))
            result["headers"]["Cache-Control"] = "no-cache"
        else:
            digest = hashlib.sha256(content).hexdigest()[:16]
            result["headers"]["Cache-Control"] = (
                "public, max-age=31536000, immutable"
                if request.query_params.get("v") == digest
                else "public, max-age=0, must-revalidate"
            )
            result["headers"]["ETag"] = '"' + digest + '"'
            if request.headers.get("if-none-match") == result["headers"]["ETag"]:
                result["headers"].pop("Content-Length", None)
                return Response(status_code=304, headers=result["headers"])
    return Response(content, status_code=result["status"], headers=result["headers"])


def create_app(environment=None, coordinator=None):
    environment = dict(os.environ if environment is None else environment)
    coordinator = coordinator or Coordinator(environment)
    static = Application(environment=environment)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await coordinator.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.coordinator = coordinator
    app.add_exception_handler(GameError, request_origin_error)

    @app.middleware("http")
    async def response_security(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            client_csp(request.url.path),
        )
        if environment.get("VERCEL"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    def trusted(connection, path, method, body=None, headers=None):
        return _trusted_request(connection, path, method, body, headers, environment)

    @app.get("/health")
    async def healthcheck():
        result = {"status": "ok"}
        if environment.get("RPG_RELEASE_SHA"):
            result["release"] = environment["RPG_RELEASE_SHA"]
        return JSONResponse(result)

    _register_socket(app, coordinator, environment, trusted)

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def http(request: Request, path: str):
        if path == "api/classes":
            from .catalogue import catalogue

            return JSONResponse(catalogue())
        if path.startswith("api/"):
            validate_request_origin(
                environment,
                {
                    "HTTP_" + key.upper().replace("-", "_"): value
                    for key, value in request.headers.items()
                },
                "/" + path,
                request.method,
            )
            try:
                raw = await request.body()
                if len(raw) > 65536:
                    return JSONResponse(
                        {"error": "too_large", "message": "Requête trop volumineuse."},
                        status_code=413,
                    )
                message = trusted(
                    request,
                    "/" + path + ("?" + request.url.query if request.url.query else ""),
                    request.method,
                    object_json(raw) if raw else None,
                )
                result = await coordinator.rpc(message)
                if (
                    request.method == "POST"
                    and result["status"] < 300
                    and coordinator.owner()
                    and not coordinator.connections
                ):
                    await coordinator.flush()
                if coordinator.owner() and not coordinator.connections:
                    await coordinator.release()
                headers = {
                    key: value
                    for key, value in result["headers"].items()
                    if key.lower() != "content-length"
                }
                return JSONResponse(
                    result["body"], status_code=result["status"], headers=headers
                )
            except (ValueError, UnicodeError, RecursionError):
                return JSONResponse(
                    {"error": "invalid_json", "message": "JSON invalide."},
                    status_code=400,
                )
            except Exception:
                return JSONResponse(
                    {
                        "error": "unavailable",
                        "message": "Moteur temps réel indisponible.",
                    },
                    status_code=503,
                )
        static_paths = {key.removeprefix("/") for key in CLIENT_STATIC}
        static_paths.update({"admin", "admin.js", "admin.css"})
        if path not in static_paths:
            return Response(status_code=404)
        result = {}

        def start(status, headers):
            result.update(status=int(status.split()[0]), headers=dict(headers))

        environment_wsgi = {
            "PATH_INFO": "/" + path,
            "REQUEST_METHOD": request.method,
            "HTTP_HOST": request.headers.get("host", ""),
            "wsgi.url_scheme": "https" if environment.get("VERCEL") else "http",
        }
        for key, value in request.headers.items():
            environment_wsgi["HTTP_" + key.upper().replace("-", "_")] = value
        content = b"".join(static(environment_wsgi, start))
        return _static_response(request, path, result, content)

    return app
