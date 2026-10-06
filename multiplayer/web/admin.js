"use strict";
let adminToken = "";
let offset = 0;
let pending = null;
let busy = false;
let hasMore = false;
const el = id => document.getElementById(id);
async function api(method, body) {
  const query = method === "GET" ? `?search=${encodeURIComponent(el("search").value)}&offset=${offset}` : "";
  const response = await fetch(`/api/admin/accounts${query}`, {method, headers: {Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json"}, ...(body ? {body: JSON.stringify(body)} : {})});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) logout();
    throw new Error(data.message || "Requête refusée.");
  }
  return data;
}
async function load() {
  const data = await api("GET");
  hasMore = data.has_more;
  el("accounts").replaceChildren();
  for (const account of data.accounts) {
    const row = document.createElement("tr");
    const cell = value => {const td = document.createElement("td"); td.textContent = value; row.append(td); return td;};
    const name = cell(account.name);
    const identifier = document.createElement("small"); identifier.textContent = account.id; name.append(identifier);
    cell(account.class_name); cell(account.suspended ? "Suspendu" : "Actif");
    const actions = cell("");
    for (const [action, label] of [["rename", "Renommer"], [account.suspended ? "restore" : "suspend", account.suspended ? "Rétablir" : "Suspendre"], ["revoke", "Révoquer l’accès"]]) {
      const button = document.createElement("button"); button.textContent = label; button.className = "secondary";
      button.addEventListener("click", () => edit(account, action, label)); actions.append(button);
    }
    el("accounts").append(row);
  }
  el("count").textContent = data.accounts.length ? `Comptes ${offset + 1} à ${offset + data.accounts.length}` : "Aucun compte trouvé.";
  el("previous").disabled = offset === 0; el("next").disabled = !data.has_more;
  el("login").hidden = true; el("panel").hidden = false;
}
function edit(account, action, label) {
  pending = {player_id: account.id, action};
  el("edit-title").textContent = `${label} · ${account.name}`;
  el("edit-description").textContent = action === "revoke" ? "Le jeton actuel sera invalidé. Ce compte ne pourra plus se connecter avec ce jeton." : action === "suspend" ? "Le compte reste conservé, mais ses requêtes de jeu seront refusées." : "";
  el("name-label").hidden = el("new-name").hidden = action !== "rename";
  el("new-name").required = action === "rename"; el("new-name").value = account.name;
  el("edit").hidden = false; el("panel").hidden = true;
  (action === "rename" ? el("new-name") : el("confirm-action")).focus();
}
function logout() {
  adminToken = ""; pending = null; el("accounts").replaceChildren(); el("panel").hidden = el("edit").hidden = true; el("login").hidden = false; el("admin-token").value = "";
}
async function perform(action) {
  if (busy) return;
  busy = true; el("status").textContent = "Chargement…";
  document.querySelectorAll("button").forEach(button => {button.disabled = true;});
  try {await action(); el("status").textContent = "";} catch (error) {el("status").textContent = error.message;}
  finally {busy = false; document.querySelectorAll("button").forEach(button => {button.disabled = false;}); el("previous").disabled = offset === 0; el("next").disabled = !hasMore;}
}
el("login-form").addEventListener("submit", event => {event.preventDefault(); adminToken = el("admin-token").value; el("admin-token").value = ""; offset = 0; perform(load);});
el("search-form").addEventListener("submit", event => {event.preventDefault(); offset = 0; perform(load);});
el("logout").addEventListener("click", logout);
el("previous").addEventListener("click", () => {offset = Math.max(0, offset - 50); perform(load);});
el("next").addEventListener("click", () => {offset += 50; perform(load);});
el("cancel-action").addEventListener("click", () => {pending = null; el("edit").hidden = true; el("panel").hidden = false;});
el("edit-form").addEventListener("submit", event => {event.preventDefault(); perform(async () => {if (!pending) return; const body = {...pending}; if (body.action === "rename") body.name = el("new-name").value; await api("POST", body); pending = null; el("edit").hidden = true; await load();});});
