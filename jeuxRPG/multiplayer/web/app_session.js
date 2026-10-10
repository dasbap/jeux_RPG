"use strict";
async function refresh(force = false) {
  if (globalThis.navigator?.onLine === false) return;
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
    nextRefreshAt = Date.now() + Math.round(Math.min(30000, 1000 * 2 ** Math.min(5, refreshFailures - 1)) * (.9 + Math.random() * .2));
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
  } finally { polling = false; scheduleRefresh(); }
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
    scheduleRefresh();
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
  try { await api("/api/account/logout", {}); }
  catch (error) {
    if (!["unauthorized", "account_suspended"].includes(error.code)) {
      message("Déconnexion non confirmée. Vérifiez votre connexion et réessayez.", true);
      return;
    }
  }
  globalThis.rpgRealtime?.close();
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
let refreshTimer = null;
function refreshInterval() {
  if (!token || !$("characters").hidden || globalThis.navigator?.onLine === false) return 30000;
  if (document.hidden || globalThis.rpgRealtime?.connected) return 20000;
  const tutorial = session?.tutorial;
  const activeBattle = tutorial?.battle && (!tutorial.field_map || tutorial.mobs?.some(mob => mob.alerted && mob.stats?.hp?.current > 0) || [...Object.values(tutorial.battle.players || {}), ...Object.values(tutorial.battle.summons || {})].some(unit => unit.route?.length || unit.casting));
  if (activeBattle || tutorial?.transit) return location.hostname === "localhost" || location.hostname === "127.0.0.1" ? 250 : 1000;
  if (!session?.tutorial) return 5000;
  return currentView === "map" ? 3600 : 15000;
}
function scheduleRefresh() {
  clearTimeout(refreshTimer);
  const delay = Math.max(Math.round(refreshInterval() * (.9 + Math.random() * .2)), nextRefreshAt - Date.now());
  refreshTimer = setTimeout(async () => {
    try { if (!globalThis.rpgRealtime?.connected) await refresh(); }
    finally { scheduleRefresh(); }
  }, delay);
}
async function resumeRefresh() {
  try { await refresh(true); }
  finally { scheduleRefresh(); }
}
window.addEventListener("online", resumeRefresh);
window.addEventListener("pageshow", resumeRefresh);
document.addEventListener("visibilitychange", () => { if (!document.hidden) return resumeRefresh(); scheduleRefresh(); });
if (globalThis.rpgRealtime) {
  globalThis.rpgRealtime.onConnection = scheduleRefresh;
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
}
resumeRefresh();
