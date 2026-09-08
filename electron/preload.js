"use strict";
/** Preload bridge — the ONLY surface the renderer gets. contextIsolation is
 * on, nodeIntegration is off, the sandbox is enabled; this file exposes a
 * small, validated API. Renderer code never touches fs/child_process/shell. */
const { contextBridge, ipcRenderer } = require("electron");

const invoke = (channel, ...args) => ipcRenderer.invoke(channel, ...args);

const hubChannel = (channel) => (...args) => invoke(`hub:${channel}`, ...args);

/** The renderer runs with the same environment as the main process. The
 * smoke harness (electron/smoke.js) sets JMDB_SMOKE=1 before creating the
 * window; the renderer pings the one-shot smoke:renderer-ready handler after
 * its first real page render. Normal runs never see this surface. */
const smokeMode = process.env.JMDB_SMOKE === "1";

contextBridge.exposeInMainWorld("jmdb", {
  platform: "electron",
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  },

  app: {
    info: () => invoke("app:info"),
    quit: () => ipcRenderer.send("app:quit"),
  },

  external: {
    open: (url) => invoke("open-external", url),
  },

  dialog: {
    pickFolder: () => invoke("dialog:pickFolder"),
  },

  hub: {
    createTab: hubChannel("createTab"),
    closeTab: hubChannel("closeTab"),
    activateTab: hubChannel("activateTab"),
    navigate: hubChannel("navigate"),
    back: hubChannel("back"),
    forward: hubChannel("forward"),
    reload: hubChannel("reload"),
    stop: hubChannel("stop"),
    home: hubChannel("home"),
    find: hubChannel("find"),
    clearFind: hubChannel("clearFind"),
    zoom: hubChannel("zoom"),
    reopenTab: hubChannel("reopenTab"),
    tabs: hubChannel("tabs"),
    setBounds: hubChannel("setBounds"),
    setVisible: hubChannel("setVisible"),
    history: hubChannel("history"),
    clearHistory: hubChannel("clearHistory"),
    togglePin: hubChannel("togglePin"),
    favorites: hubChannel("favorites"),
    switchTab: hubChannel("switchTab"),
    print: hubChannel("print"),
    exportPdf: hubChannel("exportPdf"),
    clearData: hubChannel("clearData"),
    setDefaultZoom: hubChannel("setDefaultZoom"),
    setCookiesEnabled: hubChannel("setCookiesEnabled"),
    setJavaScriptEnabled: hubChannel("setJavaScriptEnabled"),
  },

  downloads: {
    list: () => invoke("downloads:list"),
    cancel: (id) => invoke("downloads:cancel", id),
    pause: (id) => invoke("downloads:pause", id),
    resume: (id) => invoke("downloads:resume", id),
    openInFolder: (id) => invoke("downloads:openInFolder", id),
  },

  // embedded multi-codec mpv engine (desktop app only)
  mpv: {
    status: () => invoke("mpv:status"),
    open: (payload) => invoke("mpv:open", payload),
    close: () => invoke("mpv:close"),
  },

  permissions: {
    respond: (payload) => invoke("permissions:respond", payload),
  },

  passwords: {
    list: () => invoke("passwords:list"),
    add: (entry) => invoke("passwords:add", entry),
    update: (id, fields) => invoke("passwords:update", id, fields),
    remove: (id) => invoke("passwords:remove", id),
    reveal: (id) => invoke("passwords:reveal", id),
    copy: (id) => invoke("passwords:copy", id),
  },

  ...(smokeMode ? {
    smoke: {
      ready: () => invoke("smoke:renderer-ready"),
    },
  } : {}),

  on: (channel, callback) => {
    const allowed = [
      "hub:tabs",
      "hub:tab-active",
      "hub:drm",
      "hub:load-error",
      "hub:crashed",
      "hub:unresponsive",
      "hub:responsive",
      "hub:found-in-page",
      "hub:zoom-changed",
      "hub:focus-address",
      "hub:open-find",
      "downloads:updated",
      "permissions:asked",
      "native-theme-changed",
      "mpv:closed",
      "mpv:next",
      "mpv:prev",
    ];
    if (!allowed.includes(channel)) return () => {};
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on(channel, listener);
    return () => ipcRenderer.removeListener(channel, listener);
  },
});
