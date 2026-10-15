"use strict";

async function switchGameMode(mode, {resume = false} = {}) {
  if (busy || mode === gameMode) return;
  let resumeSelected = false;
  busy = true;
  stateEpoch++;
  message(mode === "solo" ? "Chargement du moteur solo… La première ouverture nécessite Internet." : "Ouverture du mode en ligne…");
  try {
    if (mode === "solo") {
      const local = await createRpgSoloTransport();
      globalThis.rpgRealtime?.close();
      soloTransport = local;
      globalThis.rpgRealtime = local;
      gameMode = "solo";
      token = "";
      bindTransport();
      local.onError = error => message("Sauvegarde solo : " + error.message, true);
      local.onSave = () => { if (gameMode === "solo") $("connection").textContent = "Solo · sauvegarde locale effectuée"; };
      accountState = await api("/api/account/me", undefined, false);
      token = accountState.token;
      const available = await api("/api/classes", undefined, false);
      for (const item of available) {
        classes[item.id] = item.name;
        for (const id of ["class-name", "new-character-class"]) if (![...$(id).options].some(option => option.value === item.id)) {
          const option = document.createElement("option"); option.value = item.id; option.textContent = item.name; $(id).append(option);
        }
      }
    } else {
      await soloTransport.close();
      soloTransport = null;
      globalThis.rpgRealtime = onlineTransport;
      gameMode = "online";
      token = sessionStorage.getItem("rpg-token") || "";
      accountState = null;
      bindTransport();
    }
    localStorage.setItem("rpg-mode", gameMode);
    resumeSelected = gameMode === "solo" && resume && Boolean(accountState.selected);
    stateEpoch++;
    session = null; sessionId = ""; lastPlayer = null; socialState = null; presenceState = null;
    bundleToken = ""; bundleHashes = {}; bundleValues = {}; sectionSignatures.clear();
    currentView = "map"; refreshFailures = 0; nextRefreshAt = 0;
    $("show-social").hidden = gameMode === "solo";
    for (const id of ["lobby", "battle", "character-menu", "chat-panel", "characters", "invitation"]) $(id).hidden = true;
    $("registration").hidden = Boolean(token) || gameMode === "solo";
    document.body.classList.remove("combat-active", "hud-menu-open", "chat-open");
    if (gameMode === "solo") {
      if (resumeSelected) soloTransport.subscribe(true);
      else renderCharacters();
    }
    else if (token) { accountState = await api("/api/account/me"); renderCharacters(); }
    message(resumeSelected ? "Reprise de votre aventure solo…" : gameMode === "solo" ? "Choisissez ou créez votre personnage solo." : "Mode en ligne.");
  } catch (error) {
    if (gameMode === "online" && !accountState) $("registration").hidden = false;
    message(error.message, true);
  }
  finally {
    busy = false;
    if (resumeSelected) await refresh(true);
    scheduleRefresh();
  }
}
$("solo-entry").addEventListener("click", () => switchGameMode("solo"));
$("mode-solo").addEventListener("click", () => switchGameMode("solo"));
$("mode-online").addEventListener("click", () => switchGameMode("online"));
document.addEventListener("visibilitychange", () => { if (document.hidden) soloTransport?.flush().catch(error => message(error.message, true)); });

async function restoreGameMode() {
  if (restoreSolo) return switchGameMode("solo", {resume: true});
  if (localStorage.getItem("rpg-mode") || token || !globalThis.indexedDB?.databases) return;
  try {
    const databases = await indexedDB.databases();
    if (databases.some(database => database.name === "jeux-rpg-solo")) await switchGameMode("solo", {resume: true});
  } catch (error) { message("Reprise solo : " + error.message, true); }
}
restoreGameMode();
