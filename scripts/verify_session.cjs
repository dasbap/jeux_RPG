"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {test} = require("node:test");

// Exercise the production refresh/command functions without a live server.
const source = fs.readFileSync(path.join(__dirname, "../jeuxRPG/multiplayer/web/app_session.js"), "utf8");
const functions = source.slice(0, source.indexOf('$("register-form")'));
const snapshot = revision => ({id: "room", revision, state: "running"});
const stale = () => Object.assign(new Error("Version refusée"), {code: "stale_revision"});
function setup(api) {
  const elements = new Map();
  const messages = [];
  let sequence = 0;
  const context = {
    api, session: snapshot(10), sessionId: "room", stateEpoch: 0,
    busy: false, polling: false, gameMode: "online", token: "test",
    accountState: {selected: "player"}, refreshFailures: 0, nextRefreshAt: 0,
    lastPlayer: null, pendingBattleMove: null, rpgRealtime: {},
    $: id => {
      if (!elements.has(id)) elements.set(id, {hidden: true});
      return elements.get(id);
    },
    requestId: () => String(++sequence),
    message: text => { if (text) messages.push(text); },
    render() {}, renderGame() {}, remember() {}, scheduleRefresh() {},
  };
  vm.createContext(context);
  vm.runInContext(functions, context);
  return {context, messages};
}

test("a rejected future revision recovers using the lower server revision", async () => {
  const revisions = [];
  const {context, messages} = setup(async (url, body) => {
    if (url === "/api/state") return {session: snapshot(9)};
    revisions.push(body.params.revision);
    if (body.params.revision > 9) throw stale();
    return {session: snapshot(10)};
  });
  await context.command("strike", {session_id: "room", revision: 10});
  assert.deepEqual(revisions, [10, 9]);
  assert.equal(context.session.revision, 10);
  assert.deepEqual(messages, []);
  assert.equal(context.busy, false);
});

test("movement is recalculated from the recovered map and world context", async () => {
  const recovered = {...snapshot(9), tutorial: {world_context: "new-map"}};
  const requests = [];
  const {context} = setup(async (url, body) => {
    if (url === "/api/state") return {session: recovered};
    requests.push(body.params);
    if (requests.length === 1) throw stale();
    return {session: snapshot(10)};
  });
  context.worldPaths = (tutorial, destination) => {
    assert.equal(tutorial.world_context, "new-map");
    assert.equal(destination, "village");
    return {newRoute: [[1, 2]]};
  };
  await context.command("move", {session_id: "room", revision: 10, destination: "village", world_context: "old-map", paths: {oldRoute: []}});
  assert.equal(requests[1].revision, 9);
  assert.equal(requests[1].world_context, "new-map");
  assert.deepEqual(requests[1].paths, {newRoute: [[1, 2]]});
});

test("polling started before recovery cannot replace the recovered state", async () => {
  let rejectCommand, resolvePoll;
  let stateCalls = 0;
  let commandCalls = 0;
  const {context} = setup((url) => {
    if (url === "/api/state") {
      if (++stateCalls === 1) return new Promise(resolve => { resolvePoll = resolve; });
      return Promise.resolve({session: snapshot(9)});
    }
    if (++commandCalls === 1) return new Promise((_, reject) => { rejectCommand = reject; });
    return Promise.resolve({session: snapshot(10)});
  });
  const command = context.command("strike", {session_id: "room", revision: 10});
  const poll = context.refresh(true);
  rejectCommand(stale());
  await command;
  resolvePoll({session: snapshot(99)});
  await poll;
  assert.equal(context.session.revision, 10);
});

test("ordinary polling still ignores older responses", async () => {
  const {context} = setup(async () => ({session: snapshot(9)}));
  await context.refresh(true);
  assert.equal(context.session.revision, 10);
});

test("recovery does not replay a command in a different session", async () => {
  let commands = 0;
  const {context, messages} = setup(async url => {
    if (url === "/api/state") return {session: {...snapshot(9), id: "other-room"}};
    commands++;
    throw stale();
  });
  await context.command("strike", {session_id: "room", revision: 10});
  assert.equal(commands, 1);
  assert.equal(context.session.id, "room");
  assert.equal(messages.length, 1);
});

test("persistent rejections stop after five attempts", async () => {
  const revisions = [];
  const {context, messages} = setup(async (url, body) => {
    if (url === "/api/state") return {session: snapshot(9)};
    revisions.push(body.params.revision);
    throw stale();
  });
  await context.command("strike", {session_id: "room", revision: 10});
  assert.deepEqual(revisions, [10, 9, 9, 9, 9]);
  assert.equal(context.session.revision, 9);
  assert.equal(messages.length, 1);
  assert.equal(context.busy, false);
});
