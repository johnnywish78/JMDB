/**
 * JMDB Electron — Preload Script
 *
 * Exposes a minimal, secure IPC bridge to the renderer process.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jmdb', {
  // Window controls
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),

  // External URLs
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),

  // File dialogs
  openFile: (opts) => ipcRenderer.invoke('dialog:openFile', opts),
  openDirectory: (opts) => ipcRenderer.invoke('dialog:openDirectory', opts),

  // Backend
  startBackend: () => ipcRenderer.invoke('backend:start'),
  stopBackend: () => ipcRenderer.invoke('backend:stop'),

  // API calls
  api: {
    get: (endpoint) => ipcRenderer.invoke('api:request', 'GET', endpoint),
    post: (endpoint, body) => ipcRenderer.invoke('api:request', 'POST', endpoint, body),
    patch: (endpoint, body) => ipcRenderer.invoke('api:request', 'PATCH', endpoint, body),
    put: (endpoint, body) => ipcRenderer.invoke('api:request', 'PUT', endpoint, body),
    delete: (endpoint) => ipcRenderer.invoke('api:request', 'DELETE', endpoint),
  },

  // Navigation (for renderer SPA routing)
  navigate: (page) => ipcRenderer.send('nav:navigate', page),

  // Play media
  playMedia: (payload) => ipcRenderer.send('play:payload', payload),

  // Playback controls
  playbackStart: (payload) => ipcRenderer.invoke('api:request', 'POST', '/api/playback/start', payload),
  playbackProgress: (position_s, duration_s) => ipcRenderer.invoke('api:request', 'POST', '/api/playback/progress', { position_s, duration_s }),
  playbackStop: (position_s, duration_s) => ipcRenderer.invoke('api:request', 'POST', '/api/playback/stop', { position_s, duration_s }),
  playbackFinish: () => ipcRenderer.invoke('api:request', 'POST', '/api/playback/finish', {}),
  playbackGetProgress: (media_key) => ipcRenderer.invoke('api:request', 'GET', `/api/playback/${media_key}`),
});
