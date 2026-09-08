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
const FAVORITES_FILE = () => path.join(app.getPath("userData"), "hub-favorites.json");

const DEFAULT_ZOOM = 1.0;

class Hub {
  constructor({ window, onExternal, cookiesEnabled = true, javascriptEnabled = true, defaultZoom = DEFAULT_ZOOM }) {
    this.getWindow = window;
    this.onExternal = onExternal;
    this.tabs = new Map(); // id -> { id, view, url, title, favicon, loading, zoom, pinned }
    this.activeId = null;
    this.closedStack = []; // for reopen (Ctrl+Shift+T)
    this.bounds = { x: 0, y: 0, width: 0, height: 0 };
    this.visible = false;
    this.nextId = 1;
    this.history = this.loadHistory();
    this.favorites = this.loadFavorites();
    // Browser settings: main seeds them from the saved profile (so even the
    // tabs restored at startup honor them); the renderer can push changes
    // live afterwards. Cookie blocking applies to the whole hub session
    // immediately; the JavaScript flag applies to newly created tabs
    // (Chromium webPreferences are fixed per WebContentsView).
    this.defaultZoom = defaultZoom;
    this.cookiesEnabled = cookiesEnabled !== false;
    this.javascriptEnabled = javascriptEnabled !== false;
    this.applyCookiePolicy();
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

  clearHistory() {
    this.history = [];
    this.saveHistory();
  }

  /** history with optional substring filter (url or title), newest first */
  recentHistory(limitOrQuery = 200, maybeLimit) {
    const query = typeof limitOrQuery === "string" ? limitOrQuery.toLowerCase() : null;
    const limit = typeof limitOrQuery === "string" ? (maybeLimit ?? 100) : limitOrQuery;
    let entries = this.history;
    if (query) {
      entries = entries.filter(
        (entry) =>
          String(entry.url || "").toLowerCase().includes(query) ||
          String(entry.title || "").toLowerCase().includes(query)
      );
    }
    return entries.slice(0, limit);
  }

  // -- favorites (pinned tabs, JPNH-style) -------------------------------------

  loadFavorites() {
    try {
      const data = JSON.parse(fs.readFileSync(FAVORITES_FILE(), "utf-8"));
      return Array.isArray(data.favorites)
        ? data.favorites.filter((f) => f && typeof f.url === "string")
        : [];
    } catch {
      return [];
    }
  }

  saveFavorites() {
    try {
      fs.writeFileSync(
        FAVORITES_FILE(),
        JSON.stringify({ favorites: this.favorites.slice(0, 200) }, null, 2)
      );
    } catch {
      /* best effort */
    }
  }

  favoritesList() {
    return this.favorites.map((f) => ({ name: f.name || f.url, url: f.url, pinned: true }));
  }

  /** pin/unpin a tab; pinned tabs persist as favorites across restarts */
  togglePin(id) {
    const tab = this.tabs.get(id);
    if (!tab) return null;
    tab.pinned = !tab.pinned;
    if (tab.pinned) {
      if (!this.favorites.some((f) => f.url === tab.url)) {
        this.favorites.push({ name: tab.title || tab.url, url: tab.url });
      }
    } else {
      this.favorites = this.favorites.filter((f) => f.url !== tab.url);
    }
    this.saveFavorites();
    this.saveSession();
    this.broadcastTabs();
    return { id: tab.id, pinned: tab.pinned };
  }

  saveSession() {
    const tabs = [...this.tabs.values()].map((tab) => ({
      url: tab.url,
      title: tab.title,
      pinned: Boolean(tab.pinned),
    }));
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
        javascript: this.javascriptEnabled !== false,
      },
    });
    const tab = {
      id, view, url, title: "New tab", favicon: null, loading: true,
      zoom: this.defaultZoom, pinned: false,
    };
    this.tabs.set(id, tab);

    const wc = view.webContents;
    wc.setAudioMuted(false);
    if (this.defaultZoom !== DEFAULT_ZOOM) {
      try { wc.setZoomFactor(this.defaultZoom); } catch { /* pre-load zoom is best effort */ }
    }

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
    wc.on("page-title-updated", (_e, title) => {
      this.markTab(id, { title });
      // did-navigate records history with the PREVIOUS page's title (the new
      // one hasn't arrived yet); fix the entry up once the real title lands.
      const entry = this.history.find((item) => item.url === tab.url);
      if (entry && title) {
        entry.title = title;
        this.saveHistory();
      }
    });
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
      else if (ctrl && input.shift && key === "tab") this.switchTab(-1);
      else if (ctrl && key === "tab") this.switchTab(1);
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

  /** cycle tabs with wraparound (Ctrl+Tab / Ctrl+Shift+Tab) */
  switchTab(direction) {
    const ids = [...this.tabs.keys()];
    if (ids.length < 2) return;
    const idx = ids.indexOf(this.activeId);
    if (idx === -1) return;
    const next = (idx + (direction >= 0 ? 1 : -1) + ids.length) % ids.length;
    this.activateTab(ids[next]);
  }

  // -- print / pdf / data clearing (JPNH-parity hub actions) ------------------

  print() {
    this.activeTab()?.view.webContents.print({ printBackground: true });
  }

  async exportPdf() {
    const tab = this.activeTab();
    const win = this.getWindow();
    if (!tab || !win) return { ok: false, error: "no active tab" };
    try {
      const data = await tab.view.webContents.printToPDF({ printBackground: true, pageSize: "A4" });
      const { dialog } = require("electron");
      const { canceled, filePath } = await dialog.showSaveDialog(win, {
        defaultPath: `${(tab.title || "page").replace(/[^\w\s-]/g, "").trim() || "page"}.pdf`,
        filters: [{ name: "PDF", extensions: ["pdf"] }],
      });
      if (canceled || !filePath) return { ok: false, cancelled: true };
      fs.writeFileSync(filePath, data);
      return { ok: true, path: filePath };
    } catch (error) {
      return { ok: false, error: String(error?.message || error) };
    }
  }

  /** clear hub browsing data: cache / cookies / history. Only the hub's own
   * "persist:jmdb" partition is touched — app UI session stays intact. */
  async clearData(types = []) {
    const cleared = {};
    const list = Array.isArray(types) ? types : [];
    try {
      if (list.includes("cache")) {
        await this.session().clearCache();
        cleared.cache = true;
      }
      if (list.includes("cookies")) {
        await this.session().clearStorageData({ storages: ["cookies", "localstorage", "indexdb", "serviceworkers", "cachestorage"] });
        cleared.cookies = true;
      }
      if (list.includes("history")) {
        this.clearHistory();
        cleared.history = true;
      }
    } catch (error) {
      return { ok: false, cleared, error: String(error?.message || error) };
    }
    return { ok: true, cleared };
  }

  /** Live cookie policy for the whole hub session. Blocking strips Cookie
   * request headers and Set-Cookie response headers — sites stop receiving
   * or storing cookies immediately (existing stored cookies stay until the
   * user clears browsing data, matching what browsers do). */
  setCookiesEnabled(enabled) {
    this.cookiesEnabled = enabled !== false;
    this.applyCookiePolicy();
    return { ok: true, cookiesEnabled: this.cookiesEnabled };
  }

  setJavaScriptEnabled(enabled) {
    this.javascriptEnabled = enabled !== false;
    return { ok: true, javascriptEnabled: this.javascriptEnabled, appliesTo: "new-tabs" };
  }

  applyCookiePolicy() {
    const strip = (headers, name) => {
      const cleaned = { ...headers };
      for (const key of Object.keys(cleaned)) {
        if (key.toLowerCase() === name) delete cleaned[key];
      }
      return cleaned;
    };
    const hubSession = this.session();
    hubSession.webRequest.onBeforeSendHeaders((details, callback) => {
      if (this.cookiesEnabled) return callback({ requestHeaders: details.requestHeaders });
      callback({ requestHeaders: strip(details.requestHeaders, "cookie") });
    });
    hubSession.webRequest.onHeadersReceived((details, callback) => {
      if (this.cookiesEnabled) return callback({ responseHeaders: details.responseHeaders });
      callback({ responseHeaders: strip(details.responseHeaders, "set-cookie") });
    });
  }

  setDefaultZoom(percent) {
    const factor = Math.min(3, Math.max(0.25, Number(percent) / 100));
    this.defaultZoom = Number.isFinite(factor) ? factor : DEFAULT_ZOOM;
    return this.defaultZoom;
  }

  /** true when the webContents belongs to a hub tab (used to route permission
   * requests to the in-page dialog instead of the native one) */
  isTabWebContents(wc) {
    if (!wc) return false;
    for (const tab of this.tabs.values()) {
      if (tab.view.webContents === wc) return true;
    }
    return false;
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
      pinned: Boolean(tab.pinned),
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
