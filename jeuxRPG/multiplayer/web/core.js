"use strict";
const $ = id => document.getElementById(id);
const sectionSignatures = new Map();

function sectionChanged(name, value) {
  const signature = JSON.stringify(value);
  if (sectionSignatures.get(name) === signature) return false;
  sectionSignatures.set(name, signature);
  return true;
}

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

function paragraphs(container, texts) {
  $(container).replaceChildren();
  for (const text of texts) {
    const p = document.createElement("p");
    p.textContent = text;
    $(container).append(p);
  }
}

function equipmentBonuses(piece) {
  return [["hp", "PV"], ["endurance", "endurance"], ["force", "force"], ["intelligence", "intelligence"], ["sagesse", "sagesse"]].filter(([key]) => piece[key] > 0).map(([key, label]) => `+${piece[key]} ${label}`).join(" · ");
}
