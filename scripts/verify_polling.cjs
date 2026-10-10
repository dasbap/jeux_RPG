"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../jeuxRPG/multiplayer/web/app_session.js"), "utf8");
const refresh = source.slice(source.indexOf("async function refresh("), source.indexOf("async function command("));
const startup = source.slice(source.includes("let refreshTimer") ? source.indexOf("let refreshTimer") : source.indexOf('window.addEventListener("online"'));

function setup(settings = {}) {
  let now = 0, nextId = 0, requests = 0, inflight = 0, peak = 0;
  const timers = new Map(), events = {}, nodes = new Map();
  const session = settings.session === undefined ? {id: "room", revision: 1, state: "running", tutorial: {}} : settings.session;
  const context = {
    token: "token", session, sessionId: session?.id || "", accountState: {selected: "player"},
    polling: false, stateEpoch: 0, nextRefreshAt: 0, refreshFailures: 0, currentView: "map", busy: false,
    bundleHashes: {}, bundleValues: {}, lastPlayer: null, location: {hostname: "game.vercel.app"},
    Date: class extends Date {static now() {return now;}}, Math: Object.assign(Object.create(Math), {random: () => .5}),
    navigator: {onLine: true}, document: {hidden: false, addEventListener: (name, fn) => {events[name] = fn;}},
    window: {addEventListener: (name, fn) => {events[name] = fn;}},
    $: id => {if (!nodes.has(id)) nodes.set(id, {hidden: id === "characters"}); return nodes.get(id);},
    render() {}, remember() {}, renderCharacters() {}, message() {},
    setTimeout: (fn, delay) => {const id = ++nextId; timers.set(id, {fn, at: now + delay}); return id;},
    clearTimeout: id => timers.delete(id), clearInterval: id => timers.delete(id),
    setInterval: (fn, delay) => {const id = ++nextId; timers.set(id, {fn, at: now + delay, interval: delay}); return id;},
    api: async () => {
      requests++; inflight++; peak = Math.max(peak, inflight);
      try {
        await Promise.resolve();
        if (settings.failure) throw Object.assign(new Error("offline"), {code: "timeout"});
        return {session};
      } finally {inflight--;}
    }
  };
  Object.assign(context, settings.context);
  Object.assign(context.document, settings.document);
  vm.createContext(context);
  const settle = async () => {for (let i = 0; i < 12; i++) await Promise.resolve();};
  async function advance(duration) {
    await settle();
    const end = now + duration;
    for (;;) {
      const next = [...timers.entries()].sort((a, b) => a[1].at - b[1].at)[0];
      if (!next || next[1].at > end) break;
      const [id, timer] = next;
      now = timer.at;
      if (timer.interval) timer.at += timer.interval;
      else timers.delete(id);
      timer.fn();
      await settle();
    }
    now = end;
    await settle();
  }
  vm.runInContext(refresh + startup, context);
  return {context, events, advance, settle, count: () => requests, peak: () => peak};
}

(async () => {
  const cases = {
    exploration: {}, battle: {session: {id: "room", revision: 1, tutorial: {battle: {}}}},
    menu: {context: {currentView: "inventory"}}, lobby: {session: null},
    field_idle: {session: {id: "room", revision: 1, tutorial: {field_map: "rosee", battle: {players: {}}, mobs: []}}},
    field_combat: {session: {id: "room", revision: 1, tutorial: {field_map: "hunt", battle: {}, mobs: [{alerted: true, stats: {hp: {current: 10}}}]}}},
    movement: {session: {id: "room", revision: 1, tutorial: {field_map: "rosee", battle: {players: {player: {route: [[1, 2]]}}}}}},
    hidden: {document: {hidden: true}}, disconnected: {context: {token: ""}},
    offline: {context: {navigator: {onLine: false}}}, failure: {failure: true},
    websocket: {context: {rpgRealtime: {connected: true}}}
  };
  const measurements = {};
  for (const [name, settings] of Object.entries(cases)) {
    const run = setup(settings);
    await run.advance(120000);
    measurements[name] = run.count();
    if (!process.argv.includes("--measure")) assert.equal(run.peak(), name === "disconnected" || name === "offline" ? 0 : 1);
  }
  console.log(JSON.stringify({duration_ms: 120000, requests: measurements}));
  if (process.argv.includes("--measure")) return;
  assert(measurements.exploration <= 35);
  assert(measurements.menu <= 9);
  assert(measurements.lobby <= 25);
  assert(measurements.hidden <= 7);
  assert.equal(measurements.disconnected, 0);
  assert.equal(measurements.offline, 0);
  assert.equal(measurements.websocket, 1);
  assert(measurements.failure <= 10);
  assert(measurements.battle >= 100 && measurements.battle <= 121);
  assert.equal(measurements.field_idle, measurements.exploration);
  assert.equal(measurements.field_combat, measurements.battle);
  assert.equal(measurements.movement, measurements.battle);
  const visible = setup({document: {hidden: true}});
  await visible.advance(5000);
  const before = visible.count();
  visible.context.document.hidden = false;
  await visible.events.visibilitychange();
  await visible.settle();
  assert.equal(visible.count(), before + 1);
  const concurrent = setup();
  await concurrent.settle();
  await Promise.all([vm.runInContext("refresh(true)", concurrent.context), vm.runInContext("refresh(true)", concurrent.context)]);
  assert.equal(concurrent.peak(), 1);
  console.log("Polling : fréquences, visibilité, retour immédiat, mode hors ligne et absence de chevauchement vérifiés.");
})().catch(error => {console.error(error); process.exitCode = 1;});
