"use strict";
globalThis.createRpgSoloTransport = async function () {
  if (!navigator.locks) throw new Error("Ce navigateur ne permet pas la sauvegarde solo sécurisée. Utilisez un navigateur récent.");
  let release, readyResolve, readyReject;
  const locked = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
  const lockTask = navigator.locks.request("jeux-rpg-solo", {ifAvailable: true}, async lock => {
    if (!lock) { readyReject(new Error("Le mode solo est déjà ouvert dans un autre onglet.")); return; }
    readyResolve();
    await new Promise(resolve => { release = resolve; });
  }).catch(readyReject);
  await locked;
  let worker;
  try { worker = new Worker(document.querySelector('meta[name="rpg-solo-worker"]')?.content || "/solo_worker.js"); }
  catch (error) { release(); await lockTask; throw error; }
  const pending = new Map();
  let sequence = 0, closed = false;
  const transport = {connected: true, onState: null, onConnection: null, onSave: null, onError: null};
  function send(type, payload) {
    if (closed) return Promise.reject(new Error("Le mode solo est fermé."));
    const id = ++sequence;
    return new Promise((resolve, reject) => { pending.set(id, {resolve, reject}); worker.postMessage({id, type, payload}); });
  }
  worker.onmessage = ({data}) => {
    if (data.type === "state") { transport.onState?.(data.result); return; }
    if (data.type === "saved") { transport.onSave?.(data.at); return; }
    if (data.type === "error") { transport.onError?.(new Error(data.error)); return; }
    const task = pending.get(data.id);
    if (!task) return;
    pending.delete(data.id);
    if (data.error) task.reject(new Error(data.error)); else task.resolve(data.result);
  };
  worker.onerror = event => {
    const error = new Error(event.message || "Le moteur solo a été interrompu.");
    for (const task of pending.values()) task.reject(error);
    pending.clear(); transport.onError?.(error);
  };
  transport.request = async (path, options = {}) => {
    if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const result = await send("request", {path, body: options.body ? JSON.parse(options.body) : null, token: (options.headers?.Authorization || "").replace(/^Bearer /, "")});
    return new Response(JSON.stringify(result.body), {status: result.status, headers: {"Content-Type": "application/json"}});
  };
  transport.subscribe = value => send("subscribe", value);
  transport.flush = () => send("flush");
  transport.close = async () => {
    await transport.flush();
    {
      closed = true; transport.connected = false; worker.terminate(); release(); await lockTask;
      for (const task of pending.values()) task.reject(new Error("Mode solo fermé."));
      pending.clear(); transport.onConnection?.();
    }
  };
  try { await send("init"); } catch (error) { closed = true; worker.terminate(); release(); await lockTask; throw error; }
  return transport;
};
