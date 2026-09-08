"use strict";
/** Downloads manager: intercepts session downloads, stores them under
 * ~/Downloads/JMDB, and streams progress to the renderer. */
const { app, shell } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { uniquePath } = require("./url-utils");

class DownloadManager {
  constructor(window) {
    this.getWindow = () => window;
    this.items = new Map();
    this.nextId = 1;
    const { session } = require("electron");
    session.fromPartition("persist:jmdb").on("will-download", (event, item, webContents) => {
      this.track(item, webContents);
    });
  }

  downloadsDir() {
    const dir = path.join(app.getPath("downloads"), "JMDB");
    try {
      fs.mkdirSync(dir, { recursive: true });
    } catch {
      /* fall back to default */
    }
    return dir;
  }

  track(item) {
    const id = this.nextId++;
    const dir = this.downloadsDir();
    const target = uniquePath(dir, item.getFilename());
    item.setSavePath(target);

    const record = {
      id,
      filename: path.basename(target),
      path: target,
      url: item.getURL(),
      total: item.getTotalBytes(),
      received: 0,
      state: "progressing",
      startedAt: Date.now(),
      mimeType: item.getMimeType(),
    };
    this.items.set(id, record);

    // real control handles — the UI's Pause/Resume/Cancel buttons call
    // these; without them the buttons would do nothing (fake controls)
    record.pause = () => item.pause?.();
    record.resume = () => item.resume?.();
    record.cancel = () => item.cancel?.();

    item.on("updated", (_event, state) => {
      record.received = item.getReceivedBytes();
      record.state = state === "interrupted" ? "interrupted" : "progressing";
      record.paused = item.isPaused?.() || false;
      this.emit();
    });
    item.once("done", (_event, state) => {
      record.received = item.getReceivedBytes();
      record.state = state; // completed | cancelled | interrupted
      this.emit();
    });
    this.emit();
  }

  emit() {
    const win = this.getWindow();
    if (win && !win.isDestroyed()) {
      win.webContents.send("downloads:updated", this.list());
    }
  }

  list() {
    return [...this.items.values()].sort((a, b) => b.startedAt - a.startedAt).slice(0, 100);
  }

  cancel(id) {
    const record = this.items.get(id);
    if (record) {
      record.cancel?.();
      record.state = "cancelled";
      this.emit();
    }
  }

  pause(id) {
    this.items.get(id)?.pause?.();
  }

  resume(id) {
    this.items.get(id)?.resume?.();
  }

  openInFolder(id) {
    const record = this.items.get(id);
    if (record && record.state === "completed") {
      shell.showItemInFolder(record.path);
    }
  }
}

module.exports = { DownloadManager };
