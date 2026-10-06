"use strict";
if (typeof WebSocket === "function" && location.hostname.endsWith(".vercel.app")) {
  globalThis.rpgRealtime = (() => {
    let socket = null;
    let opening = null;
    let delay = 250;
    let reconnectTimer = null;
    let heartbeat = null;
    let subscription = null;
    let subscriptionId = null;
    let sequence = 0;
    let stateBundles = {};
    const pending = new Map();
    const transport = {onState: null, request};
    function open() {
      if (socket?.readyState === WebSocket.OPEN) return Promise.resolve(socket);
      if (opening) return opening;
      opening = new Promise((resolve, reject) => {
        const endpoint = new URL("/api/ws", location.href);
        endpoint.protocol = location.protocol === "https:" ? "wss:" : "ws:";
        socket = new WebSocket(endpoint);
        const deadline = setTimeout(() => { reject(new Error("Connexion temps réel trop lente.")); socket.close(); }, 25000);
        socket.addEventListener("open", () => {
          clearTimeout(deadline);
          delay = 250;
          opening = null;
          heartbeat = setInterval(() => {
            if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: "ping"}));
          }, 10000);
          resolve(socket);
          if (subscription) request(subscription.path, subscription.options).then(async response => {
            transport.onState?.({status: response.status, body: await response.json()});
          }).catch(() => {});
        });
        socket.addEventListener("message", event => {
          let message;
          try { message = JSON.parse(event.data); } catch { return; }
          if (message.type === "state") {
            if (message.subscription !== subscriptionId) return;
            const result = message.result;
            if (result.body.bundle_protocol === 1) {
              const data = result.body;
              for (const key of data.removed) delete stateBundles[key];
              Object.assign(stateBundles, data.bundles);
              const assembled = {};
              for (const [path, value] of Object.entries(stateBundles).sort((a,b) => a[0].split("/").length - b[0].split("/").length)) {
                const parts = path.split("/");
                let target = assembled;
                for (const part of parts.slice(0,-1)) target = target[part] ||= {};
                target[parts.at(-1)] = structuredClone(value);
              }
              transport.onState?.({...result, body: assembled, hashes: data.hashes, bundles: structuredClone(stateBundles)});
            } else transport.onState?.(result);
          } else if (pending.has(message.id)) {
            pending.get(message.id).resolve(message.result);
            pending.delete(message.id);
          }
        });
        socket.addEventListener("error", () => reject(new Error("Connexion temps réel indisponible.")));
        socket.addEventListener("close", () => {
          clearTimeout(deadline);
          clearInterval(heartbeat);
          opening = null;
          reject(new Error("Connexion temps réel interrompue."));
          for (const item of pending.values()) item.reject(new Error("Connexion interrompue. Reconnexion automatique."));
          pending.clear();
          if (reconnectTimer === null) reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            open().catch(() => {});
          }, delay);
          delay = Math.min(10000, delay * 2);
        });
      });
      return opening;
    }
    async function request(path, options = {}) {
      const connection = await open();
      const id = String(++sequence);
      if (path === "/api/state") {
        subscription = {path, options};
        subscriptionId = id;
        stateBundles = {};
      }
      const result = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { pending.delete(id); reject(new Error("Réponse temps réel trop lente.")); }, 30000);
        pending.set(id, {resolve: value => {clearTimeout(timer); resolve(value);}, reject: error => {clearTimeout(timer); reject(error);}});
        connection.send(JSON.stringify({id, path, method: options.method || "GET", headers: options.headers || {}, body: options.body ? JSON.parse(options.body) : null}));
      });
      return {ok: result.status >= 200 && result.status < 300, status: result.status, json: async () => result.body};
    }
    return transport;
  })();
}
