"use strict";
/** Per-site permissions, persisted to userData/permissions.json.
 * Unknown requests trigger a native dialog (Allow once / Always allow /
 * Block); decisions are remembered per origin. */
const { app, dialog } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { URL } = require("node:url");

const KNOWN = new Set([
  "media",
  "geolocation",
  "notifications",
  "fullscreen",
  "pointerLock",
  "openExternal",
  "clipboard-sanitized-write",
]);

function file() {
  return path.join(app.getPath("userData"), "permissions.json");
}

class PermissionManager {
  constructor(window) {
    this.getWindow = () => window;
    try {
      this.store = JSON.parse(fs.readFileSync(file(), "utf-8"));
    } catch {
      this.store = {};
    }
    // permissions asked via the renderer dialog (in-page permission requests)
    this.pending = new Map();
    this.nextAskId = 1;
    this.askTimeoutMs = 30000; // renderer must answer within this window
    // injected after the Hub exists: (webContents) => boolean
    this.hubLookup = () => false;
  }

  /** main wires this after creating the Hub (Hub is constructed later) */
  setHubLookup(fn) {
    this.hubLookup = fn || (() => false);
  }

  originFor(webContents) {
    try {
      return new URL(webContents.getURL()).origin;
    } catch {
      return "unknown";
    }
  }

  load() {
    try {
      this.store = JSON.parse(fs.readFileSync(file(), "utf-8"));
    } catch {
      this.store = {};
    }
  }

  persist() {
    try {
      fs.writeFileSync(file(), JSON.stringify(this.store, null, 2));
    } catch {
      /* best effort */
    }
  }

  /** permission request handler (site asks for mic/cam/geo/...)
   *
   * Hub tabs get the JPNH-style in-page dialog (the renderer banner answers
   * via permissions:respond); the app UI and any request the renderer fails
   * to answer in time fall back to the native dialog. */
  async handle(webContents, permission, callback) {
    const normalized = permission.split("-")[0];
    if (!KNOWN.has(permission) && !KNOWN.has(normalized)) {
      callback(false);
      return;
    }
    const origin = this.originFor(webContents);
    const key = `${origin}|${normalized}`;
    if (key in this.store) {
      callback(this.store[key]);
      return;
    }
    const labels = {
      media: "use your camera and microphone",
      geolocation: "know your location",
      notifications: "show notifications",
      fullscreen: "go fullscreen",
      pointerLock: "lock your mouse pointer",
      openExternal: "open links in other applications",
    };
    const what = labels[normalized] || `use “${permission}”`;

    if (this.hubLookup(webContents)) {
      this.askRenderer({
        id: this.nextAskId++,
        origin,
        permission: normalized,
        message: `${origin} wants to ${what}`,
      }, callback, { key, what, origin, permission: normalized });
      return;
    }
    await this.askNative(origin, what, callback, key);
  }

  async askNative(origin, what, callback, key) {
    const win = this.getWindow();
    const { response } = await dialog.showMessageBox(win, {
      type: "question",
      title: "JMDB — permission request",
      message: `${origin} wants to ${what}`,
      detail: "You can change this later in the Browser Hub.",
      buttons: ["Allow once", "Always allow", "Block"],
      defaultId: 0,
      cancelId: 2,
    });
    if (response === 1) {
      this.store[key] = true;
      this.persist();
      callback(true);
    } else if (response === 0) {
      callback(true);
    } else {
      callback(false);
    }
  }

  /** renderer-facing API for the settings page */
  list() {
    const entries = [];
    for (const [key, value] of Object.entries(this.store)) {
      const [origin, permission] = key.split("|");
      entries.push({ origin, permission, allowed: value });
    }
    return entries;
  }

  set(origin, permission, allowed) {
    this.store[`${origin}|${permission}`] = Boolean(allowed);
    this.persist();
  }

  clear(origin, permission) {
    delete this.store[`${origin}|${permission}`];
    this.persist();
  }

  /** surface the ask in the renderer; if it doesn't answer in 30s (page
   * not open / renderer hung), fall back to the native dialog. */
  askRenderer(payload, callback, native) {
    const win = this.getWindow();
    if (!win || win.isDestroyed()) {
      this.askNative(native.origin, native.what, callback, native.key);
      return;
    }
    const entry = {
      callback,
      native,
      timer: setTimeout(() => {
        this.pending.delete(payload.id);
        this.askNative(native.origin, native.what, callback, native.key);
      }, this.askTimeoutMs),
    };
    this.pending.set(payload.id, entry);
    win.webContents.send("permissions:asked", payload);
  }

  /** renderer answered the in-page dialog: {id, allowed, remember?} */
  respondFromRenderer({ id, allowed, remember, origin, permission }) {
    if (id != null && this.pending.has(id)) {
      const entry = this.pending.get(id);
      clearTimeout(entry.timer);
      this.pending.delete(id);
      if (remember) {
        this.set(entry.native.origin, entry.native.permission, Boolean(allowed));
      }
      entry.callback(Boolean(allowed));
      return;
    }
    // legacy shape (settings page): persist a standing decision
    if (origin && permission) {
      this.set(origin, permission, Boolean(allowed));
    }
  }
}

module.exports = { PermissionManager };
