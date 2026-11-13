// Exercise the Worker against local SQLite with D1-style atomic batches.
// This does not replace a verification against Cloudflare D1.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "../cloudflare/d1-worker.mjs";

const db = new DatabaseSync(":memory:");
db.exec("PRAGMA foreign_keys=ON");
db.exec("CREATE TABLE schema_version(id INTEGER PRIMARY KEY,version INTEGER NOT NULL); INSERT INTO schema_version VALUES(1,3)");
for (const name of ["0001_initial", "0002_receipt_expiry", "0003_guilds"]) {
  db.exec(readFileSync(new URL(`../jeuxRPG/multiplayer/migrations/${name}.sql`, import.meta.url), "utf8"));
}
db.exec(readFileSync(new URL("../cloudflare/0004_fence_guard.sql", import.meta.url), "utf8"));
const binding = {
  prepare(sql) {
    let parameters = [];
    return {
      bind(...values) { parameters = values; return this; },
      async first() { return this.execute().results[0] || null; },
      execute() {
        const statement = db.prepare(sql);
        if (statement.columns().length) return { results: statement.all(...parameters) };
        statement.run(...parameters);
        return { results: [] };
      },
    };
  },
  async batch(statements) {
    db.exec("BEGIN");
    try {
      const results = statements.map(statement => statement.execute());
      db.exec("COMMIT");
      return results;
    } catch (error) {
      db.exec("ROLLBACK");
      throw error;
    }
  },
  withSession() { return this; },
};
const token = "fixture-service-token-".repeat(2);
async function request(body, authorization = `Bearer ${token}`) {
  return worker.fetch(new Request("https://fixture.invalid/", {
    method: "POST", headers: { authorization }, body: JSON.stringify(body),
  }), { DB: binding, RPG_D1_SERVICE_TOKEN: token });
}
const player = { id: "alice", token_hash: "hash", scope: "local", external_id: null, name: "Alice", class_name: "Knight", hp: 100, damage: 10 };
try {
  const health = await request({ operation: "health" });
  assert.equal(health.status, 200);
  assert.equal((await health.json()).fence_guards, 2);
  assert.equal((await request(null)).status, 400);
  assert.equal((await request({ operation: "load_snapshot", fence: 1 }, "Bearer bad")).status, 401);
  const response = await request({ operation: "persist_checkpoint", fence: 20, changes: [
    // Child deliberately precedes parent, as it can in a captured runtime batch.
    { table: "account_status", key: ["alice"], row: { player_id: "alice", suspended: 0 } },
    { table: "players", key: ["alice"], row: player },
  ] });
  assert.equal(response.status, 200, await response.text());
  const stale = await request({ operation: "persist_checkpoint", fence: 19, changes: [
    { table: "players", key: ["alice"], row: { ...player, hp: 1 } },
  ] });
  assert.equal(stale.status, 409);
  assert.equal((await stale.json()).error, "stale_runtime_fence");
  assert.equal(db.prepare("SELECT hp FROM players").get().hp, 100);
  const invalid = await request({ operation: "persist_checkpoint", fence: 21, changes: [
    { table: "players", key: ["alice"], row: { ...player, hp: 1 } },
    { table: "account_status", key: ["missing"], row: { player_id: "missing", suspended: 0 } },
  ] });
  assert.equal(invalid.status, 409);
  assert.equal(db.prepare("SELECT hp FROM players").get().hp, 100);
  assert.equal(db.prepare("SELECT value FROM meta WHERE key='runtime_fence'").get().value, "20");
  const loaded = await request({ operation: "load_snapshot", fence: 22 });
  assert.equal(loaded.status, 200);
  assert.equal((await loaded.json()).data.players[0].id, "alice");
  const inspected = await request({ operation: "read_snapshot" });
  assert.equal(inspected.status, 200);
  assert.deepEqual((await inspected.json()).sequences, []);
  assert.equal(db.prepare("SELECT value FROM meta WHERE key='runtime_fence'").get().value, "22");
  const claimed = await request({ operation: "claim_snapshot" });
  assert.equal(claimed.status, 200);
  assert.equal((await claimed.json()).data.meta.find(row => row.key === "runtime_fence").value, "23");
  const claimedAgain = await request({ operation: "claim_snapshot" });
  assert.equal((await claimedAgain.json()).data.meta.find(row => row.key === "runtime_fence").value, "24");
  const oldEngine = await request({ operation: "persist_checkpoint", fence: 23, changes: [] });
  assert.equal(oldEngine.status, 409);
  assert.equal((await oldEngine.json()).error, "stale_runtime_fence");
  db.exec("DROP TRIGGER reject_stale_runtime_fence_update");
  assert.equal((await request({ operation: "health" })).status, 503);
  console.log("Worker D1 : relations différées, rollback et rejet des anciens moteurs vérifiés sur SQLite local.");
} finally {
  db.close();
}
