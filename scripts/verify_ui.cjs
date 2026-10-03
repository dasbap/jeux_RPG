const assert = require("node:assert/strict");
const {randomUUID} = require("node:crypto");
const {JSDOM, VirtualConsole} = require("jsdom");
const origin = process.env.RPG_TEST_ORIGIN || "http://127.0.0.1:8080";
const errors = [];
const clients = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(condition, label) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (await condition()) return;
    await pause(50);
  }
  throw new Error(`Interface bloquée : ${label}`);
}
const el = (dom, id) => dom.window.document.getElementById(id);
async function request(dom, path, body) {
  const token = dom.window.sessionStorage.getItem("rpg-token");
  const response = await fetch(new URL(path, origin), {method: body ? "POST" : "GET", headers: {Authorization: `Bearer ${token}`, ...(body ? {"Content-Type": "application/json"} : {})}, body: body ? JSON.stringify(body) : undefined});
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.message), {code: data.error});
  return data;
}
async function command(dom, action, params = {}) {
  for (let retry = 0; retry < 3; retry++) {
    const state = await request(dom, "/api/state");
    try {
      return await request(dom, "/api/commands", {request_id: randomUUID(), action, params: {...(action === "tutorial" || action === "create" || action === "join" ? {} : {session_id: state.session.id, revision: state.session.revision}), ...params}});
    } catch (error) { if (error.code !== "stale_revision") throw error; }
  }
  throw new Error("Révisions instables");
}
async function client(html, app, name, className) {
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", error => errors.push(error.message));
  const dom = new JSDOM(html, {url: origin, runScripts: "outside-only", virtualConsole});
  clients.push(dom);
  dom.window.fetch = (url, options) => fetch(new URL(url, origin), options);
  dom.window.AbortSignal = AbortSignal;
  dom.window.crypto.randomUUID = randomUUID;
  dom.window.eval(app);
  el(dom, "name").value = name;
  el(dom, "class-name").value = className;
  el(dom, "register-form").dispatchEvent(new dom.window.Event("submit", {bubbles: true, cancelable: true}));
  await waitFor(() => !el(dom, "lobby").hidden, "inscription");
  return dom;
}
async function finishCombat(dom) {
  for (let attempt = 0; attempt < 600; attempt++) {
    const state = await request(dom, "/api/state");
    const adventure = state.session.tutorial;
    if (!adventure.mob) return;
    const me = adventure.players.find(p => p.id === state.session.me);
    if (me.hp > 0 && me.can_attack) await command(dom, "strike", {target: adventure.mobs[0].combat_id});
    else await pause(350);
  }
  throw new Error("Combat bloqué");
}
async function move(dom, destination) {
  await command(dom, "move", {destination});
  await finishCombat(dom);
}
async function main() {
  const html = await (await fetch(origin)).text();
  const app = await (await fetch(new URL("/app.js", origin))).text();
  try {
    const first = await client(html, app, "Alice <script>", "Knight");
    const second = await client(html, app, "Bob", "Priest");
    assert.notEqual(first.window.sessionStorage.getItem("rpg-token"), second.window.sessionStorage.getItem("rpg-token"));
    assert.equal(el(first, "player-name").querySelector("script"), null);
    const created = await command(first, "create");
    await command(second, "join", {invite: created.invite});
    await command(first, "tutorial");
    await waitFor(() => !el(first, "tutorial-panel").hidden && !el(second, "tutorial-panel").hidden, "tutoriel partagé");
    assert.equal(first.window.document.querySelector(".adventure-grid").children.length, 3);
    assert(el(first, "quest-view").closest(".quest-box"));
    assert(el(first, "combat-view").closest(".zone-actions"));
    assert(el(first, "map-view").closest(".consultation"));
    assert(!el(first, "quest-view").hidden);
    assert(!el(first, "standby-view").hidden);
    assert(el(first, "world-map").textContent.includes("Vous êtes ici"));
    assert.equal(el(first, "combat-target").options.length, 0);
    el(first, "show-stats").click();
    assert(!el(first, "stats-view").hidden && !el(first, "standby-view").hidden && !el(first, "quest-view").hidden);
    el(first, "show-map").click();
    const explore = [...el(first, "tutorial-actions").querySelectorAll("button")].find(b => b.textContent === "Explorer ce lieu");
    explore.click();
    await waitFor(() => !el(first, "combat-view").hidden && !el(second, "combat-view").hidden, "combat");
    assert(!el(first, "map-view").hidden && !el(first, "quest-view").hidden);
    assert.deepEqual([...el(first, "combat-target").options].map(o => o.value), ["mob"]);
    const initial = (await request(first, "/api/state")).session.tutorial.players.reduce((sum, p) => sum + p.hp, 0);
    await waitFor(async () => (await request(first, "/api/state")).session.tutorial.players.reduce((sum, p) => sum + p.hp, 0) < initial, "attaque autonome sans action joueur");
    await finishCombat(first);
    await move(first, "rosee");
    await waitFor(() => el(first, "position-label").textContent.includes("Village de Rosée") && el(first, "combat-view").hidden, "arrivée Rosée");
    await assert.rejects(command(first, "talk", {npc: "mira"}), error => error.code === "wrong_location");
    el(first, "show-map").click();
    el(first, "map-place").value = "rosee";
    el(first, "map-place").dispatchEvent(new first.window.Event("change", {bubbles: true}));
    [...el(first, "map-points").querySelectorAll("button")].find(b => b.textContent.includes("Mira")).click();
    [...el(first, "point-actions").querySelectorAll("button")].find(b => b.textContent === "Se déplacer à ce point").click();
    await waitFor(() => !el(first, "npc-view").hidden && !el(second, "npc-view").hidden, "déplacement point Mira");
    await command(first, "talk", {npc: "mira"});
    await move(first, "hunt");
    while ((await request(first, "/api/state")).session.tutorial.kills < 3) {
      await command(first, "explore");
      await finishCombat(first);
    }
    await move(first, "mira");
    await command(first, "talk", {npc: "mira"});
    await move(first, "forge");
    await waitFor(() => !el(first, "craft-view").hidden && !el(second, "craft-view").hidden, "forge partagée");
    await command(first, "craft", {recipe: "veste"});
    await command(second, "craft", {recipe: "veste"});
    await move(first, "brume");
    await waitFor(() => el(first, "battle-title").textContent === "Aventure accomplie" && el(second, "battle-title").textContent === "Aventure accomplie", "fin coopérative");
    el(first, "show-inventory").click();
    assert(!el(first, "inventory-view").hidden && !el(first, "quest-view").hidden);
    el(first, "show-bestiary").click();
    assert(el(first, "bestiary-details").textContent.includes("rang D"));
    el(first, "show-map").click();
    assert(el(first, "world-map").textContent.includes("Vous êtes ici"));
    assert.deepEqual(errors, []);
    console.log("UI HTTP vérifiée : deux joueurs, trois panneaux, déplacement vers Mira, combat autonome, quête, craft et arrivée à Brume.");
  } finally { clients.forEach(dom => dom.window.close()); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
