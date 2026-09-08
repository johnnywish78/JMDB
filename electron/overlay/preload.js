"use strict";
/** Overlay preload — the ONLY bridge the control-bar overlay gets.
 * Commands go to the mpv engine in the main process; state arrives as
 * pushed events. Same sandboxed, context-isolated design as the app preload. */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ov", {
  command: (name, arg) => ipcRenderer.invoke("ov:cmd", name, arg),
  onState: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("ov:state", listener);
    return () => ipcRenderer.removeListener("ov:state", listener);
  },
  onControlsVisible: (callback) => {
    const listener = (_event, visible) => callback(visible);
    ipcRenderer.on("ov:controls-visible", listener);
    return () => ipcRenderer.removeListener("ov:controls-visible", listener);
  },
});
