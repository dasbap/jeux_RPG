const assert = require("node:assert/strict");
const {randomUUID} = require("node:crypto");
const {JSDOM, VirtualConsole} = require("jsdom");

const origin = process.env.RPG_TEST_ORIGIN || "http://127.0.0.1:8080";
const errors = [];
let stage = "Duel";
const waitFor = async condition => {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    if (condition()) return;
    await new Promise(resolve => setTimeout(resolve, 30));
  }
  throw new Error(`L'interface n'a pas atteint l'état attendu : ${stage}.`);
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
  const third = await client(html, app);
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
    stage = "Nouveau salon";
    element(first, "new-room").click();
    await waitFor(() => !element(first, "invitation").hidden);
    element(second, "invite-input").value = element(first, "invite-code").textContent;
    submit(second, "join-form");
    stage = "Rejoindre le tutoriel";
    await waitFor(() => element(first, "fighters").children.length === 2 && !element(first, "party-tutorial").hidden);
    element(first, "party-tutorial").click();
    stage = "Démarrer le tutoriel";
    await waitFor(() => !element(first, "tutorial-panel").hidden && !element(second, "tutorial-panel").hidden);
    assert(!element(first, "standby-view").hidden);
    assert(element(first, "combat-view").hidden);
    assert(element(first, "target-controls").hidden);
    assert.equal(element(first, "combat-target").options.length, 0);
    assert.equal(first.window.document.querySelectorAll("#tutorial-actions button").length, 1);
    assert(!element(first, "tutorial-actions").textContent.includes("Mira"));
    element(first, "show-map").click();
    assert.equal(element(first, "map-place").options.length, 1);
    assert.equal(element(first, "world-map").querySelectorAll("g.map-node").length, 1);
    element(first, "show-bestiary").click();
    assert(element(first, "bestiary-details").textContent.includes("Aucun monstre rencontré"));
    element(first, "show-stats").click();
    assert(!element(first, "stats-view").hidden);
    assert(element(first, "standby-view").hidden);
    assert(element(first, "character-details").textContent.includes("Force"));
    element(first, "back-view").click();
    assert.equal(first.window.document.querySelector(".clock"), null);
    assert(!first.window.document.body.textContent.includes("×20"));
    async function tutorialAction(dom, label, expected) {
      stage = `${label} · ${element(dom, "location").textContent}`;
      let actualLabel = label;
      if (label.includes("Explorer") || label.includes("Essayer mes nouvelles") || label.includes("Parler à Mira") || label.includes("Entrer dans la forge") || label.includes("Rejoindre")) {
        element(dom, "show-map").click();
        const place = label.includes("Parler à Mira") || label.includes("Entrer dans la forge") || label.includes("Essayer mes nouvelles") || label.includes("Brume") ? "rosee" : label.includes("Rejoindre Rosée") ? "clearing" : element(dom, "map-place").value;
        element(dom, "map-place").value = place;
        element(dom, "map-place").dispatchEvent(new dom.window.Event("change", {bubbles: true}));
        if (label.includes("Rejoindre")) actualLabel = label.includes("Brume") ? "Prendre le chemin vers Village de Brume" : "Prendre le chemin vers Village de Rosée";
        else {
          const pointLabel = label.includes("Parler à Mira") ? "Mira" : label.includes("Entrer dans la forge") ? "Forge" : label.includes("Essayer mes nouvelles") ? "Terrain" : place === "clearing" ? "Sous-bois" : "Campement";
          const point = [...element(dom, "map-points").querySelectorAll("button")].find(b => b.textContent.includes(pointLabel));
          assert(point, `Point absent : ${pointLabel}`);
          point.click();
          actualLabel = label.includes("Parler à Mira") || label.includes("Entrer dans la forge") ? "Interagir avec ce point" : "Explorer ce point";
        }
      }
      let button;
      await waitFor(() => {
        button = [...element(dom, "tutorial-panel").querySelectorAll("button")].find(b => !b.closest("[hidden]") && b.textContent.toLowerCase().includes(actualLabel.toLowerCase()));
        return button && !button.disabled;
      });
      button.click();
      try { await waitFor(expected); }
      catch (error) { throw new Error(`${error.message} ${element(dom, "message").textContent} ${element(dom, "quest-progress").textContent} ${element(dom, "mob-hp").textContent}`); }
    }
    await tutorialAction(first, "Explorer", () => element(second, "mob-name").textContent.includes("Gobelin"));
    assert.deepEqual([...element(first, "combat-target").options].map(o => o.value), ["mob"]);
    assert.deepEqual([...element(second, "combat-target").options].map(o => o.value), ["mob"]);
    assert(!element(first, "combat-actions").textContent.includes("Récupérer"));
    await tutorialAction(first, "Sword Slash", () => element(second, "events").textContent.includes("utilise Sword Slash"));
    await tutorialAction(second, "Fire Ball", () => element(first, "location").textContent === "Sentier de Rosée");
    element(first, "show-map").click();
    element(first, "map-place").value = "rosee";
    element(first, "map-place").dispatchEvent(new first.window.Event("change", {bubbles: true}));
    assert(element(first, "place-details").textContent.includes("encore non visité"));
    assert.equal(element(first, "map-points").children.length, 0);
    await tutorialAction(first, "Rejoindre Rosée", () => element(second, "location").textContent === "Village de Rosée");
    await tutorialAction(first, "Parler à Mira", () => !element(first, "npc-view").hidden);
    assert(element(first, "combat-view").hidden);
    assert(element(first, "standby-view").hidden);
    await tutorialAction(first, "accepter la quête", () => element(second, "quest-progress").textContent.includes("0/3"));
    for (let count = 1; count <= 3; count++) {
      await tutorialAction(first, "Explorer", () => element(second, "mob-name").textContent.includes("Gobelin"));
      for (let hit = 0; hit < 5 && element(second, "mob-name").textContent; hit++) {
        const previous = element(second, "version").textContent;
        await tutorialAction(second, "Fire Ball", () => element(second, "version").textContent !== previous);
      }
      await waitFor(() => element(first, "quest-progress").textContent.includes(`${count}/3`));
    }
    element(first, "show-quest").click();
    assert(!element(first, "quest-view").hidden);
    await tutorialAction(first, "Parler à Mira", () => !element(first, "npc-view").hidden);
    await tutorialAction(first, "rendre la quête", () => element(first, "character-details").children[0].textContent.includes("niveau 5") && element(second, "character-details").children[0].textContent.includes("niveau 5"));
    assert(element(first, "character-details").textContent.includes("Shield Bash"));
    assert(element(second, "character-details").textContent.includes("Thunder"));
    await tutorialAction(first, "Essayer mes nouvelles", () => element(second, "mob-name").textContent.includes("Gobelin"));
    const previous = element(second, "version").textContent;
    await tutorialAction(second, "Thunder", () => element(second, "version").textContent !== previous);
    for (let hit = 0; hit < 5 && element(second, "mob-name").textContent; hit++) {
      const revision = element(second, "version").textContent;
      await tutorialAction(second, "Attaque simple", () => element(second, "version").textContent !== revision);
    }
    await waitFor(() => element(first, "events").textContent.includes("Entraînement terminé"));
    await tutorialAction(first, "Entrer dans la forge", () => !element(first, "craft-view").hidden);
    await tutorialAction(first, "Fabriquer et équiper", () => element(second, "events").textContent.includes("Alice <script> fabrique"));
    await tutorialAction(second, "Entrer dans la forge", () => !element(second, "craft-view").hidden);
    await tutorialAction(second, "Fabriquer et équiper", () => element(first, "location").textContent === "Route des Deux Villages");
    await tutorialAction(first, "Rejoindre Brume", () => element(first, "location").textContent === "Village de Brume" && element(second, "battle-title").textContent === "Aventure accomplie");
    assert.equal(element(first, "location").textContent, "Village de Brume");
    assert.equal(element(second, "location").textContent, "Village de Brume");
    element(first, "show-inventory").click();
    assert(element(first, "inventory-details").textContent.includes("2 peau"));
    assert(element(first, "inventory-details").textContent.includes("1 croc"));
    element(first, "show-equipment").click();
    assert(element(first, "equipment-details").textContent.includes("Veste"));
    element(first, "show-map").click();
    assert([...element(first, "map-place").options].every(option => option.textContent.includes("visité")));
    element(first, "map-place").value = "rosee";
    element(first, "map-place").dispatchEvent(new first.window.Event("change", {bubbles: true}));
    assert(element(first, "place-details").textContent.includes("déjà visité"));
    assert(element(first, "map-points").textContent.includes("Forge"));
    element(first, "show-bestiary").click();
    assert(element(first, "bestiary-details").textContent.includes("Gobelin"));
    assert(element(first, "bestiary-details").textContent.includes("Faiblesses : aucune"));
    assert(element(first, "bestiary-details").textContent.includes("1 peau, 1 croc"));
    assert.equal(element(first, "events").querySelector("script"), null);
    stage = "Cibles du prêtre";
    element(third, "name").value = "Soigneur";
    element(third, "class-name").value = "Priest";
    submit(third, "register-form");
    await waitFor(() => !element(third, "lobby").hidden);
    element(third, "tutorial").click();
    await waitFor(() => !element(third, "tutorial-panel").hidden);
    assert(element(third, "target-controls").hidden);
    assert.equal(element(third, "combat-target").options.length, 0);
    await tutorialAction(third, "Explorer", () => !element(third, "combat-view").hidden);
    assert.deepEqual([...element(third, "combat-target").options].map(o => o.value), ["mob"]);
    assert(!element(third, "skills").textContent.includes("Heal"));
    const priestVersion = element(third, "version").textContent;
    await tutorialAction(third, "Attaque simple", () => element(third, "version").textContent !== priestVersion);
    assert(element(third, "target-controls").hidden);
    await waitFor(() => [...element(third, "combat-target").options].some(o => o.value !== "mob"));
    element(third, "combat-target").value = [...element(third, "combat-target").options].find(o => o.value !== "mob").value;
    element(third, "combat-target").dispatchEvent(new third.window.Event("change", {bubbles: true}));
    assert(element(third, "skills").textContent.includes("Heal"));
    assert(!element(third, "combat-actions").textContent.includes("Attaque simple"));
    element(third, "show-stats").click();
    assert(element(third, "combat-view").hidden);
    assert(!element(third, "stats-view").hidden);
    element(third, "back-view").click();
    await tutorialAction(third, "Heal", () => element(third, "events").textContent.includes("utilise Heal"));
    assert.equal(errors.length, 0, errors.join("\n"));
    console.log("UI validée : menu, caractéristiques, inventaire, équipement, carte découverte, villages visités, points stratégiques, bestiaire et tutoriel coopératif complet.");
  } finally {
    for (const dom of [first, second, third]) for (const timer of dom.intervals) dom.window.clearInterval(timer);
    await waitFor(() => first.pending === 0 && second.pending === 0 && third.pending === 0);
    await new Promise(resolve => setTimeout(resolve, 50));
    first.window.close();
    second.window.close();
    third.window.close();
  }
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
