"use strict";
let token = sessionStorage.getItem("rpg-token") || "";
let chatToken = token;
let chatConnection = requestId();
let session = null;
let accountState = null;
let socialState = null;
let presenceState = null;
let sessionId = sessionStorage.getItem("rpg-session") || "";
let busy = false;
let polling = false;
let nextRefreshAt = 0;
let refreshFailures = 0;
let lastPlayer = null;
let stateEpoch = 0;
let bundleToken = "";
let bundleHashes = {};
let bundleValues = {};
let bundleSequence = 0;
let appliedBundleSequence = 0;
let pendingBattleMove = null;
let fieldCamera = null;
let cameraDrag = null;
let cameraReturnTimer = null;
let cameraFrame = null;
let suppressMapClickUntil = 0;
const worldCameras = new Map();
let activeWorldMap = "general";
let currentView = "map";
let viewContext = "";
let combatTarget = "";
let combatFullscreenRequested = false;
let mapPlace = "";
let mapPoint = "";
let mapMarker = null;
let focusedMob = "";
let focusedEnemy = "";
let tacticalInteractionUntil = 0;
let inspectedCell = null;
const classes = Object.create(null);
async function api(path, body, authenticated = true) {
  const headers = {Accept: "application/json"};
  if (authenticated && token) headers.Authorization = `Bearer ${token}`;
  if (authenticated && (path === "/api/state" || path === "/api/chat")) {
    if (chatToken !== token) { chatToken = token; chatConnection = requestId(); }
    headers["X-RPG-Chat-Connection"] = chatConnection;
  }
  if (body) headers["Content-Type"] = "application/json";
  if (location.hostname.endsWith(".devtunnels.ms")) headers["X-Tunnel-Skip-AntiPhishing-Page"] = "true";
  const compactCommand = !globalThis.rpgRealtime && path === "/api/commands" && ["explore", "strike", "skill", "rest", "travel", "move", "craft", "upgrade", "battle_move", "stop_move", "hide", "harvest", "leave_battle", "control_units", "unit_order", "unit_skill"].includes(body?.action);
  if (compactCommand) headers["X-RPG-Command-Ack"] = "1";
  const bundled = path === "/api/state" || path === "/api/commands" && !compactCommand;
  if (bundled) {
    if (bundleToken !== token) { bundleToken = token; bundleHashes = {}; bundleValues = {}; }
    headers["X-RPG-Bundles"] = "1";
    headers["X-RPG-Bundle-Hashes"] = JSON.stringify(bundleHashes);
  }
  const requestToken = token;
  const bundleBase = {...bundleValues};
  const requestBundleSequence = ++bundleSequence;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const options = {method: body ? "POST" : "GET", headers, body: body ? JSON.stringify(body) : undefined, signal: controller.signal, cache: "no-store"};
    const response = globalThis.rpgRealtime ? await globalThis.rpgRealtime.request(path, options) : await fetch(path, options);
    let data;
    try { data = await response.json(); }
    catch { throw Object.assign(new Error("Le tunnel ne renvoie pas l’API du jeu. Vérifiez son accès et relancez la connexion."), {code: "tunnel_response"}); }
    if (!response.ok) {
      const error = new Error(data.message || "Requête refusée.");
      error.code = data.error;
      throw error;
    }
    if (bundled && data.bundle_protocol === 1 && requestToken === token) {
      for (const key of data.removed) delete bundleBase[key];
      Object.assign(bundleBase, data.bundles);
      if (requestBundleSequence > appliedBundleSequence) {
        bundleValues = bundleBase; bundleHashes = data.hashes; appliedBundleSequence = requestBundleSequence;
      }
      const assembled = {};
      for (const [path, value] of Object.entries(bundleBase).sort((a, b) => a[0].split("/").length - b[0].split("/").length)) {
        const parts = path.split("/");
        let target = assembled;
        for (const part of parts.slice(0, -1)) target = target[part] ||= {};
        target[parts.at(-1)] = JSON.parse(JSON.stringify(value));
      }
      return assembled;
    }
    return data;
  } catch (error) {
    if (controller.signal.aborted) throw Object.assign(new Error(body ? "Réponse trop lente. L’action a peut-être été reçue ; actualisation de l’état en cours." : "Le serveur ou le tunnel répond trop lentement. Reconnexion automatique en cours."), {code: "timeout"});
    if (error instanceof TypeError) throw Object.assign(new Error("Connexion au serveur indisponible. Vérifiez le tunnel et votre réseau."), {code: "network"});
    throw error;
  } finally { clearTimeout(timeout); }
}

function remember() {
  sessionStorage.setItem("rpg-token", token);
  sessionStorage.setItem("rpg-session", sessionId);
}


async function socialAction(action, params = {}) {
  if (busy) return;
  busy = true;
  $("social-status").textContent = "";
  try {
    socialState = await api("/api/social", {action, params});
    $("social-status").textContent = action === "rally" ? "Appel envoyé. Chaque allié choisit de vous rejoindre." : "Action effectuée.";
  } catch (error) { $("social-status").textContent = error.message; }
  finally { busy = false; renderSocial(); if (!globalThis.rpgRealtime || ["realm", "wait", "resume", "join_ally", "rally_accept"].includes(action)) await refresh(true); }
}
for (const id of ["choose-character", "choose-character-options"]) $(id).addEventListener("click", async () => {
  try { accountState = await api("/api/account/me"); renderCharacters(); } catch (error) { message(error.message, true); }
});
$("character-create").addEventListener("submit", event => {event.preventDefault(); selectCharacter({action: "create", name: $("new-character-name").value, class_name: $("new-character-class").value});});
$("character-cancel").addEventListener("click", () => {$("characters").hidden = true; sectionSignatures.clear(); refresh(true);});
$("social-search").addEventListener("submit", event => {event.preventDefault(); socialAction("friend_add", {username: $("social-name").value.trim()});});
$("social-invite").addEventListener("click", () => socialAction("team_invite", {username: $("social-name").value.trim()}));

async function refresh(force = false) {
  if (!$("characters").hidden) return;
  if (!token) {
    $("connection").textContent = "Prêt · connectez-vous à votre compte";
    return;
  }
  if (polling || (!force && Date.now() < nextRefreshAt)) return;
  polling = true;
  const epoch = stateEpoch;
  try {
    if (!accountState) {
      try { accountState = await api("/api/account/me"); }
      catch (error) { if (error.code !== "unauthorized") throw error; }
      if (accountState && !accountState.selected) { renderCharacters(); return; }
    }
    const state = await api("/api/state");
    if (epoch !== stateEpoch || (state.session && session && state.session.id === session.id && state.session.revision < session.revision)) return;
    if (state.session) {
      session = state.session;
      sessionId = session.id;
    } else if (sessionId) {
      const updated = await api(`/api/sessions/${sessionId}`);
      if (epoch !== stateEpoch || (updated.id === session?.id && updated.revision < session.revision)) return;
      session = updated;
    } else session = null;
    remember();
    refreshFailures = 0;
    nextRefreshAt = 0;
    render(state);
  } catch (error) {
    refreshFailures++;
    nextRefreshAt = Date.now() + Math.min(10000, 1000 * 2 ** Math.min(4, refreshFailures - 1));
    $("connection").textContent = "Reconnexion automatique · " + (error.code === "timeout" ? "tunnel lent" : "serveur indisponible");
    if (error.code === "unauthorized") {
      token = "";
      sessionId = "";
      remember();
      $("registration").hidden = false;
      $("lobby").hidden = true;
      $("battle").hidden = true;
      message("Votre session a expiré. Connectez-vous avec votre compte.", true);
    } else if (error.code === "character_required") {
      accountState = await api("/api/account/me");
      renderCharacters();
    } else if (error.code === "not_found") {
      sessionId = "";
      session = null;
      remember();
    }
  } finally { polling = false; }
}
async function command(action, params = {}) {
  if (busy) return;
  stateEpoch++;
  busy = true;
  if (session?.tutorial) renderTutorial(session.tutorial);
  message("");
  $("attack").disabled = true;
  try {
    let data;
    let currentParams = params;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        data = await api("/api/commands", {request_id: requestId(), action, params: currentParams});
        break;
      } catch (error) {
        if (error.code !== "stale_revision" || !currentParams.session_id || attempt === 4) throw error;
        const state = await api("/api/state");
        if (!state.session || state.session.id !== currentParams.session_id) throw error;
        if (!session || session.id !== state.session.id || state.session.revision >= session.revision) session = state.session;
        currentParams = {...currentParams, revision: session.revision, ...(["move", "travel", "explore", "talk"].includes(action) && session.tutorial?.world_context ? {world_context: session.tutorial.world_context} : {})};
        if (["move", "travel"].includes(action)) { const paths = worldPaths(session.tutorial, currentParams.destination); if (paths) currentParams.paths = paths; }
        if (action === "battle_move" && session.tutorial?.battle) {
          const battle = session.tutorial.battle;
          currentParams.path = gridPath(battle.map, battle.players[session.me].position, [currentParams.x, currentParams.y]);
        }
        if (action === "unit_order" && currentParams.order === "move" && session.tutorial?.battle) {
          const battle = session.tutorial.battle;
          currentParams.paths = Object.fromEntries(currentParams.units.map(id => [id, gridPath(battle.map, battle.summons[id].position, currentParams.target)]));
        }
      }
    }
    if (data.session.acknowledged) {
      if (session?.id === data.session.id && data.session.revision >= session.revision) session = {...session, revision: data.session.revision, state: data.session.state};
    } else if (!session || session.id !== data.session.id || data.session.revision >= session.revision) session = data.session;
    if (!session) return;
    if (action === "talk") message(data.session.events?.at(-1)?.message || "Dialogue mis à jour dans le journal de quête.");
    sessionId = session.id;
    remember();
    if (data.invite) {
      sessionStorage.setItem("rpg-invite", data.invite);
      sessionStorage.setItem("rpg-invite-session", session.id);
      $("invite-code").textContent = data.invite;
      $("invite-link").value = invitationLink(data.invite);
      $("invite-status").textContent = "Invitation créée · valable 30 minutes. Partagez le lien ou le code avec votre compagnon.";
      message("Invitation créée. Le lien et le code sont affichés ci-dessus.");
      $("party-tutorial").disabled = session.players.length < 2;
      $("invitation").hidden = false;
    }
    if (action === "join") message("Vous avez rejoint votre compagnon. Le créateur peut démarrer le tutoriel.");
    if (session.state !== "lobby") $("invitation").hidden = true;
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
    if (lastPlayer && $("characters").hidden) render({player: lastPlayer});
    else if (session?.tutorial) renderTutorial(session.tutorial);
    const pending = pendingBattleMove;
    pendingBattleMove = null;
    if (pending && session?.id === pending.sessionId && session.tutorial?.battle && session.tutorial.encounter_number === pending.encounter) {
      const actor = session.tutorial.players.find(player => player.id === session.me);
      if (actor.hp > 0 && !actor.stunned && !actor.casting && (!pending.controlledIds || JSON.stringify(pending.controlledIds) === JSON.stringify(controlledUnits(session.tutorial, session.me).map(([id]) => id).sort()))) await moveControlled(session.tutorial, actor, pending.destination);
    }
    if (!globalThis.rpgRealtime) await refresh(true);
  }
}
$("register-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  try {
    const data = await api("/api/account/signup", {username: $("account-name").value, password: $("account-password").value}, false);
    token = data.token;
    accountState = data;
    remember();
    accountState = await api("/api/account/character", {action: "create", name: $("name").value, class_name: $("class-name").value});
    sessionId = "";
    $("account-password").value = "";
    message("Compte créé. Commencez le tutoriel et retrouvez vos alliés dans Social.");
  } catch (error) { message(error.message, true); if (token && accountState) renderCharacters(); }
  finally { busy = false; await refresh(true); }
});
$("restore-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  try {
    const data = await api("/api/account/login", {username: $("login-name").value, password: $("login-password").value}, false);
    token = data.token;
    accountState = data;
    sessionId = "";
    $("login-password").value = "";
    remember();
    renderCharacters();
    message("Choisissez votre personnage.");
  } catch (error) { message(error.message, true); }
  finally { busy = false; }
});
for (const view of ["social", "options", "stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"]) $(`show-${view}`).addEventListener("click", () => showView(view));
$("map-place").addEventListener("change", () => { mapPlace = $("map-place").value; mapPoint = ""; showView("map"); });
$("game-menu-toggle").addEventListener("click", () => toggleGameMenu());
document.addEventListener("keydown", event => {if (event.key !== "Escape" || !session?.tutorial) return;event.preventDefault();if (document.body.classList.contains("hud-menu-open")) {$("back-view").click();toggleGameMenu(true);} else toggleGameMenu();});
$("back-view").addEventListener("click", () => {toggleGameMenu(false);document.body.classList.remove("hud-menu-open"); currentView="map"; if(session?.tutorial) renderTutorial(session.tutorial);});
$("combat-target").addEventListener("change", () => {
  combatTarget = $("combat-target").value;
  focusedMob = combatTarget;
  focusedEnemy = session?.tutorial?.mobs?.some(mob => mob.combat_id === focusedMob && mob.stats.hp.current > 0) ? focusedMob : "";
  if (session?.tutorial) renderTutorial(session.tutorial);
});
$("chat-form").addEventListener("submit", async event => {
  event.preventDefault();
  if ($("send-chat").disabled) return;
  $("send-chat").disabled = true;
  try {
    const chat = await api("/api/chat", {channel: $("chat-channel").value, message: $("chat-message").value, session_id: session?.id || null});
    $("chat-message").value = ""; $("chat-status").textContent = "Message envoyé."; renderChat(chat);
  } catch (error) { $("chat-status").textContent = error.message; }
  finally { $("send-chat").disabled = false; }
});
$("create").addEventListener("click", () => command("create"));
$("tutorial").addEventListener("click", () => command("tutorial", {field_mode: true}));
$("party-tutorial").addEventListener("click", () => command("tutorial", {field_mode: true}));
$("join-form").addEventListener("submit", event => {
  event.preventDefault();
  command("join", {invite: invitationCode($("invite-input").value)});
});
for (const action of ["start", "attack", "leave"]) $(action).addEventListener("click", () => {
  if (session) command(action, {session_id: session.id, revision: session.revision, ...(action === "attack" ? {target: $("duel-target").value} : {})});
});
$("new-room").addEventListener("click", () => command("create"));
async function logout() {
  try { await api("/api/account/logout", {}); } catch {}
  stateEpoch++;
  $("chat-panel").hidden = true;
  token = "";
  accountState = null;
  session = null;
  sessionId = "";
  for (const key of ["rpg-token", "rpg-session", "rpg-invite", "rpg-invite-session"]) sessionStorage.removeItem(key);
  location.reload();
}
$("logout").addEventListener("click", logout);
$("logout-options").addEventListener("click", logout);
async function copy(text, outputId) {
  try { await navigator.clipboard.writeText(text); message("Copié."); }
  catch { $(outputId).hidden = false; $(outputId).textContent = text; message("Sélectionnez le texte pour le copier."); }
}
$("copy-invite-link").addEventListener("click", () => copy($("invite-link").value, "invite-link"));
$("copy-invite").addEventListener("click", () => copy($("invite-code").textContent, "invite-code"));
const incomingInvite = location.hash.match(/^#invite=([A-Za-z0-9_-]{16,64})$/)?.[1];
if (incomingInvite) { $("invite-input").value = incomingInvite; history.replaceState(null, "", location.pathname + location.search); }
const invite = sessionStorage.getItem("rpg-invite");
if (invite) { $("invite-code").textContent = invite; $("invite-link").value = invitationLink(invite); $("invitation").hidden = false; }
window.addEventListener("online", () => refresh(true));
window.addEventListener("pageshow", () => refresh(true));
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(true); });
if (globalThis.rpgRealtime) {
  globalThis.rpgRealtime.onState = result => {
    if (!token || result.status !== 200 || !$("characters").hidden) return;
    const state = result.body;
    if (lastPlayer && state.player?.id !== lastPlayer.id) return;
    if (state.session && session && state.session.id === session.id && state.session.revision < session.revision) return;
    session = state.session || null;
    sessionId = session?.id || "";
    bundleHashes = result.hashes || {};
    bundleValues = result.bundles || {};
    remember();
    render(state);
  };
} else setInterval(refresh, location.hostname === "localhost" || location.hostname === "127.0.0.1" ? 250 : 1000);
refresh();

for (const id of ["bestiary-map", "bestiary-search", "bestiary-sort"]) $(id).addEventListener(id === "bestiary-search" ? "input" : "change", () => { if (session?.tutorial) renderTutorial(session.tutorial); });

for (const action of ["in", "out", "center"]) $(`field-${["in", "out"].includes(action) ? "zoom-" : ""}${action}`).addEventListener("click", () => adjustFieldCamera(action));


const touchControls = globalThis.createRpgTouchControls?.({
  state: () => {
    const adventure = session?.tutorial, actor = adventure?.battle?.players[session.me];
    return {active: Boolean(actor), busy, key: `${session?.id}:${adventure?.encounter_number}`, actor};
  },
  move: direction => {
    const adventure = session?.tutorial, actor = adventure?.battle?.players[session.me];
    const me = adventure?.players.find(player => player.id === session.me);
    if (!actor || busy || me.hp <= 0 || me.stunned || me.casting) return false;
    const destination = actor.position.map((value, i) => value + direction[i]);
    const path = gridPath(adventure.battle.map, actor.position, destination);
    if (!path?.length || path.length > 2) return false;
    tutorialCommand("battle_move", {x: destination[0], y: destination[1], path});
    return true;
  },
  stop: () => tutorialCommand("stop_move"),
  actions: () => []
});



if (typeof fetch === 'function') fetch('/api/classes').then(response => { if (!response.ok) throw new Error('Classes indisponibles'); return response.json(); }).then(available => {
  for (const item of available) {
    classes[item.id] = item.name;
    if (![...$('class-name').options].some(option => option.value === item.id)) {
      classes[item.id] = item.name;
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = item.name;
      $('class-name').append(option);
      $('new-character-class').append(option.cloneNode(true));
    }
  }
}).catch(() => {});


$("chat-toggle").addEventListener("click", () => {
  const open = document.body.classList.toggle("chat-open");
  $("chat-toggle").setAttribute("aria-expanded", String(open));
  if (open) $("chat-message").focus();
});
$("chat-channel").addEventListener("change", () => $("chat-panel").classList.toggle("group-chat", $("chat-channel").value === "group"));

for (const [view, label] of Object.entries({social:"Social", options:"Options", stats:"Perso.", equipment:"Équip.", inventory:"Sac", quest:"Quêtes", map:"Carte", bestiary:"Bestiaire", achievements:"Succès"})) {
  const button = $("show-" + view);
  button.title = button.textContent;
  button.setAttribute("aria-label", button.textContent);
  button.textContent = label;
}

$("mob-list-toggle").addEventListener("click", () => {
  const collapsed = document.body.classList.toggle("mobs-collapsed");
  $("mob-list-toggle").setAttribute("aria-expanded", String(!collapsed));
  $("mob-list-toggle").setAttribute("aria-label", collapsed ? "Afficher la liste des monstres" : "Réduire la liste des monstres");
});
const cameraSurface = $("world-map");
cameraSurface.addEventListener("pointerdown", event => {
  if (!event.isPrimary || event.button !== 0 || cameraDrag || !session?.tutorial?.battle || !fieldCamera) return;
  const node = cameraSurface.querySelector(".battle-map");
  if (!node) return;
  const view = node.viewBox.baseVal, bounds = node.getBoundingClientRect();
  cameraDrag = {pointer: event.pointerId, map: fieldCamera.map, startX: event.clientX, startY: event.clientY, x: fieldCamera.x, y: fieldCamera.y, scaleX: view.width / bounds.width / 40, scaleY: view.height / bounds.height / 40, moved: false};
});
cameraSurface.addEventListener("pointermove", event => {
  const drag = cameraDrag;
  if (!drag || event.pointerId !== drag.pointer) return;
  if (fieldCamera?.map !== drag.map || session?.tutorial?.battle?.map.id !== drag.map) { cameraDrag = null; return; }
  const dx = event.clientX - drag.startX, dy = event.clientY - drag.startY;
  if (!drag.moved && Math.hypot(dx, dy) < 6) return;
  if (!drag.moved) { clearTimeout(cameraReturnTimer); cameraReturnTimer = null; drag.moved = true; cameraSurface.setPointerCapture(event.pointerId); }
  event.preventDefault();
  fieldCamera.follow = false;
  const map = session.tutorial.battle.map;
  fieldCamera.x = Math.max(0, Math.min(map.width - 1, drag.x - dx * drag.scaleX));
  fieldCamera.y = Math.max(0, Math.min(map.height - 1, drag.y - dy * drag.scaleY));
  suppressMapClickUntil = Date.now() + 500;
  if (cameraFrame === null) cameraFrame = requestAnimationFrame(() => {
    cameraFrame = null;
    if (session?.tutorial?.battle?.map.id === drag.map && fieldCamera?.map === drag.map) renderBattle(session.tutorial, session.tutorial.players.find(player => player.id === session.me));
  });
});
for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) cameraSurface.addEventListener(name, releaseCamera);
for (const name of ["click", "dblclick"]) cameraSurface.addEventListener(name, event => {
  if (Date.now() < suppressMapClickUntil) { event.preventDefault(); event.stopImmediatePropagation(); }
}, true);
window.addEventListener("blur", () => releaseCamera());
window.addEventListener("resize", () => { if (session?.tutorial?.battle) renderTutorial(session.tutorial); });
