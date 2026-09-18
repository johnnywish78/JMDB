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
