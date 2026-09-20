const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jmdb', {
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  openDirectory: () => ipcRenderer.invoke('open-directory'),
  openFile: (options) => ipcRenderer.invoke('open-file', options),
  player: {
    start: (filePath, options = {}) =>
      ipcRenderer.invoke('player:start', filePath, options),

    command: (command) =>
      ipcRenderer.invoke('player:command', command),

    getProperty: (property) =>
      ipcRenderer.invoke('player:get-property', property),

    setProperty: (property, value) =>
      ipcRenderer.invoke('player:set-property', property, value),

    observeProperty: (property, observeId) =>
      ipcRenderer.invoke('player:observe-property', property, observeId),

    unobserveProperty: (observeId) =>
      ipcRenderer.invoke('player:unobserve-property', observeId),

    stop: () =>
      ipcRenderer.invoke('player:stop'),

    status: () =>
      ipcRenderer.invoke('player:status'),

    onEvent: (callback) => {
      if (typeof callback !== 'function') {
        throw new TypeError('player.onEvent requires a function');
      }

      const listener = (_event, message) => {
        callback(message);
      };

      ipcRenderer.on('player:event', listener);

      return () => {
        ipcRenderer.removeListener('player:event', listener);
      };
    }
  }
});

// Personal Hub-compatible Browser bridge.
// Kept separate from the existing JMDB/MPV bridge.
contextBridge.exposeInMainWorld("jpnh", {
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  openChrome: (url) => ipcRenderer.invoke("open-chrome", url),
  backendUrl: () => ipcRenderer.invoke("backend-url"),

  browser: {
    showContextMenu: (options) =>
      ipcRenderer.invoke("show-context-menu", options),

    download: (url) =>
      ipcRenderer.invoke("download-url", { url }),

    getDownloads: () =>
      ipcRenderer.invoke("get-downloads"),

    print: () =>
      ipcRenderer.invoke("print-page"),

    exportPdf: () =>
      ipcRenderer.invoke("export-pdf"),

    clearData: (types) =>
      ipcRenderer.invoke("clear-browser-data", { types }),

    getHistory: (query) =>
      ipcRenderer.invoke("get-history", { query }),

    addHistory: (url, title) =>
      ipcRenderer.invoke("add-history", { url, title }),

    clearHistory: () =>
      ipcRenderer.invoke("clear-history"),

    respondPermission: (id, granted) =>
      ipcRenderer.invoke("respond-permission", { id, granted }),
  },

  onDownloadStarted: (cb) =>
    ipcRenderer.on("download-started", (_, data) => cb(data)),

  onDownloadProgress: (cb) =>
    ipcRenderer.on("download-progress", (_, data) => cb(data)),

  onDownloadComplete: (cb) =>
    ipcRenderer.on("download-complete", (_, data) => cb(data)),

  onPermissionRequest: (cb) =>
    ipcRenderer.on("permission-request", (_, data) => cb(data)),

  onContextMenuAction: (cb) =>
    ipcRenderer.on("context-menu-action", (_, data) => cb(data)),

  onBrowserOpenInTab: (cb) =>
    ipcRenderer.on("browser-open-in-tab", (_, data) => cb(data)),
});
