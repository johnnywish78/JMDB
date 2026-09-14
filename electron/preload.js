const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jmdb', {
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  openDirectory: () => ipcRenderer.invoke('open-directory'),
  openFile: (options) => ipcRenderer.invoke('open-file', options)
});
