"use strict";
/** Preload bridge — the ONLY surface the renderer gets. contextIsolation is
 * on, nodeIntegration is off, the sandbox is enabled; this file exposes a
 * small, validated API. Renderer code never touches fs/child_process/shell. */
const { contextBridge, ipcRenderer } = require("electron");

const invoke = (channel, ...args) => ipcRenderer.invoke(channel, ...args);

const hubChannel = (channel) => (...args) => invoke(`hub:${channel}`, ...args);

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
  },

  downloads: {
    list: hubChannel("list"),
    cancel: (id) => invoke("downloads:cancel", id),
    pause: (id) => invoke("downloads:pause", id),
    resume: (id) => invoke("downloads:resume", id),
    openInFolder: (id) => invoke("downloads:openInFolder", id),
  },

  permissions: {
    respond: (payload) => invoke("permissions:respond", payload),
  },

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
    ];
    if (!allowed.includes(channel)) return () => {};
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on(channel, listener);
    return () => ipcRenderer.removeListener(channel, listener);
  },
});
