import asyncio
import json
import hashlib
from pathlib import Path
import logging
import os
import time
import uuid
from collections import OrderedDict, defaultdict
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from redis.asyncio import Redis

from .json_protocol import object_json
from .realtime_store import RuntimeStore
from .serverless import Application


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
SNAPSHOT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('SET', KEYS[2], ARGV[2])
  return 1
end
return 0
"""
ACK = """
local data = redis.call('GET', KEYS[1])
if data then
  local checkpoint = cjson.decode(data)
  if checkpoint.save_id == ARGV[1] then
    checkpoint.pending = {}
    redis.call('SET', KEYS[1], cjson.encode(checkpoint))
    return 1
  end
end
return 0
"""
RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


class Coordinator:
    def __init__(self, environment, redis=None, store=None):
        self.environment = environment
        self.redis = redis
        self.store = store
        self.local = store is not None
        self.uid = uuid.uuid4().hex
        self.prefix = 'jeux-rpg:runtime:v2:accounts:'
        self.fence = 0
        self.deadline = 0
        self.tasks = []
        self.pending = {}
        self.messages = {}
        self.next_election = 0
        self.outgoing = defaultdict(list)
        self.received = asyncio.Queue(maxsize=256)
        self.seen = OrderedDict()
        self.lock = asyncio.Lock()
        self.save_lock = asyncio.Lock()
        self.start_lock = asyncio.Lock()
        self.started = False
        self.saving = None
        self.pubsub = None
        self.connections = 0
        self.handshakes = 0
        self.auth_slots = asyncio.Semaphore(2)

    def owner(self):
        return self.local or self.store is not None and time.monotonic() < self.deadline

    async def start(self):
        async with self.start_lock:
            if self.started:
                return
            if not self.local:
                url = self.environment.get('REDIS_URL') or self.environment.get('KV_URL')
                if not url and self.redis is None:
                    raise RuntimeError('Stockage temps réel absent')
                if self.redis is None:
                    self.redis = Redis.from_url(url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
                self.pubsub = self.redis.pubsub()
                await self.pubsub.subscribe(self.prefix + 'requests', self.prefix + 'reply:' + self.uid)
                await self.elect()
                self.tasks.extend([asyncio.create_task(self.listen()), asyncio.create_task(self.leases()), asyncio.create_task(self.pump())])
            self.tasks.append(asyncio.create_task(self.ticker()))
            self.started = True

    async def elect(self):
        self.next_election = time.monotonic() + 8
        result = await self.redis.eval(LEASE, 2, self.prefix + 'lease', self.prefix + 'fence', self.uid, str(4_000_000_000_000_000 + time.time_ns() // 1000))
        if not result:
            self.deadline = 0
            if self.store is not None:
                async with self.lock:
                    self.store.close()
                    self.store = None
            return
        self.fence = int(result)
        self.deadline = time.monotonic() + 25
        if self.store is None:
            self.seen.clear()
            saved = await self.redis.get(self.prefix + 'checkpoint')
            if saved:
                checkpoint = json.loads(saved)
                self.store = RuntimeStore(self.environment, checkpoint.get('durable', checkpoint))
                from .realtime_store import KEYS
                for item in checkpoint.get('pending', []):
                    table, row = item['table'], item['row']
                    self.store.pending[(table, tuple(item.get('key', ())) if row is None else tuple(row[key] for key in KEYS[table]))] = row
                self.store.due = time.monotonic() + 5 if self.store.pending else None
            else:
                loaded = await asyncio.to_thread(RuntimeStore.load, self.environment)
                try:
                    if getattr(loaded, "reset_performed", False):
                        await self.redis.set("jeux-rpg:runtime:v1:lease", "retired-accounts-v1", px=600000)
                        await self.redis.delete("jeux-rpg:runtime:v1:checkpoint", "jeux-rpg:runtime:v1:fence")
                except BaseException:
                    loaded.close()
                    raise
                self.store = loaded
                checkpoint = json.dumps({'durable': json.loads(self.store.snapshot()), 'pending': [], 'save_id': ''})
                await self.redis.eval(SNAPSHOT, 2, self.prefix + 'lease', self.prefix + 'checkpoint', self.uid + ':' + str(self.fence), checkpoint)
            for identifier, message in list(self.messages.items()):
                future = self.pending.get(identifier)
                if future is not None and not future.done():
                    future.set_result(await self.execute(message))

    async def leases(self):
        while True:
            await asyncio.sleep(8)
            if not self.connections and not self.pending:
                continue
            try:
                await self.elect()
            except Exception:
                logging.getLogger(__name__).warning('Coordination Redis indisponible')

    async def listen(self):
        while True:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                if message is None:
                    await asyncio.sleep(.02)
                    continue
                items = json.loads(message['data'])
                if message['channel'] == self.prefix + 'requests':
                    if self.owner():
                        for item in items:
                            if not self.received.full():
                                self.received.put_nowait(item)
                else:
                    for item in items:
                        future = self.pending.get(item['id'])
                        if future is not None and not future.done():
                            future.set_result(item['result'])
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger(__name__).warning('Relais temps réel indisponible')
                await asyncio.sleep(1)

    async def pump(self):
        while True:
            await asyncio.sleep(.5)
            try:
                while not self.received.empty():
                    item = self.received.get_nowait()
                    if not self.owner():
                        continue
                    if item['id'] not in self.seen:
                        self.seen[item['id']] = await self.execute(item['message'])
                        if len(self.seen) > 256:
                            self.seen.popitem(last=False)
                    self.outgoing['reply:' + item['source']].append({'id': item['id'], 'result': self.seen[item['id']]})
                for target in list(self.outgoing):
                    queue = self.outgoing[target]
                    if target == 'requests':
                        queue[:] = [item for item in queue if item['id'] in self.pending]
                    if not queue:
                        self.outgoing.pop(target, None)
                        continue
                    items = queue[:64]
                    payload = json.dumps(items, separators=(',', ':'))
                    while len(payload.encode()) > 4 * 1024 * 1024 and len(items) > 1:
                        items = items[:len(items) // 2]
                        payload = json.dumps(items, separators=(',', ':'))
                    await self.redis.publish(self.prefix + target, payload)
                    del queue[:len(items)]
                    if not queue:
                        self.outgoing.pop(target, None)
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger(__name__).warning('Lot temps réel non livré')

    async def memory_call(self, function, *args):
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            with suppress(Exception):
                await task
            raise

    async def execute(self, message):
        prepared = None
        store = None
        body = message.get('body')
        login = message.get('method') == 'POST' and message.get('path') in ('/api/account/login', '/api/account/signup')
        if login and isinstance(body, dict) and set(body) == {'username', 'password'}:
            from .service import GameError
            from .serverless import DatabaseLimiter
            async with self.auth_slots:
                async with self.lock:
                    if self.owner():
                        store = self.store
                        if not DatabaseLimiter(store.service).accept(('password_work', message.get('peer', 'unknown')), 10):
                            return {'status': 429, 'headers': {}, 'body': {'error': 'rate_limit', 'message': 'Trop de connexions. Réessayez dans une minute.'}}
                if store is not None:
                    try:
                        prepared = await self.memory_call(store.service.prepare_account_login, body['username'], body['password'], message['path'].endswith('signup'))
                    except GameError as error:
                        return {'status': error.status, 'headers': {}, 'body': {'error': error.code, 'message': str(error)}}
        async with self.lock:
            if not self.owner() or store is not None and self.store is not store:
                return {'status': 503, 'headers': {}, 'body': {'error': 'unavailable', 'message': 'Reconnexion du moteur en cours.'}}
            return await self.memory_call(self.store.request, message, prepared)

    async def rpc(self, message):
        await self.start()
        if not self.owner() and time.monotonic() >= self.next_election:
            await self.elect()
        if self.owner():
            return await self.execute(message)
        if len(self.pending) >= 256:
            raise RuntimeError('Relais saturé')
        identifier = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        self.messages[identifier] = message
        try:
            self.outgoing['requests'].append({'id': identifier, 'source': self.uid, 'message': message})
            return await asyncio.wait_for(future, 25)
        finally:
            self.pending.pop(identifier, None)
            self.messages.pop(identifier, None)

    async def save(self, store, batch, snapshot, fence):
        async with self.save_lock:
            batch = store.pending_batch()
            if not batch:
                return
            snapshot = store.snapshot()
            await self.write_checkpoint(store, batch, snapshot, fence)

    async def write_checkpoint(self, store, batch, snapshot, fence):
        try:
            save_id = uuid.uuid4().hex
            if not self.local:
                checkpoint = json.dumps({'durable': json.loads(snapshot), 'pending': [{'table': table, 'key': key, 'row': row} for (table, key), row in batch.items()], 'save_id': save_id}, separators=(',', ':'))
                accepted = await self.redis.eval(SNAPSHOT, 2, self.prefix + 'lease', self.prefix + 'checkpoint', self.uid + ':' + str(fence), checkpoint)
                if not accepted:
                    return
            await asyncio.to_thread(store.persist, fence, batch)
            store.saved(batch)
            if not self.local:
                await self.redis.eval(ACK, 1, self.prefix + 'checkpoint', save_id)
        except Exception:
            store.last_save_error = bool(store.pending)
            store.due = time.monotonic() + 5 if store.pending else None
            logging.getLogger(__name__).warning('Sauvegarde différée ; changements conservés pour nouvelle tentative')

    async def ticker(self):
        while True:
            await asyncio.sleep(.2)
            if not self.owner():
                continue
            try:
                async with self.lock:
                    if not self.owner():
                        continue
                    await self.memory_call(self.store.tick)
                    if self.store.due is not None and self.store.due <= time.monotonic() and (self.saving is None or self.saving.done()):
                        self.saving = asyncio.create_task(self.save(self.store, self.store.pending_batch(), self.store.snapshot(), self.fence))
            except Exception:
                logging.getLogger(__name__).warning('Simulation interrompue ; nouvelle tentative au prochain tick')

    async def close(self):
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
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
            store, batch, snapshot, fence = self.store, self.store.pending_batch(), self.store.snapshot(), self.fence
        await self.save(store, batch, snapshot, fence)

    async def release(self):
        if self.local or not self.owner() or self.connections:
            return
        await self.flush()
        if self.connections:
            return
        await self.redis.eval(RELEASE, 1, self.prefix + 'lease', self.uid + ':' + str(self.fence))
        async with self.lock:
            self.deadline = 0
            self.next_election = 0
            self.store.close()
            self.store = None


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

    @app.middleware('http')
    async def response_security(request, call_next):
        response = await call_next(request)
        response.headers.setdefault('Cache-Control', 'no-store')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        response.headers.setdefault('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if environment.get('VERCEL'):
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
        return response

    def trusted(connection, path, method, body=None, headers=None):
        incoming = dict(connection.headers)
        forwarded = {key.lower(): value for key, value in (headers or incoming).items() if key.lower() in
                     ('authorization', 'x-rpg-chat-connection', 'x-rpg-command-ack', 'x-rpg-bundles', 'x-rpg-bundle-hashes')}
        for key in ('origin', 'sec-fetch-site', 'sec-fetch-mode', 'sec-fetch-dest'):
            if key in incoming:
                forwarded[key] = incoming[key]
        return {'path': path, 'method': method, 'body': body, 'headers': forwarded,
                'host': incoming.get('host', ''), 'peer': connection.client.host if connection.client else 'unknown',
                'scheme': 'https' if environment.get('VERCEL') else 'http'}

    @app.websocket('/api/ws')
    async def socket(websocket: WebSocket):
        host = websocket.headers.get('host', '')
        origin = websocket.headers.get('origin')
        scheme = 'https' if environment.get('VERCEL') else 'http'
        allowed = {value for value in (environment.get('VERCEL_URL'), environment.get('VERCEL_PROJECT_PRODUCTION_URL'), environment.get('VERCEL_BRANCH_URL'), environment.get('RPG_PUBLIC_ORIGIN', '').removeprefix('https://')) if value}
        if not environment.get('VERCEL'):
            allowed.add(host if host.startswith(('localhost:', '127.0.0.1:')) or host in ('testserver', 'localhost', '127.0.0.1') else '')
        if host not in allowed or origin != scheme + '://' + host:
            await websocket.close(code=1008)
            return
        if coordinator.connections >= 40 or coordinator.handshakes >= 16:
            await websocket.close(code=1013)
            return
        coordinator.handshakes += 1
        authenticated = None
        try:
            await websocket.accept()
            if environment.get('VERCEL'):
                raw = await asyncio.wait_for(websocket.receive_text(), 10)
                if len(raw.encode()) > 4096:
                    await websocket.close(code=1009)
                    return
                item = object_json(raw)
                headers = item.get('headers', {})
                if item.get('type') != 'authenticate' or not isinstance(headers, dict) or set(headers) != {'Authorization'} or not isinstance(headers['Authorization'], str):
                    await websocket.close(code=1008)
                    return
                identity = await coordinator.rpc(trusted(websocket, '/api/account/me', 'GET', headers=headers))
                if identity['status'] != 200:
                    await websocket.close(code=1008)
                    return
                authenticated = headers['Authorization']
                await websocket.send_json({'type': 'authenticated'})
            if coordinator.connections >= 40:
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
        subscription = None
        paused = False

        async def send(value):
            async with send_lock:
                await websocket.send_json(value)

        async def push():
            while True:
                fast = coordinator.owner() and len(coordinator.store.service.runtime_presence) <= 16
                small = fast and len(coordinator.store.service.runtime_presence) <= 4
                await asyncio.sleep(.15 if small else .5 if fast else 1)
                if subscription is not None and not paused:
                    try:
                        result = await coordinator.rpc(subscription)
                    except (TimeoutError, RuntimeError, OSError):
                        with suppress(RuntimeError, WebSocketDisconnect):
                            await websocket.close(code=1012)
                        return
                    if result['status'] in (401, 403):
                        await websocket.close(code=1008)
                        return
                    if paused:
                        continue
                    await send({'type': 'state', 'subscription': subscription['subscription'], 'result': result})
                    if result['body'].get('bundle_protocol') == 1:
                        subscription['headers']['x-rpg-bundle-hashes'] = json.dumps(result['body']['hashes'])

        pusher = asyncio.create_task(push())
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
                if item.get('type') == 'visibility' and type(item.get('active')) is bool:
                    paused = not item['active']
                    await send({'type': 'visibility', 'active': not paused})
                    continue
                if item.get('type') == 'ping':
                    await send({'type': 'pong'})
                    continue
                path = item.get('path', '')
                headers = item.get('headers', {})
                if not isinstance(path, str) or len(path) > 256 or not path.startswith('/api/') or path.startswith('/api/admin/') or path == '/api/ws' or not isinstance(headers, dict) or any(not isinstance(k, str) or len(k) > 64 or not isinstance(v, str) or len(v) > 8192 for k, v in headers.items()):
                    await websocket.close(code=1008)
                    return
                if item.get('method', 'GET') not in ('GET', 'POST') or authenticated and headers.get('Authorization', headers.get('authorization')) != authenticated:
                    await websocket.close(code=1008)
                    return
                request = trusted(websocket, path, item.get('method', 'GET'), item.get('body'), headers)
                result = await coordinator.rpc(request)
                await send({'id': item.get('id'), 'result': result})
                if path == '/api/state' and result['status'] == 200:
                    subscription = {**request, 'subscription': item.get('id'), 'headers': {**request['headers'], 'x-rpg-bundles': '1', 'x-rpg-bundle-hashes': ''}}
        except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
            pass
        finally:
            pusher.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError, TimeoutError):
                await pusher
            coordinator.connections -= 1
            if coordinator.connections == 0:
                await coordinator.flush()
                await coordinator.release()
            with suppress(RuntimeError, WebSocketDisconnect):
                await websocket.close(code=1012)

    @app.api_route('/{path:path}', methods=['GET', 'POST'])
    async def http(request: Request, path: str):
        if path == 'api/classes':
            from .catalogue import catalogue
            return JSONResponse(catalogue())
        if path.startswith('api/'):
            try:
                raw = await request.body()
                if len(raw) > 65536:
                    return JSONResponse({'error': 'too_large', 'message': 'Requête trop volumineuse.'}, status_code=413)
                message = trusted(request, '/' + path + ('?' + request.url.query if request.url.query else ''), request.method, object_json(raw) if raw else None)
                result = await coordinator.rpc(message)
                if request.method == 'POST' and result['status'] < 300 and coordinator.owner() and not coordinator.connections:
                    await coordinator.flush()
                if coordinator.owner() and not coordinator.connections:
                    await coordinator.release()
                headers = {key: value for key, value in result['headers'].items() if key.lower() != 'content-length'}
                return JSONResponse(result['body'], status_code=result['status'], headers=headers)
            except (ValueError, UnicodeError, RecursionError):
                return JSONResponse({'error': 'invalid_json', 'message': 'JSON invalide.'}, status_code=400)
            except Exception:
                return JSONResponse({'error': 'unavailable', 'message': 'Moteur temps réel indisponible.'}, status_code=503)
        if path not in ('', 'app.js', 'mobile_controls.js', 'realtime.js', 'map_artwork.js', 'style.css', 'admin', 'admin.js', 'admin.css'):
            return Response(status_code=404)
        result = {}
        def start(status, headers):
            result.update(status=int(status.split()[0]), headers=dict(headers))
        environment_wsgi = {'PATH_INFO': '/' + path, 'REQUEST_METHOD': request.method, 'HTTP_HOST': request.headers.get('host', ''), 'wsgi.url_scheme': 'https' if environment.get('VERCEL') else 'http'}
        for key, value in request.headers.items():
            environment_wsgi['HTTP_' + key.upper().replace('-', '_')] = value
        content = b''.join(static(environment_wsgi, start))
        if result['status'] == 200:
            web = Path(__file__).parent / 'web'
            if path in ('', 'admin'):
                for asset in ('app.js', 'realtime.js', 'mobile_controls.js', 'map_artwork.js', 'style.css', 'admin.js', 'admin.css'):
                    digest = hashlib.sha256((web / asset).read_bytes()).hexdigest()[:16]
                    content = content.replace(('"/' + asset + '"').encode(), ('"/' + asset + '?v=' + digest + '"').encode())
                result['headers']['Content-Length'] = str(len(content))
                result['headers']['Cache-Control'] = 'no-cache'
            else:
                digest = hashlib.sha256(content).hexdigest()[:16]
                result['headers']['Cache-Control'] = 'public, max-age=31536000, immutable' if request.query_params.get('v') == digest else 'public, max-age=0, must-revalidate'
                result['headers']['ETag'] = '"' + digest + '"'
                if request.headers.get('if-none-match') == result['headers']['ETag']:
                    result['headers'].pop('Content-Length', None)
                    return Response(status_code=304, headers=result['headers'])
        return Response(content, status_code=result['status'], headers=result['headers'])

    return app
