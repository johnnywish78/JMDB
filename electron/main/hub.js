"use strict";
/** Browser Hub: multi-tab web browsing with WebContentsView (not the
 * deprecated BrowserView API). Each tab renders in its own WebContentsView
 * using the persistent "persist:jmdb" session partition, so site logins
 * survive restarts. Views are positioned over the renderer's #hub-content
 * element; the renderer reports its bounds.
 *
 * Honesty notes: view stacking covers the whole window; when the user is on
 * any other app page the renderer asks us to hide the views.
 */
const { app, WebContentsView } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { buildContextMenu } = require("./context-menu");
const { ExternalBrowser } = require("./external");
const { DRM_DOMAINS, isDrmHost, normalizeInput } = require("./url-utils");

const SESSION_FILE = () => path.join(app.getPath("userData"), "hub-session.json");
const HISTORY_FILE = () => path.join(app.getPath("userData"), "browser-history.json");

const DEFAULT_ZOOM = 1.0;

class Hub {
  constructor({ window, onExternal }) {
    this.getWindow = window;
    this.onExternal = onExternal;
    this.tabs = new Map(); // id -> { id, view, url, title, favicon, loading, zoom }
    this.activeId = null;
    this.closedStack = []; // for reopen (Ctrl+Shift+T)
    this.bounds = { x: 0, y: 0, width: 0, height: 0 };
    this.visible = false;
    this.nextId = 1;
    this.history = this.loadHistory();
    this.searchEngines = {
      duckduckgo: "https://duckduckgo.com/?q=",
      google: "https://www.google.com/search?q=",
      bing: "https://www.bing.com/search?q=",
      brave: "https://search.brave.com/search?q=",
      startpage: "https://www.startpage.com/sp/search?query=",
    };
    this.restoreSession();
  }

  // -- session & history persistence -----------------------------------------

  loadHistory() {
    try {
      return JSON.parse(fs.readFileSync(HISTORY_FILE(), "utf-8"));
    } catch {
      return [];
    }
  }

  saveHistory() {
    try {
      fs.writeFileSync(HISTORY_FILE(), JSON.stringify(this.history.slice(0, 5000)));
    } catch {
      /* best effort */
    }
  }

  addHistory(entry) {
    this.history.unshift(entry);
    if (this.history.length > 5000) this.history.length = 5000;
    this.saveHistory();
  }

  recentHistory(limit = 200) {
    return this.history.slice(0, limit);
  }

  clearHistory() {
    this.history = [];
    this.saveHistory();
  }

  saveSession() {
    const tabs = [...this.tabs.values()].map((tab) => ({ url: tab.url, title: tab.title }));
    try {
      fs.writeFileSync(SESSION_FILE(), JSON.stringify({ tabs }));
    } catch {
      /* best effort */
    }
  }

  restoreSession() {
    try {
      const data = JSON.parse(fs.readFileSync(SESSION_FILE(), "utf-8"));
      this._pendingRestore = Array.isArray(data.tabs) ? data.tabs.slice(0, 25) : [];
    } catch {
      this._pendingRestore = null;
    }
  }

  restoreIfPending() {
    if (this._pendingRestore) {
      for (const tab of this._pendingRestore) this.createTab(tab.url, { activate: false });
      if (this.tabs.size > 0) this.activateTab(this.tabs.keys().next().value);
      this._pendingRestore = null;
      return true;
    }
    return false;
  }

  // -- tab lifecycle ----------------------------------------------------------

  createTab(url = "https://duckduckgo.com", { activate = true } = {}) {
    const id = this.nextId++;
    const view = new WebContentsView({
      webPreferences: {
        session: this.session(),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        spellcheck: false,
      },
    });
    const tab = { id, view, url, title: "New tab", favicon: null, loading: true, zoom: DEFAULT_ZOOM };
    this.tabs.set(id, tab);

    const wc = view.webContents;
    wc.setAudioMuted(false);

    wc.setWindowOpenHandler(({ url: target }) => {
      if (/^https?:/i.test(target)) this.createTab(target);
      return { action: "deny" };
    });

    wc.on("did-start-loading", () => this.markTab(id, { loading: true }));
    wc.on("did-stop-loading", () => this.markTab(id, { loading: false }));
    wc.on("did-navigate", (_e, url) => {
      this.markTab(id, { url });
      try {
        const parsed = new URL(url);
        if (parsed.protocol === "http:" || parsed.protocol === "https:") {
          this.addHistory({ url, title: tab.title, at: Date.now() });
        }
        const drm = isDrmHost(parsed.hostname);
        this.send("hub:drm", { id, url, drm });
      } catch {
        /* non-standard url */
      }
      this.saveSession();
    });
    wc.on("did-navigate-in-page", (_e, url) => this.markTab(id, { url }));
    wc.on("page-title-updated", (_e, title) => this.markTab(id, { title }));
    wc.on("page-favicon-updated", (_e, icons) => {
      const icon = icons.length ? icons[icons.length - 1] : null;
      this.markTab(id, { favicon: icon });
    });
    wc.on("did-fail-load", (_e, code, description, url, isMainFrame) => {
      if (isMainFrame && code !== -3) this.send("hub:load-error", { id, code, description, url });
    });
    wc.on("render-process-gone", (_e, details) => {
      this.send("hub:crashed", { id, reason: details.reason });
      // never take the app down: show the crash in the tab strip, keep the tab
      this.markTab(id, { crashed: true });
    });
    wc.on("unresponsive", () => this.send("hub:unresponsive", { id }));
    wc.on("responsive", () => this.send("hub:responsive", { id }));
    wc.on("found-in-page", (_e, result) => this.send("hub:found-in-page", { id, ...result }));
    wc.on("zoom-changed", (_e, direction) => this.send("hub:zoom-changed", { id, direction }));

    wc.on("context-menu", (event, params) => {
      event.preventDefault();
      buildContextMenu(
        wc,
        params,
        {
          back: () => wc.navigationHistory.goBack(),
          forward: () => wc.navigationHistory.goForward(),
          reload: () => wc.reload(),
          openExternal: (target) => this.onExternal(target),
          openTab: (target) => this.createTab(target),
          devtools: !app.isPackaged,
        },
        { hub: true, tabId: id, hubActions: this }
      ).popup();
    });

    // keyboard shortcuts while web content has focus
    wc.on("before-input-event", (event, input) => {
      if (input.type !== "keyDown") return;
      const ctrl = input.control || input.meta;
      const key = (input.key || "").toLowerCase();
      let handled = true;
      if (ctrl && key === "t") this.createTab();
      else if (ctrl && key === "w") this.closeTab(this.activeId);
      else if (ctrl && input.shift && key === "t") this.reopenTab();
      else if (ctrl && key === "l") this.send("hub:focus-address");
      else if (ctrl && key === "r") this.reload();
      else if (ctrl && key === "f") this.send("hub:open-find");
      else if (ctrl && (key === "+" || key === "=")) this.zoom("in");
      else if (ctrl && key === "-") this.zoom("out");
      else if (ctrl && key === "0") this.zoom("reset");
      else if (ctrl && input.shift && key === "arrowleft") this.back();
      else if (ctrl && input.shift && key === "arrowright") this.forward();
      else if (key === "f5") this.reload();
      else if (key === "f12" && !app.isPackaged) wc.openDevTools({ mode: "detach" });
      else handled = false;
      if (handled) event.preventDefault();
    });

    const target = this.normalizeInput(url);
    wc.loadURL(target);
    if (activate) this.activateTab(id);
    else this.attachView(view, false);
    this.broadcastTabs();
    this.saveSession();
    return id;
  }

  session() {
    const { session } = require("electron");
    return session.fromPartition("persist:jmdb");
  }

  closeTab(id) {
    const tab = this.tabs.get(id);
    if (!tab) return;
    this.closedStack.push({ url: tab.url, title: tab.title });
    if (this.closedStack.length > 25) this.closedStack.shift();
    this.tabs.delete(id);
    const win = this.getWindow();
    if (win) win.contentView.removeChildView(tab.view);
    (tab.view.webContents || {}).destroy?.();
    tab.view.webContents?.close?.();
    if (this.tabs.size === 0) {
      this.createTab("https://duckduckgo.com");
      return;
    }
    if (this.activeId === id) {
      this.activateTab(this.tabs.keys().next().value);
    }
    this.broadcastTabs();
    this.saveSession();
  }

  reopenTab() {
    const last = this.closedStack.pop();
    if (last) this.createTab(last.url);
  }

  activateTab(id) {
    const tab = this.tabs.get(id);
    if (!tab) return;
    this.activeId = id;
    for (const other of this.tabs.values()) {
      this.attachView(other.view, other.id === id);
    }
    this.broadcastTabs();
    this.sendActiveState();
  }

  /** keep exactly the active view attached+visible; others detached */
  attachView(view, isActive) {
    const win = this.getWindow();
    if (!win) return;
    if (isActive) {
      win.contentView.addChildView(view);
      view.setBounds(this.bounds);
      view.setVisible(this.visible);
    } else {
      win.contentView.removeChildView(view);
    }
  }

  // -- navigation ---------------------------------------------------------

  normalizeInput(input) {
    const direct = normalizeInput(input, "https://duckduckgo.com");
    if (direct) return direct;
    return this.searchEngines.duckduckgo + encodeURIComponent(String(input).trim());
  }

  setEngine(name) {
    if (this.searchEngines[name]) this.searchEngines.current = name;
  }

  navigate(input) {
    const tab = this.tabs.get(this.activeId);
    if (!tab) return this.createTab(input);
    const target = this.normalizeInput(input);
    tab.view.webContents.loadURL(target);
  }

  back() {
    this.activeTab()?.view.webContents.navigationHistory.goBack();
  }
  forward() {
    this.activeTab()?.view.webContents.navigationHistory.goForward();
  }
  reload() {
    this.activeTab()?.view.webContents.reload();
  }
  stop() {
    this.activeTab()?.view.webContents.stop();
  }
  home() {
    this.navigate("https://duckduckgo.com");
  }

  // -- view placement ------------------------------------------------------

  setBounds(rect) {
    this.bounds = {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    };
    if (!this.visible) return;
    const tab = this.activeTab();
    if (tab) tab.view.setBounds(this.bounds);
  }

  setVisible(visible) {
    this.visible = Boolean(visible);
    for (const tab of this.tabs.values()) {
      if (tab.id === this.activeId) {
        tab.view.setVisible(this.visible);
        if (this.visible) tab.view.setBounds(this.bounds);
      } else {
        tab.view.setVisible(false);
      }
    }
  }

  // -- find / zoom ---------------------------------------------------------

  find(text, { forward = true, findNext = false } = {}) {
    const tab = this.activeTab();
    if (!tab || !text) return;
    tab.view.webContents.findInPage(text, { forward, findNext });
  }

  clearFind() {
    this.activeTab()?.view.webContents.stopFindInPage("clearSelection");
  }

  zoom(direction) {
    const tab = this.activeTab();
    if (!tab) return;
    const levels = [0.25, 0.33, 0.5, 0.67, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0];
    const current = tab.view.webContents.getZoomFactor();
    if (direction === "in") {
      const next = levels.find((level) => level > current + 0.001);
      tab.view.webContents.setZoomFactor(next || levels[levels.length - 1]);
    } else if (direction === "out") {
      const prev = [...levels].reverse().find((level) => level < current - 0.001);
      tab.view.webContents.setZoomFactor(prev || levels[0]);
    } else {
      tab.view.webContents.setZoomFactor(1.0);
    }
    this.sendActiveState();
  }

  // -- renderer plumbing ----------------------------------------------------

  activeTab() {
    return this.tabs.get(this.activeId);
  }

  markTab(id, patch) {
    const tab = this.tabs.get(id);
    if (!tab) return;
    Object.assign(tab, patch);
    this.broadcastTabs();
    if (id === this.activeId) this.sendActiveState();
  }

  tabSummaries() {
    return [...this.tabs.values()].map((tab) => ({
      id: tab.id,
      url: tab.url,
      title: tab.title,
      favicon: tab.favicon,
      loading: tab.loading,
      crashed: Boolean(tab.crashed),
      zoom: tab.view.webContents.getZoomFactor(),
    }));
  }

  sendActiveState() {
    const summary = this.tabSummaries().find((tab) => tab.id === this.activeId);
    if (summary) this.send("hub:tab-active", summary);
  }

  broadcastTabs() {
    this.send("hub:tabs", this.tabSummaries());
  }

  send(channel, payload) {
    const win = this.getWindow();
    if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
  }

  destroy() {
    for (const tab of this.tabs.values()) {
      try {
        this.getWindow()?.contentView.removeChildView(tab.view);
        tab.view.webContents.close();
      } catch {
        /* already gone */
      }
    }
    this.tabs.clear();
    this.saveSession();
  }
}

module.exports = { Hub };
