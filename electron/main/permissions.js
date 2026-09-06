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
    // permissions asked via the renderer banner (in-page permission requests)
    this.pending = new Map();
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

  /** native permission request handler (site asks for mic/cam/geo/...) */
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

  /** in-page HTML5 permission requests surface in the hub as a banner */
  askRenderer(payload) {
    const win = this.getWindow();
    if (win && !win.isDestroyed()) {
      win.webContents.send("permissions:asked", payload);
    }
  }

  respondFromRenderer({ origin, permission, allowed }) {
    this.set(origin, permission, allowed);
    const pending = this.pending.get(`${origin}|${permission}`);
    if (pending) {
      pending(allowed);
      this.pending.delete(`${origin}|${permission}`);
    }
  }
}

module.exports = { PermissionManager };
