const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jmdb", {
  version: "0.1.0",

  backend: {
    getUrl: () => ipcRenderer.invoke("jmdb:backend-url")
  }
});
