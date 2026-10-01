const assert = require("node:assert/strict");
const {randomUUID} = require("node:crypto");
const {JSDOM, VirtualConsole} = require("jsdom");

const origin = process.env.RPG_TEST_ORIGIN || "http://127.0.0.1:8080";
const errors = [];
const waitFor = async condition => {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    if (condition()) return;
    await new Promise(resolve => setTimeout(resolve, 30));
  }
  throw new Error("L'interface n'a pas atteint l'état attendu.");
};

async function client(html, app) {
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", error => errors.push(error.message));
  const dom = new JSDOM(html, {url: origin, runScripts: "outside-only", virtualConsole});
  dom.pending = 0;
  dom.intervals = [];
  const setInterval = dom.window.setInterval.bind(dom.window);
  dom.window.setInterval = (callback, delay) => {
    const timer = setInterval(callback, delay);
    dom.intervals.push(timer);
    return timer;
  };
  dom.window.fetch = async (url, options) => {
    dom.pending++;
    try { return await fetch(new URL(url, origin), options); }
    finally { dom.pending--; }
  };
  dom.window.AbortSignal = AbortSignal;
  dom.window.crypto.randomUUID = randomUUID;
  dom.window.eval(app);
  return dom;
}

const element = (dom, id) => dom.window.document.getElementById(id);
function submit(dom, id) {
  element(dom, id).dispatchEvent(new dom.window.Event("submit", {bubbles: true, cancelable: true}));
}

async function main() {
  const html = await (await fetch(origin)).text();
  const app = await (await fetch(new URL("/app.js", origin))).text();
  const first = await client(html, app);
  const second = await client(html, app);
  try {
    assert.equal(element(first, "connection").textContent, "Prêt · créez votre personnage");
    element(first, "name").value = "Alice <script>";
    submit(first, "register-form");
    element(second, "name").value = "Bob";
    element(second, "class-name").value = "Mage";
    submit(second, "register-form");
    await waitFor(() => !element(first, "lobby").hidden && !element(second, "lobby").hidden);
    assert.notEqual(first.window.sessionStorage.getItem("rpg-token"), second.window.sessionStorage.getItem("rpg-token"));
    assert.equal(element(first, "player-name").textContent, "Alice <script> · Chevalier");
    assert.equal(element(first, "player-name").querySelector("script"), null);
    element(first, "create").click();
    await waitFor(() => !element(first, "invitation").hidden);
    element(second, "invite-input").value = element(first, "invite-code").textContent;
    submit(second, "join-form");
    await waitFor(() => element(first, "fighters").children.length === 2 && element(second, "fighters").children.length === 2);
    assert(element(second, "start").hidden);
    await waitFor(() => !element(first, "start").disabled);
    element(first, "start").click();
    await waitFor(() => !element(first, "attack").hidden && !element(second, "attack").hidden);
    element(first, "attack").click();
    await waitFor(() => element(second, "events").textContent.includes("Alice <script> attaque"));
    assert(element(first, "attack").disabled);
    assert(element(second, "events").textContent.includes("Alice <script>"));
    assert.equal(element(second, "events").querySelector("script"), null);
    await waitFor(() => !element(first, "attack").disabled);
    element(second, "leave").click();
    await waitFor(() => element(first, "battle-title").textContent === "Duel terminé");
    assert.equal(element(first, "result").textContent, "Alice <script> remporte le duel.");
    assert.equal(errors.length, 0, errors.join("\n"));
    console.log("UI fonctionnelle validée : deux identités, invitation, duel, état partagé, cooldown, abandon et rendu du texte utilisateur.");
  } finally {
    for (const dom of [first, second]) for (const timer of dom.intervals) dom.window.clearInterval(timer);
    await waitFor(() => first.pending === 0 && second.pending === 0);
    await new Promise(resolve => setTimeout(resolve, 50));
    first.window.close();
    second.window.close();
  }
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
