import asyncio
import json
import logging
import os
import time
import uuid
from collections import OrderedDict, defaultdict
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from redis.asyncio import Redis

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
        self.prefix = 'jeux-rpg:runtime:v1:'
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
        result = await self.redis.eval(LEASE, 2, self.prefix + 'lease', self.prefix + 'fence', self.uid, str(time.time_ns() // 1000))
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
                    self.store.pending[(table, tuple(row[key] for key in KEYS[table]))] = row
                self.store.due = time.monotonic() + 5 if self.store.pending else None
            else:
                self.store = await asyncio.to_thread(RuntimeStore.load, self.environment)
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
                while not self.received.empty():
                    item = self.received.get_nowait()
                    if not self.owner():
                        continue
                    if item['id'] not in self.seen:
                        self.seen[item['id']] = await self.execute(item['message'])
                        if len(self.seen) > 256:
                            self.seen.popitem(last=False)
                    self.outgoing['reply:' + item['source']].append({'id': item['id'], 'result': self.seen[item['id']]})
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger(__name__).warning('Lot temps réel non livré')

    async def execute(self, message):
        async with self.lock:
            if not self.owner():
                return {'status': 503, 'headers': {}, 'body': {'error': 'unavailable', 'message': 'Reconnexion du moteur en cours.'}}
            return self.store.request(message)

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
                checkpoint = json.dumps({'durable': json.loads(snapshot), 'pending': [{'table': table, 'row': row} for (table, key), row in batch.items()], 'save_id': save_id}, separators=(',', ':'))
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
            await asyncio.sleep(.1)
            if not self.owner():
                continue
            try:
                async with self.lock:
                    if not self.owner():
                        continue
                    self.store.tick()
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
        if self.pubsub:
            await self.pubsub.aclose()
        if self.redis:
            await self.redis.aclose()
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
        await websocket.accept()
        coordinator.connections += 1
        send_lock = asyncio.Lock()
        subscription = None

        async def send(value):
            async with send_lock:
                await websocket.send_json(value)

        async def push():
            while True:
                await asyncio.sleep(.5 if coordinator.owner() else 1)
                if subscription is not None:
                    try:
                        result = await coordinator.rpc(subscription)
                    except (TimeoutError, RuntimeError, OSError):
                        with suppress(RuntimeError, WebSocketDisconnect):
                            await websocket.close(code=1012)
                        return
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
                item = json.loads(raw)
                if item.get('type') == 'ping':
                    await send({'type': 'pong'})
                    continue
                path = item.get('path', '')
                headers = item.get('headers', {})
                if not isinstance(path, str) or len(path) > 256 or not path.startswith('/api/') or path.startswith('/api/admin/') or path == '/api/ws' or not isinstance(headers, dict) or any(not isinstance(v, str) or len(v) > 8192 for v in headers.values()):
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
                message = trusted(request, '/' + path + ('?' + request.url.query if request.url.query else ''), request.method, json.loads(raw) if raw else None)
                result = await coordinator.rpc(message)
                if request.method == 'POST' and result['status'] < 300 and coordinator.owner() and not coordinator.connections:
                    await coordinator.flush()
                if coordinator.owner() and not coordinator.connections:
                    await coordinator.release()
                headers = {key: value for key, value in result['headers'].items() if key.lower() != 'content-length'}
                return JSONResponse(result['body'], status_code=result['status'], headers=headers)
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
        return Response(content, status_code=result['status'], headers=result['headers'])

    return app
