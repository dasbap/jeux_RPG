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
