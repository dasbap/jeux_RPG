'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const timers = new Map();
const intervals = new Set();
let next = 0;
let now = 0;
let documentListeners = 0;
let connections = 0;
class Socket {
  static OPEN = 1;
  constructor() {
    connections++;
    this.readyState = 0;
    this.events = new Map();
    Socket.last = this;
    queueMicrotask(() => { this.readyState = 1; this.emit('open'); });
  }
  addEventListener(name, handler) {
    assert(!this.events.has(name), 'Un seul listener par evenement/socket');
    this.events.set(name, handler);
  }
  emit(name, event = {}) { this.events.get(name)?.(event); }
  send(raw) {
    const item = JSON.parse(raw);
    if (item.type === 'authenticate') queueMicrotask(() => this.emit('message', {data: JSON.stringify({type: 'authenticated'})}));
    else if (item.id) queueMicrotask(() => this.emit('message', {data: JSON.stringify({id: item.id, result: {status: 200, body: {ok: true}}})}));
  }
  close() { this.readyState = 3; queueMicrotask(() => this.emit('close')); }
}
const context = {
  WebSocket: Socket, location: new URL('https://fixture.vercel.app/'), URL, structuredClone,
  document: {hidden: false, addEventListener() { documentListeners++; }},
  Date: class extends Date { static now() { return now; } },
  fetch: async () => { throw new Error('Repli HTTP inattendu'); },
  setTimeout(callback, delay) { const id = ++next; timers.set(id, {callback, due: now + delay}); return id; },
  clearTimeout(id) { timers.delete(id); },
  setInterval() { const id = ++next; intervals.add(id); return id; },
  clearInterval(id) { intervals.delete(id); },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../jeuxRPG/multiplayer/web/realtime.js'), 'utf8'), context);
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  const request = () => context.rpgRealtime.request('/api/state', {headers: {Authorization: 'Bearer fixture'}});
  await request();
  for (let cycle = 0; cycle < 500; cycle++) {
    Socket.last.close();
    await settle();
    assert.equal(intervals.size, 0);
    assert.equal(timers.size, 1);
    now += 31000;
    for (const [id, timer] of [...timers]) if (timer.due <= now) { timers.delete(id); timer.callback(); }
    await settle();
    assert.equal(context.rpgRealtime.connected, true);
    assert.equal(intervals.size, 1);
    await request();
    assert.equal(timers.size, 0);
  }
  context.rpgRealtime.close();
  await settle();
  assert.equal(timers.size, 0);
  assert.equal(intervals.size, 0);
  assert.equal(documentListeners, 1);
  assert.equal(connections, 501);
  console.log('500 reconnexions: 501 sockets, 1 listener document, aucun timer restant apres fermeture. Horloge simulee; pas une mesure de fuite heap navigateur.');
})().catch(error => { console.error(error); process.exitCode = 1; });
