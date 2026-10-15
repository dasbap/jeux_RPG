"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {JSDOM} = require(require.resolve("jsdom", {paths: [path.join(__dirname, "..", ".ui-test")]}));
async function check(selected, legacy = false) {
  const html = fs.readFileSync(path.join(__dirname, "../jeuxRPG/multiplayer/web/index.html"), "utf8");
  const dom = new JSDOM(html, {url:"https://game.vercel.app/",runScripts:"outside-only"});
  const w = dom.window;
  if (legacy) w.indexedDB = {databases: async () => [{name:"jeux-rpg-solo"}]};
  else { w.localStorage.setItem("rpg-mode", "solo"); w.sessionStorage.setItem("rpg-token", "online-token"); }
  w.sessionStorage.setItem("rpg-session", "online-session");
  w.fetch = async url => {assert.equal(url,"/api/classes"); return {ok:true,json:async()=>[]};};
  w.setTimeout = () => 1;
  w.setInterval = () => 1;
  w.resumed = 0;
  let onlineCalls = 0, subscribed = false;
  w.rpgRealtime = {close() {}, request() {onlineCalls++; throw new Error("Online unavailable");}};
  w.createRpgSoloTransport = async () => ({connected:true, subscribe(value) {subscribed=value;}, request:async url => ({ok:true,json:async()=>url === "/api/classes" ? [] : {account:{username:"Local"},characters:[],selected,token:selected ? "local-token" : ""}})});
  w.eval(require("./client_source.cjs")() + '; refresh = async () => {if (gameMode === "solo" && token) window.resumed++;}; window.state = () => ({gameMode,token,sessionId});');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(w.state().gameMode, "solo");
  assert.equal(w.state().token, selected ? "local-token" : "");
  assert.equal(w.state().sessionId, "");
  assert.equal(w.sessionStorage.getItem("rpg-token"), legacy ? null : "online-token");
  assert.equal(onlineCalls, 0);
  assert.equal(w.resumed > 0, Boolean(selected));
  assert.equal(subscribed, Boolean(selected));
  assert.equal(w.document.getElementById("characters").hidden, Boolean(selected));
  dom.window.close();
}
(async () => {await check("local-character"); await check(null); await check("legacy-character", true); console.log("Refresh solo : reprise automatique du personnage ou menu local vide, sans connexion en ligne ni perte de session distante.");})().catch(error => {console.error(error); process.exitCode=1;});
