const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../multiplayer/web/app.js"), "utf8");
const command = source.slice(source.indexOf("async function command("), source.indexOf('$("register-form").addEventListener'));
async function check(conflicts, failure) {
  const revisions = [], messages = [];
  let reads = 0;
  const context = {
    busy: false, stateEpoch: 0, sessionId: "room", session: {id: "room", revision: 0},
    crypto: {randomUUID: () => "request"},
    $: () => ({disabled: false, hidden: false}),
    remember: () => {}, refresh: async () => {},
    message: (message, error) => messages.push({message, error}),
    api: async (url, body) => {
      if (url === "/api/state") return {session: {id: "room", revision: ++reads}};
      revisions.push(body.params.revision);
      if (failure) throw Object.assign(new Error("Cible invalide"), {code: "invalid_target"});
      if (revisions.length <= conflicts) throw Object.assign(new Error("État modifié"), {code: "stale_revision"});
      return {session: {id: "room", revision: reads + 1, state: "running"}};
    }
  };
  vm.createContext(context);
  await vm.runInContext(`"use strict"; ${command}; command("leave_battle", {session_id: "room", revision: 0});`, context);
  assert.equal(context.busy, false);
  if (failure) {
    assert.equal(revisions.length, 1);
    assert.equal(reads, 0);
    assert(messages.some(message => message.error && message.message === "Cible invalide"));
  } else {
    assert.deepEqual(revisions, [0, 1, 2, 3]);
    assert.equal(context.session.revision, 4);
    assert(!messages.some(message => message.error));
  }
}
async function checkLateSnapshot() {
  const refreshSource = source.slice(source.indexOf("async function refresh("), source.indexOf("async function command("));
  let resolveRead;
  let renders = 0;
  const context = {token: "token", polling: false, busy: false, tacticalInteractionUntil: 0, stateEpoch: 0,
    sessionId: "room", session: {id: "room", revision: 1}, Date,
    api: () => new Promise(resolve => {resolveRead = resolve;}), remember: () => {},
    render: () => {renders++;}, $: () => ({}), message: () => {}};
  vm.createContext(context);
  const pending = vm.runInContext(`${refreshSource}; refresh();`, context);
  context.stateEpoch++;
  context.session = {id: "room", revision: 3};
  resolveRead({session: {id: "room", revision: 2}});
  await pending;
  assert.equal(context.session.revision, 3);
  assert.equal(renders, 0);
  assert.equal(context.polling, false);
  const oldRevision = vm.runInContext("refresh();", context);
  resolveRead({session: {id: "room", revision: 2}});
  await oldRevision;
  assert.equal(context.session.revision, 3);
  assert.equal(renders, 0);
}
Promise.resolve().then(checkLateSnapshot).then(() => check(3, false)).then(() => check(0, true)).then(() => console.log("UI : sortie après trois conflits de révision et refus métier sans répétition vérifiés.")).catch(error => { console.error(error); process.exitCode = 1; });
