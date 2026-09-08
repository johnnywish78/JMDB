"use strict";
/** JMDB Electron main process.
 *
 * Owns: application window, the Python backend process, the Browser Hub
 * (WebContentsView tabs), downloads, permissions, context menus, external
 * browser handling, and the strict preload bridge. The renderer is plain
 * same-origin web content served by the backend — it never sees Node.
 */
const { app, BrowserWindow, clipboard, dialog, ipcMain, nativeTheme, safeStorage, session } = require("electron");
const path = require("node:path");
const { URL } = require("node:url");

const { BackendProcess } = require("./main/backend");
const { Hub } = require("./main/hub");
const { DownloadManager } = require("./main/downloads");
const { PermissionManager } = require("./main/permissions");
const { buildContextMenu } = require("./main/context-menu");
const { ExternalBrowser } = require("./main/external");
const { PasswordVault } = require("./main/passwords");
const { registerIpc } = require("./main/ipc");

/** Matches the backend's browser_default_zoom default (percent). */
const DEFAULT_ZOOM_PERCENT = 100;

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
/** @type {PasswordVault} */
let vault = null;
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
  vault = new PasswordVault({
    app, safeStorage, clipboard,
    log: (message) => console.log(message),
  });
  // seed the Hub with the saved browser settings so even session-restored
  // tabs honor them (JavaScript is fixed per WebContentsView at creation)
  let browserSettings = {};
  try {
    const response = await fetch(new URL("/api/settings", info.url), {
      headers: { Authorization: `Bearer ${info.token}` },
    });
    if (response.ok) browserSettings = (await response.json()).values || {};
  } catch {
    /* defaults are fine; the renderer pushes settings on hub mount anyway */
  }
  hub = new Hub({
    window: () => mainWindow,
    onExternal: (url) => ExternalBrowser.open(url),
    cookiesEnabled: browserSettings.browser_allow_cookies !== false,
    javascriptEnabled: browserSettings.browser_enable_javascript !== false,
    defaultZoom: Number(browserSettings.browser_default_zoom) || DEFAULT_ZOOM_PERCENT,
  });

  // hub-tab permission requests surface as the in-page JPNH-style dialog
  permissions.setHubLookup((wc) => hub != null && hub.isTabWebContents(wc));

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
// lifecycle
// ----------------------------------------------------------------------------
app.whenReady().then(() => {
  // the shared registration in main/ipc.js maps every preload bridge call to
  // this process's real manager instances
  registerIpc({
    hub,
    downloads,
    permissions,
    backend,
    vault,
    getWindow: () => mainWindow,
  });
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
