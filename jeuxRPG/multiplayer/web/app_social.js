"use strict";
function renderCharacters() {
  if (!accountState) return;
  document.body.classList.remove("combat-active", "hud-menu-open");
  $("characters").hidden = false;
  $("registration").hidden = true;
  $("lobby").hidden = true;
  $("battle").hidden = true;
  $("character-menu").hidden = true;
  $("chat-panel").hidden = true;
  $("account-title").textContent = `${accountState.account.username} · mes personnages`;
  $("character-list").replaceChildren();
  for (const character of accountState.characters) {
    const button = document.createElement("button");
    button.textContent = `${character.name} · ${classes[character.class_name] || character.class_name}`;
    button.addEventListener("click", () => selectCharacter({action: "select", player_id: character.id}));
    $("character-list").append(button);
  }
  const owned = new Set(accountState.characters.map(character => character.class_name));
  for (const option of $("new-character-class").options) option.disabled = owned.has(option.value);
  $("new-character-class").value = [...$("new-character-class").options].find(option => !option.disabled)?.value || "";
  $("character-create").hidden = !$("new-character-class").value;
  $("character-cancel").hidden = !accountState.selected;
}
async function selectCharacter(body) {
  if (busy) return;
  busy = true;
  stateEpoch++;
  try {
    accountState = await api("/api/account/character", body);
    session = null;
    sessionId = "";
    presenceState = null;
    socialState = null;
    currentView = "map";
    sectionSignatures.clear();
    $("characters").hidden = true;
    remember();
  } catch (error) { message(error.message, true); }
  finally { busy = false; if ($("characters").hidden) await refresh(true); }
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
function renderSocial() {
  if (!$("social-view") || currentView !== "social") return;
  const data = socialState || {friends: [], requests: [], invitations: [], team: null, rallies: [], guild: null, guild_invitations: []};
  const presence = presenceState;
  $("social-capacity").textContent = presence ? `Serveur ${presence.realm} · ${presence.online}/40 joueurs · équipe ${data.team?.members.length || 1}/4 · guilde ${data.guild ? data.guild.members.length + "/" + data.guild.capacity : "aucune"} · PvP désactivé` : "Choisissez votre personnage pour retrouver les autres joueurs.";
  $("guild-create").hidden = Boolean(data.guild);
  $("social-guild-invite").hidden = !data.guild || data.guild.role !== "owner";
  const root = $("social-content");
  const retained = new Set();
  function row(key, text, actions) {
    retained.add(key);
    let node = [...root.children].find(child => child.dataset.socialRow === key);
    if (!node) { node = document.createElement("article"); node.dataset.socialRow = key; node.className = "social-row"; node.append(document.createElement("p")); root.append(node); }
    node.firstChild.textContent = text;
    const buttons = new Set();
    for (const [label, action, params] of actions) {
      buttons.add(action);
      let button = [...node.querySelectorAll("button")].find(item => item.dataset.socialAction === action);
      if (!button) { button = document.createElement("button"); button.dataset.socialAction = action; button.className = "secondary"; node.append(button); }
      button.textContent = label;
      button.disabled = busy;
      button.onclick = () => socialAction(action, params);
    }
    for (const button of [...node.querySelectorAll("button")]) if (!buttons.has(button.dataset.socialAction)) button.remove();
  }
  for (const friend of data.friends) row(`friend-${friend.id}`, `Ami · ${friend.username}`, [["Inviter", "team_invite", {username: friend.username}], ["Retirer", "friend_remove", {account_id: friend.id}]]);
  for (const friend of data.requests) row(`request-${friend.id}`, `${friend.incoming ? "Demande reçue" : "Demande envoyée"} · ${friend.username}`, [...(friend.incoming ? [["Accepter", "friend_accept", {account_id: friend.id}]] : []), ["Refuser / annuler", "friend_remove", {account_id: friend.id}]]);
  for (const invite of data.invitations) row(`invite-${invite.id}`, `Invitation dans l’équipe de ${invite.username}`, [["Accepter", "team_accept", {invite_id: invite.id}], ["Refuser", "team_decline", {invite_id: invite.id}]]);
  for (const invite of data.guild_invitations || []) row(`guild-invite-${invite.id}`, `Invitation guilde · ${invite.name} · par ${invite.username}`, [["Accepter", "guild_accept", {invite_id: invite.id}], ["Refuser", "guild_decline", {invite_id: invite.id}]]);
  for (const member of data.guild?.members || []) {
    const actions = data.guild.role === "owner" && member.id !== accountState?.account?.id ? [["Exclure", "guild_kick", {account_id: member.id}]] : [];
    row(`guild-member-${member.id}`, `Guilde ${data.guild.name} · ${member.username} · ${member.role === "owner" ? "chef" : "membre"} · ${member.online ? "en ligne" : "hors ligne"}`, actions);
  }
  for (const member of data.team?.members || []) {
    const position = member.position ? ` · ${member.position.map(Math.round).join(", ")}` : "";
    const mode = {travel: "en route", combat: "en combat", exploration: "en exploration", outing: member.waiting ? "attend sur la route" : "vue sortie", lobby: "au salon"}[member.mode] || "";
    const text = `Équipe · ${member.name} (${member.username}) · ${member.online ? `${member.location} · ${mode} · serveur ${member.realm}${position}` : "hors ligne"}`;
    row(`member-${member.id}`, text, member.player_id && member.player_id !== lastPlayer?.id && member.mode === "outing" ? [["Rejoindre", "join_ally", {player_id: member.player_id}]] : []);
  }
  for (const rally of data.rallies) row(`rally-${rally.id}`, `${rally.username} appelle les alliés vers ${session?.tutorial?.world.places.find(place => place.id === rally.destination)?.name || rally.destination}`, [["M’y diriger", "rally_accept", {rally_id: rally.id}]]);
  for (const player of presence?.nearby || []) row(`nearby-${player.id}`, `${player.ally ? "Allié" : "Joueur dans la zone"} · ${player.name} · ${player.location}`, []);
  if (data.team) row("team-leave", "Les alliés voyagent librement. Quitter l’équipe conserve votre progression.", [["Quitter l’équipe", "team_leave", {}]]);
  if (data.guild) row("guild-leave", `Guilde · ${data.guild.name}. Le chef est transféré au membre le plus ancien s’il quitte.`, [["Quitter la guilde", "guild_leave", {}]]);
  for (const child of [...root.children]) if (!retained.has(child.dataset.socialRow)) child.remove();
  if (!root.children.length) row("empty", "Ajoutez un joueur par son nom de compte ou invitez-le dans votre équipe.", []);
  const travel = $("social-travel");
  const adventure = session?.tutorial;
  if (!sectionChanged("social-travel", [presence?.realm, presence?.realms, adventure?.world.current, adventure?.moving, adventure?.transit?.waiting, Boolean(adventure?.battle), Boolean(data.team), busy])) return;
  travel.replaceChildren();
  function button(label, action, params) { const node = document.createElement("button"); node.textContent = label; node.disabled = busy; node.onclick = () => socialAction(action, params); travel.append(node); }
  if (adventure?.transit && !adventure.battle) button(adventure.transit.waiting ? "Reprendre le trajet" : "Attendre les alliés", adventure.transit.waiting ? "resume" : "wait", {});
  if (data.team && adventure && !adventure.battle && !adventure.moving) {
    const select = document.createElement("select"); select.id = "rally-destination"; select.setAttribute("aria-label", "Destination du ralliement");
    for (const place of adventure.world.places) { const option = document.createElement("option"); option.value = place.id; option.textContent = place.name; select.append(option); }
    travel.append(select);
    const call = document.createElement("button"); call.textContent = "Appeler les alliés"; call.disabled = busy; call.onclick = () => socialAction("rally", {destination: select.value}); travel.append(call);
  }
  for (let index = 1; index <= (presence?.realms || 0); index++) if (index !== presence.realm) button(`Rejoindre le serveur ${index}`, "realm", {realm: index});
}
for (const id of ["choose-character", "choose-character-options"]) $(id).addEventListener("click", async () => {
  try { accountState = await api("/api/account/me"); renderCharacters(); } catch (error) { message(error.message, true); }
});
$("character-create").addEventListener("submit", event => {event.preventDefault(); selectCharacter({action: "create", name: $("new-character-name").value, class_name: $("new-character-class").value});});
$("character-cancel").addEventListener("click", () => {$("characters").hidden = true; sectionSignatures.clear(); refresh(true);});
$("social-search").addEventListener("submit", event => {event.preventDefault(); socialAction("friend_add", {username: $("social-name").value.trim()});});
$("social-invite").addEventListener("click", () => socialAction("team_invite", {username: $("social-name").value.trim()}));
$("social-guild-invite").addEventListener("click", () => socialAction("guild_invite", {username: $("social-name").value.trim()}));
$("guild-create").addEventListener("submit", event => { event.preventDefault(); socialAction("guild_create", {name: $("guild-name").value.trim()}); });
