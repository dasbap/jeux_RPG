"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("rpg-token") || "";
let session = null;
let sessionId = sessionStorage.getItem("rpg-session") || "";
let busy = false;
let polling = false;
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
  $("clock").textContent = `Temps de jeu écoulé : ${Math.floor(state.game_time)} s`;
  $("connection").textContent = "Connecté · état partagé";
  $("room-controls").hidden = Boolean(session && session.state !== "finished");
  $("battle").hidden = !session;
  $("invitation").hidden = !(session && session.state === "lobby" && session.owner === session.me && sessionStorage.getItem("rpg-invite-session") === session.id);
  if (!session) return;
  $("battle-title").textContent = {lobby: "En attente du second joueur", running: "Duel en cours", finished: "Duel terminé"}[session.state];
  $("version").textContent = `État ${session.revision}`;
  $("fighters").replaceChildren();
  for (const player of session.players) {
    const article = document.createElement("article");
    article.className = `fighter${player.id === session.me ? " mine" : ""}`;
    const title = document.createElement("h3");
    title.textContent = `${player.name}${player.id === session.me ? " · vous" : ""}`;
    const type = document.createElement("div");
    type.className = "class";
    type.textContent = classes[player.class_name];
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
  $("attack").hidden = session.state !== "running";
  $("attack").disabled = busy || me.cooldown_real_seconds > 0;
  $("attack").textContent = me.cooldown_real_seconds > 0 ? `Attaque dans ${me.cooldown_real_seconds.toFixed(1)} s` : "Attaquer";
  $("leave").hidden = session.state === "finished";
  $("leave").disabled = busy;
  $("new-room").hidden = session.state !== "finished";
  const winner = session.players.find(player => player.id === session.winner);
  $("result").textContent = session.state === "finished" ? (winner ? `${winner.name} remporte le duel.` : "Session terminée sans vainqueur.") : `Temps restant : ${Math.ceil(session.remaining_real_seconds)} secondes réelles`;
  $("events").replaceChildren();
  for (const event of session.events) {
    const li = document.createElement("li");
    li.textContent = `${Math.floor(event.game_time)} s · ${event.message}`;
    $("events").append(li);
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
    message("Personnage créé. Vous pouvez inviter un adversaire.");
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
$("create").addEventListener("click", () => command("create"));
$("join-form").addEventListener("submit", event => {
  event.preventDefault();
  command("join", {invite: $("invite-input").value.trim()});
});
for (const action of ["start", "attack", "leave"]) $(action).addEventListener("click", () => {
  if (session) command(action, {session_id: session.id, revision: session.revision});
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
