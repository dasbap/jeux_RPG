"use strict";
const $ = id => document.getElementById(id);
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
const sectionSignatures = new Map();
function sectionChanged(name, value) {
  const signature = JSON.stringify(value);
  if (sectionSignatures.get(name) === signature) return false;
  sectionSignatures.set(name, signature);
  return true;
}
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
function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}
function requestId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(value => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
function invitationCode(value) {
  const trimmed = value.trim();
  try { return new URL(trimmed).hash.match(/^#invite=([A-Za-z0-9_-]{16,64})$/)?.[1] || trimmed; }
  catch { return trimmed; }
}
function invitationLink(code) {
  const url = new URL(location.href);
  url.hash = `invite=${code}`;
  url.search = "";
  return url.href;
}
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
