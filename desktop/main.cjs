"use strict";
const {app, BrowserWindow, Menu, dialog, protocol, session} = require("electron");
const path = require("node:path");
const {APP_ORIGIN, createHandler} = require("./runtime.cjs");
app.setName("Jeux RPG");
// Keep the profile independent of the executable's name, location and build number.
app.setPath("userData", process.env.RPG_DESKTOP_DATA_DIR || path.join(app.getPath("appData"), "JeuxRPG"));
protocol.registerSchemesAsPrivileged([{scheme: "rpg", privileges: {standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, allowServiceWorkers: true}}]);
let window;
let closing = false;
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } });
  app.on("window-all-closed", () => app.quit());
  app.whenReady().then(async () => {
    const root = path.join(__dirname, "assets");
    const manifest = require("./assets/manifest.json");
    const profile = session.fromPartition("persist:jeux-rpg");
    profile.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
    profile.setPermissionCheckHandler(() => false);
    profile.on("will-download", event => event.preventDefault());
    profile.protocol.handle("rpg", createHandler({root, manifest, fetchOnline: (url, options) => profile.fetch(url, options)}));
    profile.webRequest.onBeforeRequest({urls: ["https://*/*", "http://*/*", "wss://*/*", "ws://*/*"]}, (details, callback) => {
      const url = new URL(details.url);
      const origin = url.protocol === "wss:" ? url.origin.replace("wss:", "https:") : url.origin;
      callback({cancel: origin !== manifest.server || !url.pathname.startsWith("/api/")});
    });
    // The desktop is an authenticated client of the existing public server.
    const websocket = manifest.server.replace("https:", "wss:") + "/api/ws";
    profile.webRequest.onBeforeSendHeaders({urls: [websocket]}, (details, callback) => {
      const headers = {...details.requestHeaders};
      for (const key of Object.keys(headers)) if (key.toLowerCase() === "origin") delete headers[key];
      headers.Origin = manifest.server;
      callback({requestHeaders: headers});
    });
    window = new BrowserWindow({
      title: "Jeux RPG", width: 1440, height: 960, minWidth: 900, minHeight: 650, show: false,
      backgroundColor: "#101820", autoHideMenuBar: true,
      webPreferences: {session: profile, sandbox: true, contextIsolation: true, nodeIntegration: false, nodeIntegrationInWorker: false, webSecurity: true, webviewTag: false},
    });
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      {label: "Jeu", submenu: [{label: "Recharger le client", role: "reload"}, {label: "Plein écran", role: "togglefullscreen"}, {type: "separator"}, {label: "Quitter", role: "quit"}]},
      {label: "Affichage", submenu: [{role: "resetZoom"}, {role: "zoomIn"}, {role: "zoomOut"}, {type: "separator"}, {label: "Outils de diagnostic", role: "toggleDevTools"}]},
    ]));
    window.webContents.setWindowOpenHandler(() => ({action: "deny"}));
    window.webContents.on("will-navigate", (event, url) => { if (url !== APP_ORIGIN + "/") event.preventDefault(); });
    window.on("ready-to-show", () => { if (process.env.RPG_DESKTOP_TEST !== "1") window.show(); });
    window.on("close", event => {
      if (closing) return;
      event.preventDefault();
      closing = true;
      const flush = window.webContents.executeJavaScript("typeof soloTransport !== 'undefined' && soloTransport ? soloTransport.flush() : Promise.resolve()").catch(() => {});
      Promise.race([flush, new Promise(resolve => setTimeout(resolve, 5000))]).finally(() => window.close());
    });
    await window.loadURL(APP_ORIGIN + "/");
  }).catch(error => { dialog.showErrorBox("Jeux RPG", "Impossible de démarrer le client : " + error.message); app.exit(1); });
}
