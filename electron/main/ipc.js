"use strict";
/** Shared IPC surface registration — the single place that maps renderer
 * bridge calls (preload.js) to the real manager instances.
 *
 * Both the real main process (main.js) and the smoke harness (smoke.js) own
 * instances of the same managers; registering the surface through this module
 * guarantees the renderer sees the identical IPC handlers in both. That is
 * what makes "hub:setVisible → No handler registered" impossible in smoke
 * runs while keeping exactly one definition of the surface.
 *
 * deps:
 *   hub        Browser Hub instance (required)
 *   downloads  DownloadManager instance (required)
 *   permissions PermissionManager instance (required)
 *   vault      PasswordVault instance (Browser Hub password manager)
 *   backend    BackendProcess instance or null (app:info reports its URL)
 *   getWindow  () => BrowserWindow | null (dialog parenting)
 */
const { app, dialog, ipcMain } = require("electron");
const { ExternalBrowser } = require("./external");

function registerIpc({ hub, downloads, permissions, vault = null, backend = null, getWindow, mpv = null }) {
  if (!hub || !downloads || !permissions) {
    throw new Error("registerIpc: hub, downloads and permissions instances are required");
  }

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

  // native folder picker for "Add location" (cancel → null, never a fake path)
  ipcMain.handle("dialog:pickFolder", async () => {
    const result = await dialog.showOpenDialog(getWindow(), {
      title: "Choose a media folder",
      properties: ["openDirectory", "createDirectory"],
    });
    if (result.canceled || !result.filePaths.length) return null;
    return result.filePaths[0];
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
  ipcMain.handle("hub:history", (_e, query) => hub.recentHistory(query));
  ipcMain.handle("hub:clearHistory", () => hub.clearHistory());
  ipcMain.handle("hub:togglePin", (_e, id) => hub.togglePin(id));
  ipcMain.handle("hub:favorites", () => hub.favoritesList());
  ipcMain.handle("hub:switchTab", (_e, direction) => hub.switchTab(direction));
  ipcMain.handle("hub:print", () => hub.print());
  ipcMain.handle("hub:exportPdf", () => hub.exportPdf());
  ipcMain.handle("hub:clearData", (_e, types) => hub.clearData(types));
  ipcMain.handle("hub:setDefaultZoom", (_e, percent) => hub.setDefaultZoom(percent));
  ipcMain.handle("hub:setCookiesEnabled", (_e, enabled) => hub.setCookiesEnabled(enabled));
  ipcMain.handle("hub:setJavaScriptEnabled", (_e, enabled) => hub.setJavaScriptEnabled(enabled));

  ipcMain.handle("downloads:list", () => downloads.list());
  ipcMain.handle("downloads:cancel", (_e, id) => downloads.cancel(id));
  ipcMain.handle("downloads:pause", (_e, id) => downloads.pause(id));
  ipcMain.handle("downloads:resume", (_e, id) => downloads.resume(id));
  ipcMain.handle("downloads:openInFolder", (_e, id) => downloads.openInFolder(id));

  // ---- embedded mpv engine (optional: null in smoke/legacy contexts) ------
  ipcMain.handle("mpv:status", () => (mpv ? mpv.status() : Promise.resolve({ available: false, reason: "the mpv engine only exists in the full desktop app" })));
  ipcMain.handle("mpv:open", (_e, payload) => (mpv ? mpv.open(payload || {}) : Promise.resolve({ ok: false, error: "mpv engine unavailable" })));
  ipcMain.handle("mpv:close", () => (mpv ? mpv.close() : Promise.resolve({ ok: false })));
  // overlay window → engine commands
  ipcMain.handle("ov:cmd", (_e, name, arg) => (mpv ? mpv.command(name, arg) : Promise.resolve({ ok: false, error: "engine not running" })));

  ipcMain.handle("permissions:respond", (_e, payload) =>
    permissions.respondFromRenderer(payload)
  );

  if (vault) {
    // Password vault: the renderer gets structured entries WITHOUT secrets;
    // secrets only move on an explicit reveal/copy of a single entry.
    ipcMain.handle("passwords:list", () => ({ ok: true, backend: vault.backendName(), entries: vault.list() }));
    ipcMain.handle("passwords:add", (_e, entry) => vault.add(entry || {}));
    ipcMain.handle("passwords:update", (_e, id, fields) => vault.update(id, fields || {}));
    ipcMain.handle("passwords:remove", (_e, id) => vault.remove(id));
    ipcMain.handle("passwords:reveal", (_e, id) => vault.reveal(id));
    ipcMain.handle("passwords:copy", (_e, id) => vault.copy(id));
  }
}

module.exports = { registerIpc };
