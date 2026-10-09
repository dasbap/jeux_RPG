const assert = require("node:assert/strict");
const {resumeJourneyStep} = require("./demo_authored_ui.cjs");
const {randomUUID} = require("node:crypto");
const {JSDOM, VirtualConsole} = require("jsdom");
const origin = process.env.RPG_TEST_ORIGIN || "http://127.0.0.1:8080";
const errors = [];
const clients = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(condition, label, timeout = 10000, diagnostics = null) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await condition()) return;
    await pause(50);
  }
  const details = diagnostics ? diagnostics() : "";
  throw new Error(`Interface bloquée : ${label}${details ? " · " + details : ""}`);
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
  for (let retry = 0; retry < 15; retry++) {
    const state = await request(dom, "/api/state");
    try {
      const result = await request(dom, "/api/commands", {request_id: randomUUID(), action, params: {...(action === "tutorial" || action === "create" || action === "join" ? {} : {session_id: state.session.id, revision: state.session.revision}), ...params}});
      await dom.window.demoRefresh();
      return result;
    } catch (error) { if (error.code !== "stale_revision") throw error; }
  }
  throw new Error("Révisions instables");
}
async function client(html, app, name, className) {
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", error => errors.push(error.message));
  const dom = new JSDOM(html, {url: origin, runScripts: "outside-only", virtualConsole, pretendToBeVisual: true});
  clients.push(dom);
  dom.pollTimers = [];
  const startInterval = dom.window.setInterval.bind(dom.window);
  dom.window.setInterval = (...args) => { const id = startInterval(...args); dom.pollTimers.push(id); return id; };
  dom.window.fetch = (url, options) => fetch(new URL(url, origin), options);
  dom.window.AbortSignal = AbortSignal;
  dom.window.AbortController = AbortController;
  dom.window.crypto.randomUUID = randomUUID;
  dom.window.confirm = () => true;
  dom.window.eval(app + ";window.demoSnapshot = () => session; window.demoReady = () => !busy; window.demoRefresh = () => refresh(true); window.testFns = {battleAllowed, gridPath, requestTravel, flags: () => ({busy, polling, revision: session?.revision})};");
  el(dom, "account-name").value = "test_" + randomUUID().slice(0, 8);
  el(dom, "account-password").value = randomUUID();
  el(dom, "name").value = name;
  el(dom, "class-name").value = className;
  el(dom, "register-form").dispatchEvent(new dom.window.Event("submit", {bubbles: true, cancelable: true}));
  await waitFor(
    () => !el(dom, "lobby").hidden,
    "inscription",
    30000,
    () => `${el(dom, "message").textContent || "aucun message"} / ${el(dom, "connection").textContent || "aucun état de connexion"} / busy=${dom.window.demoReady ? !dom.window.demoReady() : "inconnu"}`
  );
  return dom;
}
async function closeClient(dom) {
  for (const timer of dom.pollTimers || []) dom.window.clearInterval(timer);
  await waitFor(() => { const flags = dom.window.testFns.flags(); return !flags.busy && !flags.polling; }, "requêtes terminées avant fermeture");
  dom.window.close();
}
async function finishCombat(dom) {
  for (let attempt = 0; attempt < 1200; attempt++) {
    const state = await request(dom, "/api/state");
    const adventure = state.session.tutorial;
    const me = adventure.players.find(p => p.id === state.session.me);
    if (!adventure.battle) {
      if (adventure.moving || adventure.transit || adventure.journey.length) { await pause(50); continue; }
      return;
    }
    if (me.casting || me.hp <= 0 || me.stunned || me.cooldown_real_seconds > 0) { await pause(50); continue; }
    for (const ally of clients.filter(client => client !== dom && !client.window.closed)) {
      const supportState = await request(ally, "/api/state");
      if (supportState.session?.id !== state.session.id) continue;
      const support = supportState.session.tutorial.players.find(p => p.id === supportState.session.me);
      const heal = support.skills.find(s => s.type === "HEAL" && s.available && s.targets.includes(me.id));
      if (me.hp < me.max_hp && heal) {
        await command(ally, "skill", {skill_name: heal.name, target: me.id});
        break;
      }
    }
    const unit = adventure.battle.players[me.id];
    if (unit.route.length) { await pause(50); continue; }
    const enemy = adventure.mobs.find(m => dom.window.testFns.battleAllowed(adventure, me.id, m.combat_id, me.attack_range));
    if (enemy) {
      const skill = me.skills.find(s => s.available && ["DAMAGE", "DEBUFF"].includes(s.type) && s.targets.includes(enemy.combat_id));
      await command(dom, skill ? "skill" : "strike", skill ? {skill_name: skill.name, target: enemy.combat_id} : {target: enemy.combat_id});
    } else if (adventure.mobs.length) {
      const target = adventure.mobs[0].position;
      const path = dom.window.testFns.gridPath(adventure.battle.map, unit.position, target);
      if (path?.length) await command(dom, "battle_move", {x: target[0], y: target[1], path});
      else await pause(50);
    } else if (adventure.battle.hostiles_alive) {
      const target = [9, 4];
      const path = dom.window.testFns.gridPath(adventure.battle.map, unit.position, target);
      if (path?.length) await command(dom, "battle_move", {x: target[0], y: target[1], path});
      else await pause(50);
    } else {
      await waitFor(() => el(dom, "mob-cards").children.length === 0 && el(dom, "combat-status").textContent.includes("La zone est calme"), "interface après mort du dernier mob");
      assert.equal(el(dom, "enemy-intents").querySelectorAll("tr").length, 0);
      assert.equal(el(dom, "combat-target").options.length, 0);
      assert.equal(el(dom, "mob-hp").textContent, "");
      assert(el(dom, "world-map").querySelector(".battle-map"));
      assert(!el(dom, "tactical-actions").textContent.includes("Quitter le champ de bataille"));
      assert(el(dom, "world-map").querySelector(".battle-exit"));
      const corpse = adventure.battle.corpses.find(c => !c.harvested.length);
      if (!corpse) {
        const exit = adventure.battle.exit;
        await waitFor(() => dom.window.demoReady(), "sortie disponible pour le pilote");
        if (!adventure.field_map) {
          await waitFor(() => {
            const snapshot = dom.window.demoSnapshot()?.tutorial;
            return snapshot?.battle && snapshot.encounter_number === adventure.encounter_number && !snapshot.battle.hostiles_alive && snapshot.battle.corpses.every(corpse => corpse.harvested.length);
          }, "dépeçage reçu par le client avant reprise du trajet");
          assert.equal(resumeJourneyStep(dom), true);
        }
        else el(dom, "world-map").querySelector(`[data-cell="${exit.join(",")}"]`).dispatchEvent(new dom.window.Event("dblclick", {bubbles:true}));
        try {
          await waitFor(async () => {
            const next = (await request(dom, "/api/state")).session.tutorial;
            return !next.battle || next.encounter_number !== adventure.encounter_number;
          }, "sortie effective après dépeçage");
        } catch (error) {
          throw new Error(`${error.message} · ${el(dom, "message").textContent} · ${JSON.stringify(dom.window.testFns.flags())}`);
        }
        continue;
      }
      if (Math.hypot(unit.position[0] - corpse.position[0], unit.position[1] - corpse.position[1]) <= 1.5) await command(dom, "harvest", {target: corpse.id});
      else {
        const path = dom.window.testFns.gridPath(adventure.battle.map, unit.position, corpse.position);
        const position = unit.position.join(",");
        assert(el(dom, "world-map").querySelector(".battle-exit"));
        el(dom, "world-map").querySelector(`[data-cell="${corpse.position.join(",")}"]`).dispatchEvent(new dom.window.Event("dblclick", {bubbles: true}));
        await waitFor(async () => {
          const moved = (await request(dom, "/api/state")).session.tutorial.battle.players[me.id];
          return moved.route.length > 0 || moved.position.join(",") !== position;
        }, "clic de déplacement vers un corps après victoire");
      }
    }
    await pause(30);
  }
  throw new Error("Combat bloqué");
}
async function move(dom, destination) {
  await command(dom, "move", {destination});
  await finishCombat(dom);
}
async function main() {
  const html = await (await fetch(origin)).text();
  const app = await (await fetch(new URL("/map_artwork.js", origin))).text() + "\n" + (await Promise.all(require("./client_source.cjs").files.map(async file => await (await fetch(new URL("/" + file, origin))).text()))).join("\n");
  try {
    const group = await client(html, app, "Groupe", "Knight");
    await command(group, "tutorial");
    await command(group, "explore");
    await waitFor(() => el(group, "battle").classList.contains("combat-mode"), "combat actif avec vision étendue");
    assert(el(group, "mob-cards").children.length <= 5);
    assert(el(group, "enemy-intents").querySelectorAll("tr").length <= 5);
    assert([...el(group, "combat-target").options].every(option => !option.value || option.value.startsWith("mob")));
    assert(!el(group, "tactical-actions").textContent.includes("Quitter le champ de bataille"));
    el(group, "world-map").querySelector('[data-cell="1,5"]').dispatchEvent(new group.window.Event("dblclick", {bubbles: true}));
    await waitFor(async () => (await request(group, "/api/state")).session.tutorial.battle.players[(await request(group, "/api/state")).session.me].position[1] === 5, "clic sur case de combat");
    await assert.rejects(command(group, "move", {destination: "clearing_fight"}), error => error.code === "in_combat");
    await closeClient(group);
    clients.splice(clients.indexOf(group), 1);
    const necromancer = await client(html, app, "Invocateur", "Necromancien");
    await command(necromancer, "tutorial");
    await command(necromancer, "explore");
    await waitFor(() => el(necromancer, "self-skills").querySelector("button:not(:disabled)"), "invocation accessible sans sélectionner le personnage");
    assert.equal(el(necromancer, "combat-auto-target").getAttribute("aria-pressed"), "true");
    el(necromancer, "self-skills").querySelector("button").click();
    await waitFor(async () => {
      const adventure = (await request(necromancer, "/api/state")).session.tutorial;
      return Object.keys(adventure.battle?.summons || {}).length > 0;
    }, "squelette créé par le bouton personnel");
    await waitFor(() => el(necromancer, "world-map").querySelector(".summon-unit"), "squelette affiché après invocation personnelle");
    await waitFor(async () => {
      const state = (await request(necromancer, "/api/state")).session;
      const me = state.tutorial.players.find(p => p.id === state.me);
      return me.energies.some(e => e.type === "Mana" && e.current >= 8) && el(necromancer, "unit-control-list").querySelector("input:not(:disabled)");
    }, "énergie disponible pour le contrôle du squelette");
    el(necromancer, "unit-control-list").querySelector("input").click();
    await waitFor(async () => Object.values((await request(necromancer, "/api/state")).session.tutorial.battle.summons).some(u => u.controlled), "contrôle effectif du squelette");
    const controlledState = (await request(necromancer, "/api/state")).session;
    const controlledId = Object.keys(controlledState.tutorial.battle.summons)[0];
    const originalPosition = controlledState.tutorial.battle.players[controlledState.me].position.join(",");
    el(necromancer, "world-map").querySelector('[data-cell="1,4"]').dispatchEvent(new necromancer.window.MouseEvent("dblclick", {bubbles: true}));
    await waitFor(async () => {
      const state = (await request(necromancer, "/api/state")).session.tutorial;
      return state.battle.summons[controlledId].route.length > 0 || state.battle.summons[controlledId].position.join(",") === "1,4";
    }, "ordre de déplacement du squelette par la carte");
    assert.equal((await request(necromancer, "/api/state")).session.tutorial.battle.players[controlledState.me].position.join(","), originalPosition);
    await command(necromancer, "control_units", {units: []});
    assert(!Object.values((await request(necromancer, "/api/state")).session.tutorial.battle.summons).some(u => u.controlled));
    await closeClient(necromancer);
    clients.splice(clients.indexOf(necromancer), 1);
    const first = await client(html, app, "Alice <script>", "Mage");
    const second = await client(html, app, "Bob", "Priest");
    assert.notEqual(first.window.sessionStorage.getItem("rpg-token"), second.window.sessionStorage.getItem("rpg-token"));
    assert.equal(el(first, "player-name").querySelector("script"), null);
    first.window.crypto.randomUUID = undefined;
    el(first, "create").click();
    await waitFor(() => !el(first, "invitation").hidden && el(first, "invite-link").value.includes("#invite="), "lien d’invitation visible en HTTP sans randomUUID");
    assert(el(first, "party-tutorial").disabled);
    const invitation = el(first, "invite-link").value;
    await pause(300);
    assert(!el(first, "invitation").hidden);
    el(second, "invite-input").value = invitation;
    el(second, "join-form").dispatchEvent(new second.window.Event("submit", {bubbles: true, cancelable: true}));
    await waitFor(() => !el(first, "party-tutorial").disabled, "compagnon rejoint par lien");
    await command(first, "tutorial");
    await waitFor(() => !el(first, "tutorial-panel").hidden && !el(second, "tutorial-panel").hidden, "tutoriel partagé");
    assert.equal(first.window.document.querySelector(".adventure-grid").children.length, 3);
    el(first, "chat-channel").value = "group";
    el(first, "chat-message").value = "Bonjour <script>";
    el(first, "chat-form").dispatchEvent(new first.window.Event("submit", {bubbles:true,cancelable:true}));
    await waitFor(() => el(second, "chat-group").textContent.includes("Bonjour <script>"), "chat partagé du groupe");
    assert.equal(el(second, "chat-group").querySelector("script"), null);
    await waitFor(() => !el(first, "send-chat").disabled, "envoi du groupe terminé");
    el(first, "chat-channel").value = "global";
    el(first, "chat-message").value = "Message avant connexion";
    el(first, "chat-form").dispatchEvent(new first.window.Event("submit", {bubbles:true,cancelable:true}));
    await waitFor(() => el(second, "chat-global").textContent.includes("Message avant connexion"), "diffusion en direct du général");
    const late = await client(html, app, "Late", "Knight");
    await pause(300);
    assert(!el(late, "chat-global").textContent.includes("Message avant connexion"));
    await waitFor(() => !el(first, "send-chat").disabled, "premier envoi général terminé");
    el(first, "chat-message").value = "Message après connexion";
    el(first, "chat-form").dispatchEvent(new first.window.Event("submit", {bubbles:true,cancelable:true}));
    await waitFor(() => el(late, "chat-global").textContent.includes("Message après connexion"), "nouveau connecté reçoit les messages suivants");
    assert(!el(late, "chat-global").textContent.includes("Message avant connexion"));
    await closeClient(late);
    clients.splice(clients.indexOf(late), 1);
    el(first, "show-achievements").click();
    assert(!el(first, "achievements-view").hidden);
    assert(el(first, "achievement-rows").children.length >= 10);
    el(first, "show-map").click();
    assert(el(first, "quest-view").closest(".quest-box"));
    assert(el(first, "combat-view").closest(".zone-actions"));
    assert(el(first, "map-view").closest(".map-strip"));
    assert(el(first, "quest-view").hidden);
    assert(el(first, "map-details").open && !el(first, "region-view").hidden);
    const selected = el(first, "map-place").value;
    el(first, "quest-actions").querySelector("button").click();
    assert.equal(el(first, "map-place").value, selected);
    assert(el(first, "map-details").open && !el(first, "region-view").hidden);
    assert(el(first, "world-map").querySelector(".objective-ring"));
    assert(!el(first, "standby-view").hidden);
    assert(el(first, "world-map").textContent.includes("Vous êtes ici"));
    assert.equal(el(first, "combat-target").options.length, 0);
    el(first, "show-stats").click();
    assert(!el(first, "stats-view").hidden && !el(first, "standby-view").hidden && el(first, "quest-view").hidden);
    el(first, "show-map").click();
    const explore = [...el(first, "tutorial-actions").querySelectorAll("button")].find(b => b.textContent === "Explorer ce lieu");
    explore.click();
    await waitFor(() => !el(first, "combat-view").hidden && !el(second, "combat-view").hidden, "combat");
    assert(!el(first, "map-view").hidden && el(first, "quest-view").hidden);
    assert(el(first, "battle").classList.contains("combat-mode"));
    assert(!el(first, "character-menu").hidden);
    assert(el(first, "zone-name").textContent.length > 0);
    assert(/^Niv\. \d+$/.test(el(first, "zone-level").textContent));
    assert(el(first, "world-map").querySelector(".battle-map"));
    assert(!el(first, "combat-layout").hidden);
    assert(el(first, "combat-view").closest("#combat-action-panel"));
    assert(el(first, "skill-main-attack").querySelector(".skill-attack"));
    assert(el(first, "skill-hud").querySelectorAll(".skill-icon").length >= 2);
    assert(el(first, "map-view").closest("#combat-map-panel"));
    assert(el(first, "mob-cards").closest("#combat-enemy-panel"));
    assert(el(first, "enemy-intents").closest("#combat-enemy-panel"));
    assert.deepEqual([...el(first, "combat-layout").children].map(panel => panel.id), ["combat-player-panel", "combat-map-panel", "combat-enemy-panel", "combat-action-panel"]);
    await finishCombat(first);
    await waitFor(() => [...el(first, "tutorial-actions").querySelectorAll("button")].some(b => b.textContent.includes("Rejoindre") && !b.disabled), "trajet visible après premier combat");
    el(first, "map-place").value = "rosee";
    el(first, "map-place").dispatchEvent(new first.window.Event("change", {bubbles: true}));
    const roseeButtons = [...first.window.document.querySelectorAll("button")].filter(button => /^(Rejoindre|Prendre le chemin vers).*Rosée/.test(button.textContent));
    assert.equal(roseeButtons.length, 1);
    const villageNode = el(first, "world-map").querySelector('[data-destination="rosee"]');
    villageNode.dispatchEvent(new first.window.MouseEvent("click", {bubbles: true}));
    assert(villageNode.isConnected);
    villageNode.dispatchEvent(new first.window.MouseEvent("click", {bubbles: true}));
    assert(villageNode.isConnected);
    villageNode.dispatchEvent(new first.window.MouseEvent("dblclick", {bubbles: true}));
    assert.equal(el(first, "travel-confirmation"), null);
    await waitFor(async () => (await request(first, "/api/state")).session.tutorial.position !== "clearing", "départ vers Rosée");
    await finishCombat(first);
    await waitFor(() => el(first, "position-label").textContent.includes("Village de Rosée") && el(first, "combat-view").hidden, "arrivée Rosée");
    await assert.rejects(command(first, "talk", {npc: "mira"}), error => error.code === "wrong_location");
    el(first, "show-map").click();
    el(first, "map-place").value = "rosee";
    el(first, "map-place").dispatchEvent(new first.window.Event("change", {bubbles: true}));
    await waitFor(() => el(first, "world-map").querySelector('[data-point="mira"][aria-disabled="false"]'), "icône Mira");
    const miraNode = el(first, "world-map").querySelector('[data-point="mira"]');
    miraNode.dispatchEvent(new first.window.MouseEvent("click", {bubbles: true}));
    assert(miraNode.isConnected);
    assert.equal((await request(first, "/api/state")).session.tutorial.position, "rosee");
    miraNode.dispatchEvent(new first.window.MouseEvent("dblclick", {bubbles: true}));
    await waitFor(() => !el(first, "npc-view").hidden && !el(second, "npc-view").hidden, "déplacement point Mira");
    await command(first, "talk", {npc: "mira"});
    await waitFor(() => el(first, "world-map").querySelector('[data-point="forge"][aria-disabled="false"]'), "icône Forge");
    el(first, "world-map").querySelector('[data-point="forge"]').dispatchEvent(new first.window.Event("dblclick", {bubbles: true}));
    await waitFor(() => !el(first, "craft-view").hidden, "forge verrouillée");
    assert(el(first, "forge-status").textContent.includes("Forge verrouillée"));
    assert([...el(first, "forge-catalogue").querySelectorAll("button")].every(b => b.disabled));
    await move(first, "hunt");
    while ((await request(first, "/api/state")).session.tutorial.kills < 3) {
      await command(first, "explore");
      await finishCombat(first);
    }
    await move(first, "mira");
    await command(first, "talk", {npc: "mira"});
    await move(first, "forge");
    await waitFor(() => !el(first, "craft-view").hidden && !el(second, "craft-view").hidden, "forge partagée");
    assert.equal(el(first, "forge-catalogue").children.length, 6);
    assert(el(first, "forge-catalogue").textContent.includes("+2 intelligence"));
    assert(el(first, "forge-catalogue").textContent.includes("+2 force"));
    assert(el(first, "forge-catalogue").textContent.includes("+2 sagesse"));
    await command(first, "craft", {recipe: "veste"});
    await waitFor(() => el(first, "quest-description").textContent.includes("Veste fabriquée et équipée") && el(first, "quest-description").textContent.includes("compagnon"), "fabrication personnelle validée dans la quête");
    await command(second, "craft", {recipe: "veste"});
    await waitFor(() => el(first, "quest-description").textContent.includes("Prochaine étape") && el(first, "craft-actions").textContent.includes("Brume"), "objectif Brume après fabrication du groupe");
    await move(first, "brume");
    await waitFor(() => el(first, "battle-title").textContent === "Aventure accomplie" && el(second, "battle-title").textContent === "Aventure accomplie", "fin coopérative");
    assert(el(first, "combat-layout").hidden);
    assert(el(first, "map-view").closest(".map-strip"));
    assert(el(first, "combat-view").closest(".zone-actions"));
    el(first, "show-inventory").click();
    assert(!el(first, "inventory-view").hidden && el(first, "quest-view").hidden);
    el(first, "show-bestiary").click();
    assert(el(first, "bestiary-details").textContent.includes("rang D"));
    el(first, "show-map").click();
    assert(el(first, "world-map").textContent.includes("Vous êtes ici"));
    assert.deepEqual(errors, []);
    console.log("UI HTTP vérifiée : deux joueurs, combat tactique, cases cliquables, PV et intentions, repère de quête, dépeçage, six recettes et tutoriel jusqu’à Brume.");
  } finally { for (const dom of clients) await closeClient(dom); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });

