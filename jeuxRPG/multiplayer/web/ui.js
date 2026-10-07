"use strict";
function renderChat(chat) {
  $("chat-panel").hidden = !token;
  if (!chat) return;
  $("online-players").textContent = `En ligne : ${chat.online.map(player => player.name).join(", ") || "personne"}`;
  $("chat-channel").querySelector('[value="group"]').disabled = !session && !socialState?.team;
  if (!session && !socialState?.team && $("chat-channel").value === "group") $("chat-channel").value = "global";
  for (const channel of ["global", "group"]) {
    const list = $(`chat-${channel}`), follow = list.scrollTop + list.clientHeight >= list.scrollHeight - 20;
    const messages = chat[channel] || [];
    const retained = new Set(messages.map(item => String(item.id)));
    for (const child of [...list.children]) if (!retained.has(child.dataset.id)) child.remove();
    for (const item of messages) {
      if ([...list.children].some(child => child.dataset.id === String(item.id))) continue;
      const row = document.createElement("li"); row.dataset.id = item.id; row.textContent = `${item.name} : ${item.message}`; list.append(row);
    }
    if (follow) list.scrollTop = list.scrollHeight;
  }
}

function renderAchievements(data) {
  if (!data || !sectionChanged("achievements", data)) return;
  $("achievement-summary").textContent = `Niveau maximum ${data.max_level} · ${data.kills} créature(s) vaincue(s) · meilleur temps ${data.best_seconds === null ? "—" : data.best_seconds.toFixed(1) + " s"}`;
  $("achievement-rows").replaceChildren();
  for (const item of data.rows) {
    const row = document.createElement("tr"); row.className = item.unlocked ? "achievement-unlocked" : "";
    for (const text of [item.name, item.progress, item.title]) { const cell = document.createElement("td"); cell.textContent = text; row.append(cell); }
    $("achievement-rows").append(row);
  }
  $("achievement-titles").textContent = `Titres obtenus : ${data.unlocked_titles.join(" · ") || "aucun"}`;
}

function render(state) {
  const signature = JSON.stringify([state, busy], (key, value) => ["game_time", "revision"].includes(key) ? undefined : value);
  if (sectionSignatures.get("state-render") === signature) return;
  sectionSignatures.set("state-render", signature);
  lastPlayer = state.player;
  if (state.presence) presenceState = state.presence;
  if (state.social) socialState = state.social;
  renderChat(state.chat);
  renderSocial();
  $("registration").hidden = Boolean(token);
  $("lobby").hidden = !token || !$("characters").hidden;
  $("player-name").textContent = `${state.player.name} · ${classes[state.player.class_name] || state.player.class_name}`;
  $("connection").textContent = "Connecté · état partagé";
  $("room-controls").hidden = Boolean(session && session.state !== "finished");
  $("battle").hidden = !session;
  $("invitation").hidden = !(session && session.state === "lobby" && session.owner === session.me && sessionStorage.getItem("rpg-invite-session") === session.id);
  if (!$("invitation").hidden) {
    const code = sessionStorage.getItem("rpg-invite") || "";
    $("invite-code").textContent = code;
    $("invite-link").value = invitationLink(code);
    $("invite-status").textContent = `Invitation valable encore ${Math.ceil(session.remaining_real_seconds / 60)} min · ${session.players.length}/4 joueurs. Attendez votre compagnon avant de démarrer.`;
  }
  $("tutorial-panel").hidden = !(session && session.tutorial);
  $("character-menu").hidden = !(session && session.tutorial);
  $("duel-target-controls").hidden = true;
  if (!session) return;
  $("battle-title").textContent = {lobby: "En attente du second joueur", running: "Duel en cours", finished: "Duel terminé"}[session.state];
  $("version").textContent = `État ${session.revision}`;
  if (!session.tutorial) $("tutorial-panel").before($("fighters"));
  $("fighters").replaceChildren();
  $("fighters").hidden = Boolean(session.tutorial);
  for (const player of session.tutorial ? session.tutorial.players : session.players) {
    const article = document.createElement("article");
    article.className = `fighter${player.id === session.me ? " mine" : ""}`;
    const title = document.createElement("h3");
    title.textContent = `${player.name}${player.id === session.me ? " · vous" : ""}`;
    const type = document.createElement("div");
    type.className = "class";
    type.textContent = `${classes[player.class_name] || player.class_name}${player.level ? ` · niveau ${player.level}` : ""}`;
    const bar = document.createElement("div");
    bar.className = "health";
    bar.setAttribute("role", "meter");
    bar.setAttribute("aria-label", `Points de vie de ${player.name}`);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", String(player.max_hp));
    bar.setAttribute("aria-valuenow", String(player.hp));
    const fill = document.createElement("progress");
    fill.className = "health-fill";
    fill.max = player.max_hp;
    fill.value = player.hp;
    bar.append(fill);
    const hp = document.createElement("div");
    hp.textContent = `${player.hp} / ${player.max_hp} PV`;
    article.append(title, type, bar, hp);
    $("fighters").append(article);
  }
  const me = session.players.find(player => player.id === session.me);
  $("start").hidden = session.state !== "lobby" || session.owner !== session.me;
  $("start").disabled = busy || session.players.length < 2;
  $("party-tutorial").hidden = session.state !== "lobby" || session.owner !== session.me;
  $("party-tutorial").disabled = busy || session.players.length < 2;
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

function toggleGameMenu(open = $("game-menu-items").hidden) {
  $("game-menu-items").hidden = !open;
  $("game-menu-toggle").setAttribute("aria-expanded", String(open));
}

function showView(view) {
  toggleGameMenu(false);
  if (currentView === view && document.body.classList.contains("hud-menu-open")) {document.body.classList.remove("hud-menu-open");currentView = "map";if(session?.tutorial) renderTutorial(session.tutorial);return;}
  if (["social", "options", "stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"].includes(view)) currentView = view;
  document.body.classList.toggle("hud-menu-open", Boolean(session?.tutorial));
  renderSocial();
  if (session && session.tutorial) renderTutorial(session.tutorial);
}

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

function renderSocial() {
  if (!$("social-view") || currentView !== "social") return;
  const data = socialState || {friends: [], requests: [], invitations: [], team: null, rallies: []};
  const presence = presenceState;
  $("social-capacity").textContent = presence ? `Serveur ${presence.realm} · ${presence.online}/40 joueurs · équipe ${data.team?.members.length || 1}/4 · PvP désactivé` : "Choisissez votre personnage pour retrouver les autres joueurs.";
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
  for (const member of data.team?.members || []) {
    const position = member.position ? ` · ${member.position.map(Math.round).join(", ")}` : "";
    const mode = {travel: "en route", combat: "en combat", exploration: "en exploration", outing: member.waiting ? "attend sur la route" : "vue sortie", lobby: "au salon"}[member.mode] || "";
    const text = `Équipe · ${member.name} (${member.username}) · ${member.online ? `${member.location} · ${mode} · serveur ${member.realm}${position}` : "hors ligne"}`;
    row(`member-${member.id}`, text, member.player_id && member.player_id !== lastPlayer?.id && member.mode === "outing" ? [["Rejoindre", "join_ally", {player_id: member.player_id}]] : []);
  }
  for (const rally of data.rallies) row(`rally-${rally.id}`, `${rally.username} appelle les alliés vers ${session?.tutorial?.world.places.find(place => place.id === rally.destination)?.name || rally.destination}`, [["M’y diriger", "rally_accept", {rally_id: rally.id}]]);
  for (const player of presence?.nearby || []) row(`nearby-${player.id}`, `${player.ally ? "Allié" : "Joueur dans la zone"} · ${player.name} · ${player.location}`, []);
  if (data.team) row("team-leave", "Les alliés voyagent librement. Quitter l’équipe conserve votre progression.", [["Quitter l’équipe", "team_leave", {}]]);
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
