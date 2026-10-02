"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("rpg-token") || "";
let session = null;
let sessionId = sessionStorage.getItem("rpg-session") || "";
let busy = false;
let polling = false;
let currentView = "standby";
let viewContext = "";
let combatTarget = "";
const classes = {Knight: "Chevalier", Mage: "Mage", Archer: "Archer", Priest: "Prêtre", Necromancien: "Nécromancien"};
function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}
async function api(path, body, authenticated = true) {
  const headers = {};
  if (authenticated && token) headers.Authorization = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {method: body ? "POST" : "GET", headers, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(5000)});
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.message || "Requête refusée.");
    error.code = data.error;
    throw error;
  }
  return data;
}
function remember() {
  sessionStorage.setItem("rpg-token", token);
  sessionStorage.setItem("rpg-session", sessionId);
}
function render(state) {
  $("registration").hidden = Boolean(token);
  $("lobby").hidden = !token;
  $("player-name").textContent = `${state.player.name} · ${classes[state.player.class_name]}`;
  $("connection").textContent = "Connecté · état partagé";
  $("room-controls").hidden = Boolean(session && session.state !== "finished");
  $("battle").hidden = !session;
  $("invitation").hidden = !(session && session.state === "lobby" && session.owner === session.me && sessionStorage.getItem("rpg-invite-session") === session.id);
  $("tutorial-panel").hidden = !(session && session.tutorial);
  $("duel-target-controls").hidden = true;
  if (!session) return;
  $("battle-title").textContent = {lobby: "En attente du second joueur", running: "Duel en cours", finished: "Duel terminé"}[session.state];
  $("version").textContent = `État ${session.revision}`;
  $("fighters").replaceChildren();
  $("fighters").hidden = Boolean(session.tutorial);
  for (const player of session.tutorial ? session.tutorial.players : session.players) {
    const article = document.createElement("article");
    article.className = `fighter${player.id === session.me ? " mine" : ""}`;
    const title = document.createElement("h3");
    title.textContent = `${player.name}${player.id === session.me ? " · vous" : ""}`;
    const type = document.createElement("div");
    type.className = "class";
    type.textContent = `${classes[player.class_name]}${player.level ? ` · niveau ${player.level}` : ""}`;
    const bar = document.createElement("div");
    bar.className = "health";
    bar.setAttribute("role", "meter");
    bar.setAttribute("aria-label", `Points de vie de ${player.name}`);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", String(player.max_hp));
    bar.setAttribute("aria-valuenow", String(player.hp));
    const fill = document.createElement("div");
    fill.className = "health-fill";
    fill.style.width = `${100 * player.hp / player.max_hp}%`;
    bar.append(fill);
    const hp = document.createElement("div");
    hp.textContent = `${player.hp} / ${player.max_hp} PV`;
    article.append(title, type, bar, hp);
    $("fighters").append(article);
  }
  const me = session.players.find(player => player.id === session.me);
  $("start").hidden = session.state !== "lobby" || session.owner !== session.me;
  $("start").disabled = busy || session.players.length !== 2;
  $("party-tutorial").hidden = session.state !== "lobby" || session.owner !== session.me;
  $("party-tutorial").disabled = busy;
  $("attack").hidden = session.state !== "running";
  $("attack").disabled = busy || me.cooldown_real_seconds > 0;
  $("duel-target").replaceChildren();
  if (!session.tutorial && session.state === "running" && me.hp > 0 && me.cooldown_real_seconds <= 0) {
    for (const opponent of session.players.filter(p => p.id !== session.me && p.hp > 0)) {
      const option = document.createElement("option");
      option.value = opponent.id;
      option.textContent = opponent.name;
      $("duel-target").append(option);
    }
    $("duel-target-controls").hidden = $("duel-target").options.length === 0;
  }
  $("attack").textContent = me.cooldown_real_seconds > 0 ? `Attaque dans ${me.cooldown_real_seconds.toFixed(1)} s` : "Attaquer";
  $("leave").hidden = session.state === "finished";
  $("leave").disabled = busy;
  $("new-room").hidden = session.state !== "finished";
  const winner = session.players.find(player => player.id === session.winner);
  $("result").textContent = session.state === "finished" ? (winner ? `${winner.name} remporte le duel.` : "Session terminée.") : "";
  if (session.tutorial) renderTutorial(session.tutorial);
  $("events").replaceChildren();
  for (const event of session.events) {
    const li = document.createElement("li");
    li.textContent = event.message;
    $("events").append(li);
  }
}
function tutorialCommand(action, params = {}) {
  if (session) return command(action, {session_id: session.id, revision: session.revision, ...params});
}
function showView(view) {
  currentView = view;
  if (session && session.tutorial) renderTutorial(session.tutorial);
}
function skillAllowed(me, skill, target, mob) {
  if (!mob || me.hp <= 0 || me.stunned || me.cooldown_real_seconds > 0 || !skill.available || skill.cooldown > 0) return false;
  const energy = me.energies.find(e => e.type === skill.energy);
  if (!energy || energy.current < skill.cost || !skill.targets.includes(target.id)) return false;
  if (["DAMAGE", "DEBUFF"].includes(skill.type)) return target.id === "mob" && target.hp > 0;
  if (skill.type === "INVOCATION") return target.id === me.id && me.invocations.length < me.invocation_limit;
  if (target.id === "mob" || target.id !== me.id && !skill.can_target_others) return false;
  if (skill.type === "RESURRECT") return target.hp <= 0;
  if (target.hp <= 0) return false;
  if (skill.type === "HEAL") return target.hp < target.max_hp;
  return skill.type === "BUFF";
}
function renderTutorial(adventure) {
  const fighting = Boolean(adventure.mob);
  const context = `${session.id}:${adventure.step}:${fighting}`;
  if (context !== viewContext) {
    currentView = fighting ? "combat" : "standby";
    combatTarget = "";
    viewContext = context;
  }
  const me = adventure.players.find(player => player.id === session.me);
  const canTalk = !fighting && (adventure.step === "village" || adventure.step === "hunt" && adventure.kills === 3);
  const canCraft = !fighting && adventure.step === "craft" && !me.equipment;
  const hasQuest = adventure.quest !== "unaccepted";
  if (currentView === "npc" && !canTalk || currentView === "craft" && !canCraft || currentView === "quest" && (!hasQuest || fighting)) currentView = fighting ? "combat" : "standby";
  for (const view of ["standby", "npc", "quest", "stats", "craft", "combat"]) $(`${view}-view`).hidden = currentView !== view;
  $("fighters").hidden = currentView !== "combat";
  $("show-quest").hidden = fighting || !hasQuest || currentView === "quest";
  $("show-stats").hidden = currentView === "stats";
  $("back-view").hidden = currentView === (fighting ? "combat" : "standby");
  $("back-view").textContent = fighting ? "Retour au combat" : "Retour à l'exploration";
  $("battle-title").textContent = adventure.step === "complete" ? "Aventure accomplie" : "Votre tutoriel";
  $("attack").hidden = true;
  $("leave").hidden = true;
  $("result").textContent = adventure.step === "complete" ? "Vous êtes arrivé au village de Brume." : "";
  $("location").textContent = adventure.location;
  $("objective").textContent = adventure.objective;
  $("quest-progress").textContent = `Quête de Mira : ${{unaccepted: "à accepter", active: `${adventure.kills}/3 gobelins vaincus`, completed: "accomplie"}[adventure.quest]}`;
  $("quest-description").textContent = adventure.quest === "completed" ? "Mira vous a remis votre récompense. Utilisez les matériaux de votre sac pour fabriquer et équiper votre veste à la forge." : "Battez trois gobelins de la lisière, puis revenez parler à Mira à Rosée. Gardez les matériaux pour fabriquer votre veste.";
  $("character-details").replaceChildren();
  for (const text of [
    `Expérience : ${me.exp}/${me.next_level_exp} · niveau ${me.level}`,
    `PV : ${me.hp}/${me.max_hp} · Force ${me.stats.force} · Endurance ${me.stats.endurance} · Intelligence ${me.stats.intelligence} · Sagesse ${me.stats.sagesse}`,
    `Énergie : ${me.energies.map(e => `${e.type} ${e.current}/${e.max}`).join(" · ")}`,
    `Sac : ${Object.entries(me.inventory).map(([item, amount]) => `${amount} ${item}`).join(", ") || "vide"}`,
    `Équipement : ${me.equipment || "aucun"}`,
    `Invocations : ${me.invocations.map(i => `${i.name} (${i.hp} PV)`).join(", ") || "aucune"}`,
    `Compétences acquises : ${me.skills.map(s => `${s.name} (${s.cost} ${s.energy})`).join(", ")}`,
    `Prochaines compétences : ${me.upcoming_skills.map(s => `${s.name} au niveau ${s.level}`).join(", ") || "toutes acquises"}`,
  ]) {
    const p = document.createElement("p");
    p.textContent = text;
    $("character-details").append(p);
  }
  for (const id of ["tutorial-actions", "npc-actions", "quest-actions", "craft-actions", "combat-actions", "skills"]) $(id).replaceChildren();
  function button(container, label, handler, disabled = false) {
    const element = document.createElement("button");
    element.textContent = label;
    element.disabled = busy || disabled;
    element.addEventListener("click", handler);
    $(container).append(element);
    return element;
  }
  function action(container, label, name, params = {}, disabled = false) {
    return button(container, label, () => tutorialCommand(name, params), disabled);
  }
  if (!fighting && adventure.step !== "complete") {
    action("tutorial-actions", "Se reposer", "rest");
    if (adventure.step === "clearing" || adventure.step === "hunt" && adventure.kills < 3) action("tutorial-actions", "Explorer : chercher un gobelin", "explore");
    if (adventure.step === "road") action("tutorial-actions", "Rejoindre Rosée", "travel", {destination: "rosee"});
    if (canTalk) button("tutorial-actions", adventure.step === "village" ? "Parler à Mira" : "Revenir à Rosée : parler à Mira", () => showView("npc"));
    if (canCraft) button("tutorial-actions", "Entrer dans la forge", () => showView("craft"));
    if (adventure.step === "craft" && me.equipment) {
      const p = document.createElement("p");
      p.textContent = "Votre veste est équipée. Votre compagnon doit fabriquer la sienne avant le départ.";
      $("tutorial-actions").append(p);
    }
    if (["craft", "travel"].includes(adventure.step)) action("tutorial-actions", "Essayer mes nouvelles compétences · entraînement sans butin", "explore");
    if (adventure.step === "travel") action("tutorial-actions", "Rejoindre Brume", "travel", {destination: "brume"});
  }
  $("npc-dialogue").textContent = adventure.step === "village" ? "Mira : des gobelins menacent notre lisière. Pourriez-vous en battre trois ? Gardez leurs peaux et leurs crocs pour la forge." : "Mira : vous avez vaincu les trois gobelins ! Votre récompense vous attend. Ensuite, faites fabriquer votre veste à la forge.";
  if (canTalk) action("npc-actions", adventure.step === "village" ? "Accepter la quête" : "Rendre la quête", "talk", {npc: "mira"});
  if (canTalk && hasQuest) button("quest-actions", "Parler à Mira", () => showView("npc"));
  $("craft-materials").textContent = `Votre sac : ${me.inventory.peau || 0} peau(s), ${me.inventory.croc || 0} croc(s).`;
  if (canCraft) action("craft-actions", "Fabriquer et équiper la veste", "craft", {recipe: "veste"}, (me.inventory.peau || 0) < 2 || (me.inventory.croc || 0) < 3);
  $("mob-name").textContent = fighting ? adventure.mob.name : "";
  $("mob-hp").textContent = fighting ? `${adventure.mob.stats.hp.current}/${adventure.mob.stats.hp.max} PV` : "";
  const mob = fighting ? {id: "mob", name: adventure.mob.name, hp: adventure.mob.stats.hp.current, max_hp: adventure.mob.stats.hp.max} : null;
  const canAttack = target => Boolean(mob && target.id === "mob" && mob.hp > 0 && me.hp > 0 && !me.stunned && me.cooldown_real_seconds <= 0 && me.can_attack);
  const possibleTargets = fighting ? [mob, ...adventure.players].filter(target => canAttack(target) || me.skills.some(skill => skillAllowed(me, skill, target, mob))) : [];
  $("combat-target").replaceChildren();
  for (const target of possibleTargets) {
    const option = document.createElement("option");
    option.value = target.id;
    option.textContent = `${target.name}${target.id === me.id ? " · vous" : ""}`;
    $("combat-target").append(option);
  }
  if (possibleTargets.length && !possibleTargets.some(target => target.id === combatTarget)) combatTarget = possibleTargets[0].id;
  $("combat-target").value = possibleTargets.length ? combatTarget : "";
  $("target-controls").hidden = !fighting || possibleTargets.length === 0;
  const selected = possibleTargets.find(target => target.id === combatTarget);
  $("combat-status").textContent = !fighting ? "" : me.hp <= 0 ? "Vous êtes à terre. Votre compagnon peut terminer le combat." : me.cooldown_real_seconds > 0 ? `Prochaine action dans ${me.cooldown_real_seconds.toFixed(1)} s.` : me.stunned ? "Vous êtes étourdi. Récupérez pour laisser passer le tour." : selected ? "Choisissez une action pour cette cible." : "Aucune cible disponible. Vous pouvez récupérer de l'énergie.";
  if (fighting && me.hp > 0) {
    if (selected && canAttack(selected)) action("combat-actions", "Attaque simple", "strike", {target: selected.id});
    action("combat-actions", "Récupérer de l'énergie", "rest", {}, me.cooldown_real_seconds > 0);
    if (selected) for (const skill of me.skills.filter(s => skillAllowed(me, s, selected, mob))) {
      const element = action("skills", `${skill.name} · ${skill.cost} ${skill.energy}`, "skill", {skill_name: skill.name, target: selected.id});
      element.className = "secondary";
      element.title = skill.description;
    }
  }
}
async function refresh() {
  if (!token) {
    $("connection").textContent = "Prêt · créez votre personnage";
    return;
  }
  if (polling || busy) return;
  polling = true;
  try {
    const state = await api("/api/state");
    if (state.session) {
      session = state.session;
      sessionId = session.id;
    } else if (sessionId) {
      session = await api(`/api/sessions/${sessionId}`);
    } else session = null;
    remember();
    render(state);
  } catch (error) {
    $("connection").textContent = "Connexion interrompue";
    if (error.code === "unauthorized") {
      token = "";
      sessionId = "";
      remember();
      $("registration").hidden = false;
      $("lobby").hidden = true;
      $("battle").hidden = true;
      message("Votre clé n'est plus valide. Reconnectez-vous.", true);
    } else if (error.code === "not_found") {
      sessionId = "";
      session = null;
      remember();
    }
  } finally { polling = false; }
}
async function command(action, params = {}) {
  if (busy) return;
  busy = true;
  if (session?.tutorial) renderTutorial(session.tutorial);
  message("");
  $("attack").disabled = true;
  try {
    const data = await api("/api/commands", {request_id: crypto.randomUUID(), action, params});
    session = data.session;
    sessionId = session.id;
    remember();
    if (data.invite) {
      sessionStorage.setItem("rpg-invite", data.invite);
      sessionStorage.setItem("rpg-invite-session", session.id);
      $("invite-code").textContent = data.invite;
      $("invitation").hidden = false;
    }
    if (session.state !== "lobby") $("invitation").hidden = true;
  } catch (error) {
    message(error.message, true);
  } finally { busy = false; await refresh(); }
}
$("register-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  try {
    const data = await api("/api/register", {name: $("name").value, class_name: $("class-name").value}, false);
    token = data.token;
    sessionId = "";
    remember();
    message("Personnage créé. Commencez le tutoriel ou invitez un compagnon.");
  } catch (error) { message(error.message, true); }
  finally { busy = false; await refresh(); }
});
$("restore-form").addEventListener("submit", async event => {
  event.preventDefault();
  token = $("restore-token").value.trim();
  sessionId = "";
  remember();
  $("restore-token").value = "";
  await refresh();
});
$("show-stats").addEventListener("click", () => showView("stats"));
$("show-quest").addEventListener("click", () => showView("quest"));
$("back-view").addEventListener("click", () => showView(session?.tutorial?.mob ? "combat" : "standby"));
$("combat-target").addEventListener("change", () => {
  combatTarget = $("combat-target").value;
  if (session?.tutorial) renderTutorial(session.tutorial);
});
$("create").addEventListener("click", () => command("create"));
$("tutorial").addEventListener("click", () => command("tutorial"));
$("party-tutorial").addEventListener("click", () => command("tutorial"));
$("join-form").addEventListener("submit", event => {
  event.preventDefault();
  command("join", {invite: $("invite-input").value.trim()});
});
for (const action of ["start", "attack", "leave"]) $(action).addEventListener("click", () => {
  if (session) command(action, {session_id: session.id, revision: session.revision, ...(action === "attack" ? {target: $("duel-target").value} : {})});
});
$("new-room").addEventListener("click", () => command("create"));
$("logout").addEventListener("click", () => {
  token = "";
  session = null;
  sessionId = "";
  for (const key of ["rpg-token", "rpg-session", "rpg-invite", "rpg-invite-session"]) sessionStorage.removeItem(key);
  location.reload();
});
async function copy(text, outputId) {
  try { await navigator.clipboard.writeText(text); message("Copié."); }
  catch { $(outputId).hidden = false; $(outputId).textContent = text; message("Sélectionnez le texte pour le copier."); }
}
$("copy-token").addEventListener("click", () => copy(token, "token-output"));
$("copy-invite").addEventListener("click", () => copy($("invite-code").textContent, "invite-code"));
const invite = sessionStorage.getItem("rpg-invite");
if (invite) { $("invite-code").textContent = invite; $("invitation").hidden = false; }
setInterval(refresh, 500);
refresh();
