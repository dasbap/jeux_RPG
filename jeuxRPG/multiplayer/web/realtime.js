"use strict";
if (typeof WebSocket === "function" && location.hostname.endsWith(".vercel.app")) {
  globalThis.rpgRealtime = (() => {
    let socket = null;
    let opening = null;
    let delay = 250;
    let retryAt = 0;
    let reconnectTimer = null;
    let heartbeat = null;
    let subscription = null;
    let subscriptionId = null;
    let sequence = 0;
    let stateBundles = {};
    let authorization = null;
    let connected = false;
    const pending = new Map();
    const transport = {onState: null, onConnection: null, request, close, get connected() { return connected; }};
    function close() {
      authorization = null;
      subscription = null;
      connected = false;
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
      clearInterval(heartbeat);
      heartbeat = null;
      for (const item of pending.values()) item.reject(new Error("Connexion fermée."));
      pending.clear();
      socket?.close();
    }
    function open() {
      if (opening) return opening;
      if (connected && socket?.readyState === WebSocket.OPEN) return Promise.resolve(socket);
      if (Date.now() < retryAt) return Promise.reject(new Error("Reconnexion temporisée."));
      opening = new Promise((resolve, reject) => {
        const endpoint = new URL("/api/ws", location.href);
        endpoint.protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const connection = new WebSocket(endpoint);
        socket = connection;
        const deadline = setTimeout(() => { reject(new Error("Connexion temps réel trop lente.")); connection.close(); }, 5000);
        connection.addEventListener("open", () => {
          connection.send(JSON.stringify({type: "authenticate", headers: {Authorization: authorization}}));
        });
        function authenticated() {
          if (socket !== connection || connected) return;
          clearTimeout(deadline);
          delay = 250;
          retryAt = 0;
          opening = null;
          connected = true;
          transport.onConnection?.();
          heartbeat = setInterval(() => {
            if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: "ping"}));
          }, 10000);
          resolve(socket);
          socket.send(JSON.stringify({type: "visibility", active: !document.hidden}));
          if (subscription) request(subscription.path, subscription.options).then(async response => {
            transport.onState?.({status: response.status, body: await response.json()});
          }).catch(() => {});
        }
        connection.addEventListener("message", event => {
          if (socket !== connection) return;
          let message;
          try { message = JSON.parse(event.data); } catch { return; }
          if (message.type === "authenticated") { authenticated(); return; }
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
        connection.addEventListener("error", () => reject(new Error("Connexion temps réel indisponible.")));
        connection.addEventListener("close", () => {
          if (socket !== connection) { clearTimeout(deadline); reject(new Error("Connexion remplacée.")); return; }
          connected = false;
          transport.onConnection?.();
          clearTimeout(deadline);
          clearInterval(heartbeat);
          opening = null;
          reject(new Error("Connexion temps réel interrompue."));
          for (const item of pending.values()) item.reject(new Error("Connexion interrompue. Reconnexion automatique."));
          pending.clear();
          if (authorization && reconnectTimer === null) {
            const wait = Math.round(delay * (.8 + Math.random() * .4));
            retryAt = Date.now() + wait;
            reconnectTimer = setTimeout(() => {
              reconnectTimer = null;
              if (authorization) open().catch(() => {});
            }, wait);
            delay = Math.min(30000, delay * 2);
          }
        });
      });
      return opening;
    }
    async function request(path, options = {}) {
      const credentials = options.headers?.Authorization || options.headers?.authorization;
      if (path.startsWith("/api/account/") || path === "/api/classes" || !credentials) return fetch(path, options);
      if (authorization && authorization !== credentials) {
        connected = false;
        clearInterval(heartbeat);
        subscription = null;
        socket?.close();
        socket = null;
        opening = null;
      }
      authorization = credentials;
      let connection;
      try { connection = await open(); }
      catch {
        opening = null;
        if (Date.now() >= retryAt) {
          retryAt = Date.now() + Math.round(delay * (.8 + Math.random() * .4));
          delay = Math.min(30000, delay * 2);
        }
        return fetch(path, options);
      }
      const id = String(++sequence);
      if (path === "/api/state") {
        subscription = {path, options};
        subscriptionId = id;
        stateBundles = {};
      }
      let result;
      try { result = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { pending.delete(id); reject(new Error("Réponse temps réel trop lente.")); }, 15000);
        pending.set(id, {resolve: value => {clearTimeout(timer); resolve(value);}, reject: error => {clearTimeout(timer); reject(error);}});
        try { connection.send(JSON.stringify({id, path, method: options.method || "GET", headers: options.headers || {}, body: options.body ? JSON.parse(options.body) : null})); }
        catch (error) { pending.get(id).reject(error); pending.delete(id); }
      }); }
      catch (error) {
        const body = options.body ? JSON.parse(options.body) : null;
        if ((!options.method || options.method === "GET") || path === "/api/commands" && typeof body?.request_id === "string") return fetch(path, options);
        throw error;
      }
      return {ok: result.status >= 200 && result.status < 300, status: result.status, json: async () => result.body};
    }
    document.addEventListener("visibilitychange", () => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: "visibility", active: !document.hidden}));
    });
    return transport;
  })();
}
