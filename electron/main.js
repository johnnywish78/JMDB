"use strict";
/** JMDB Electron main process.
 *
 * Owns: application window, the Python backend process, the Browser Hub
 * (WebContentsView tabs), downloads, permissions, context menus, external
 * browser handling, and the strict preload bridge. The renderer is plain
 * same-origin web content served by the backend — it never sees Node.
 */
const { app, BrowserWindow, ipcMain, session, nativeTheme } = require("electron");
const path = require("node:path");
const { URL } = require("node:url");

const { BackendProcess } = require("./main/backend");
const { Hub } = require("./main/hub");
const { DownloadManager } = require("./main/downloads");
const { PermissionManager } = require("./main/permissions");
const { buildContextMenu } = require("./main/context-menu");
const { ExternalBrowser } = require("./main/external");

app.setName("JMDB");

const isDev = !app.isPackaged;

/** @type {BrowserWindow} */
let mainWindow = null;
/** @type {BackendProcess} */
let backend = null;
/** @type {Hub} */
let hub = null;
/** @type {DownloadManager} */
let downloads = null;
/** @type {PermissionManager} */
let permissions = null;
let quitting = false;

// ----------------------------------------------------------------------------
// single instance lock
// ----------------------------------------------------------------------------
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// ----------------------------------------------------------------------------
// security hygiene
// ----------------------------------------------------------------------------
function hardenSession(thesession) {
  thesession.setPermissionRequestHandler((wc, permission, callback) => {
    permissions.handle(wc, permission, callback);
  });
  // no remote origins may frame us / be framed by the app UI
  thesession.webRequest.onHeadersReceived((details, callback) => {
    callback({ responseHeaders: details.responseHeaders });
  });
}

// ----------------------------------------------------------------------------
// window + boot
// ----------------------------------------------------------------------------
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    backgroundColor: "#0c0e13",
    title: "JMDB",
    show: false,
    autoHideMenuBar: true,
    icon: path.join(__dirname, "src", "assets", "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // the app UI itself never opens windows; anything unexpected goes to a hub tab
    if (url.startsWith("http://") || url.startsWith("https://")) {
      hub.createTab(url);
    }
    return { action: "deny" };
  });
  mainWindow.webContents.on("context-menu", (event, params) => {
    if (params.inputFieldType === "plainPassword" || params.isEditable) return;
    buildContextMenu(
      mainWindow.webContents,
      params,
      {
        back: () => mainWindow.webContents.navigationHistory.goBack(),
        forward: () => mainWindow.webContents.navigationHistory.goForward(),
        reload: () => mainWindow.webContents.reload(),
        openExternal: (url) => ExternalBrowser.open(url),
        openTab: (url) => hub.createTab(url),
        devtools: isDev,
      },
      { appUi: true }
    ).popup();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function showErrorPage(message, hint) {
  if (!mainWindow) return;
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>JMDB — backend error</title>
  <style>
    body{font-family:system-ui;background:#0c0e13;color:#e8eaf0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
    .box{max-width:560px;text-align:center}h1{color:#ffb454}p{color:#9aa3b5;line-height:1.6}
    code{background:#161a22;padding:2px 6px;border-radius:4px}
    button{margin-top:18px;background:#ffb454;border:0;color:#1a1206;padding:10px 22px;border-radius:8px;font-size:15px;cursor:pointer}
  </style></head><body><div class="box">
  <h1>JMDB couldn't reach its backend</h1>
  <p>${message}</p>
  <p>${hint || ""}</p>
  <button onclick="location.reload()">Retry</button>
  </div></body></html>`;
  mainWindow.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(html));
}

async function boot() {
  backend = new BackendProcess();

  let info;
  try {
    info = await backend.start();
  } catch (error) {
    createWindow();
    showErrorPage(
      `The local Python backend failed to start:<br><code>${String(error.message || error)
        .replace(/</g, "&lt;")}</code>`,
      "Check that Python 3.10+ with the project dependencies is available."
    );
    return;
  }

  hardenSession(session.fromPartition("persist:jmdb"));
  permissions = new PermissionManager(mainWindow);
  downloads = new DownloadManager(mainWindow);
  hub = new Hub({
    window: () => mainWindow,
    onExternal: (url) => ExternalBrowser.open(url),
  });

  createWindow();

  const bootUrl = new URL("/app/boot", info.url);
  bootUrl.searchParams.set("token", info.token);
  mainWindow.loadURL(bootUrl.toString()).catch((error) => {
    showErrorPage(`Renderer failed to load: ${error.message}`, info.url);
  });

  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow.webContents.executeJavaScript(
      `window.__JMDB_BOOT__ = { url: ${JSON.stringify(info.url)} }; true`
    ).catch(() => {});
  });

  if (isDev) {
    mainWindow.webContents.once("dom-ready", () => {
      // devtools available via context menu in dev builds only
    });
  }
}

// ----------------------------------------------------------------------------
// IPC surface (everything the renderer may ask the OS for)
// ----------------------------------------------------------------------------
function registerIpc() {
  ipcMain.handle("app:info", () => ({
    version: app.getVersion(),
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
    platform: process.platform,
    packaged: app.isPackaged,
    backendUrl: backend ? backend.url : null,
    externalBrowsers: ExternalBrowser.list(),
  }));

  ipcMain.handle("open-external", (_event, url) => {
    if (typeof url !== "string") return { ok: false };
    if (!/^https?:\/\//i.test(url)) return { ok: false };
    return ExternalBrowser.open(url);
  });

  ipcMain.handle("hub:createTab", (_e, url) => hub.createTab(url));
  ipcMain.handle("hub:closeTab", (_e, id) => hub.closeTab(id));
  ipcMain.handle("hub:activateTab", (_e, id) => hub.activateTab(id));
  ipcMain.handle("hub:navigate", (_e, url) => hub.navigate(url));
  ipcMain.handle("hub:back", () => hub.back());
  ipcMain.handle("hub:forward", () => hub.forward());
  ipcMain.handle("hub:reload", () => hub.reload());
  ipcMain.handle("hub:stop", () => hub.stop());
  ipcMain.handle("hub:home", () => hub.home());
  ipcMain.handle("hub:find", (_e, text, opts) => hub.find(text, opts || {}));
  ipcMain.handle("hub:clearFind", () => hub.clearFind());
  ipcMain.handle("hub:zoom", (_e, direction) => hub.zoom(direction));
  ipcMain.handle("hub:reopenTab", () => hub.reopenTab());
  ipcMain.handle("hub:tabs", () => hub.tabSummaries());
  ipcMain.handle("hub:setBounds", (_e, rect) => hub.setBounds(rect));
  ipcMain.handle("hub:setVisible", (_e, visible) => hub.setVisible(visible));
  ipcMain.handle("hub:history", () => hub.recentHistory());
  ipcMain.handle("hub:clearHistory", () => hub.clearHistory());

  ipcMain.handle("downloads:list", () => downloads.list());
  ipcMain.handle("downloads:cancel", (_e, id) => downloads.cancel(id));
  ipcMain.handle("downloads:pause", (_e, id) => downloads.pause(id));
  ipcMain.handle("downloads:resume", (_e, id) => downloads.resume(id));
  ipcMain.handle("downloads:openInFolder", (_e, id) => downloads.openInFolder(id));

  ipcMain.handle("permissions:respond", (_e, payload) =>
    permissions.respondFromRenderer(payload)
  );
}

// ----------------------------------------------------------------------------
// lifecycle
// ----------------------------------------------------------------------------
app.whenReady().then(() => {
  registerIpc();
  nativeTheme.on("updated", () => {
    if (mainWindow) {
      mainWindow.webContents.send("native-theme-changed", {
        shouldUseDarkColors: nativeTheme.shouldUseDarkColors,
      });
    }
  });
  boot();
});

app.on("window-all-closed", () => {
  // Linux convention; we are a desktop app, keep it simple
  app.quit();
});

app.on("before-quit", (event) => {
  if (quitting) return;
  quitting = true;
  if (hub) hub.setVisible(false);
  if (backend) {
    event.preventDefault();
    backend
      .stop()
      .catch(() => {})
      .finally(() => app.exit(0));
  }
});

process.on("exit", () => {
  if (backend) backend.kill();
});
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (backend) backend.kill();
    app.quit();
  });
}
