"use strict";

async function switchGameMode(mode) {
  if (busy || mode === gameMode) return;
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
    stateEpoch++;
    session = null; sessionId = ""; lastPlayer = null; socialState = null; presenceState = null;
    bundleToken = ""; bundleHashes = {}; bundleValues = {}; sectionSignatures.clear();
    currentView = "map"; refreshFailures = 0; nextRefreshAt = 0;
    $("show-social").hidden = gameMode === "solo";
    for (const id of ["lobby", "battle", "character-menu", "chat-panel", "characters", "invitation"]) $(id).hidden = true;
    $("registration").hidden = Boolean(token) || gameMode === "solo";
    document.body.classList.remove("combat-active", "hud-menu-open", "chat-open");
    if (gameMode === "solo") renderCharacters();
    else if (token) { accountState = await api("/api/account/me"); renderCharacters(); }
    message(gameMode === "solo" ? "Choisissez ou créez votre personnage solo." : "Mode en ligne.");
  } catch (error) {
    if (gameMode === "online" && !accountState) $("registration").hidden = false;
    message(error.message, true);
  }
  finally { busy = false; scheduleRefresh(); }
}
$("solo-entry").addEventListener("click", () => switchGameMode("solo"));
$("mode-solo").addEventListener("click", () => switchGameMode("solo"));
$("mode-online").addEventListener("click", () => switchGameMode("online"));
document.addEventListener("visibilitychange", () => { if (document.hidden) soloTransport?.flush().catch(error => message(error.message, true)); });
