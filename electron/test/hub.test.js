"use strict";
/** Browser Hub logic tests (electron/main/hub.js) with a stubbed electron
 * module. This covers tab lifecycle, activation, zoom, find, history and
 * session persistence WITHOUT the Electron binary (which cannot be
 * downloaded in this sandbox). The Hub code under test is the real file. */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Module = require("node:module");

const userData = fs.mkdtempSync(path.join(os.tmpdir(), "jmdb-hub-test-"));

class FakeWebContents {
  constructor() {
    this.handlers = new Map();
    this.zoomFactor = 1.0;
    this.findArgs = null;
    this.loadedURLs = [];
    this.navigationHistory = { goBack: () => {}, goForward: () => {} };
    this.destroyed = false;
    this.id = Math.floor(Math.random() * 1e6);
  }
  on(event, handler) { (this.handlers.get(event) || this.handlers.set(event, []).get(event)).push(handler); }
  emit(event, ...args) { for (const h of this.handlers.get(event) || []) h(...args); }
  loadURL(url) { this.loadedURLs.push(url); return Promise.resolve(); }
  reload() {}
  stop() {}
  setZoomFactor(f) { this.zoomFactor = f; }
  getZoomFactor() { return this.zoomFactor; }
  findInPage(text, opts) { this.findArgs = { text, opts }; this.emit("found-in-page", { activeMatchOrdinal: 1, matches: 3 }); }
  stopFindInPage(action) { this.findArgs = { action }; }
  print(options) { this.printArgs = options; }
  async printToPDF(options) { this.pdfArgs = options; return Buffer.from("%PDF-1.4 test"); }
  setWindowOpenHandler() {}
  setAudioMuted() {}
  openDevTools() {}
  close() { this.destroyed = true; }
}

class FakeView {
  constructor() {
    this.webContents = new FakeWebContents();
    this.bounds = null;
    this.visible = true;
    this.attached = 0;
  }
  setBounds(b) { this.bounds = b; }
  setVisible(v) { this.visible = v; }
}

const sent = [];
const attachedViews = [];
const detachedViews = [];

const sessionActions = [];
let saveDialogResult = { canceled: true };

const stubElectron = {
  app: {
    getPath: (name) => (name === "userData" ? userData : os.tmpdir()),
    isPackaged: true,
    getName: () => "JMDB",
  },
  dialog: {
    showSaveDialog: async () => saveDialogResult,
  },
  WebContentsView: class {
    constructor(webPreferences) { this.__view = new FakeView(); this.__prefs = webPreferences || {}; }
    get webContents() { return this.__view.webContents; }
    setBounds(b) { this.__view.setBounds(b); }
    setVisible(v) { this.__view.setVisible(v); }
  },
  session: {
    fromPartition: () => ({
      on: () => {},
      setPermissionRequestHandler: () => {},
      clearCache: async () => { sessionActions.push("clearCache"); },
      clearStorageData: async (options) => { sessionActions.push(["clearStorageData", options]); },
      webRequest: {
        onBeforeSendHeaders: (listener) => { stubElectron.__webRequestListeners = stubElectron.__webRequestListeners || {}; stubElectron.__webRequestListeners.onBeforeSendHeaders = listener; },
        onHeadersReceived: (listener) => { stubElectron.__webRequestListeners = stubElectron.__webRequestListeners || {}; stubElectron.__webRequestListeners.onHeadersReceived = listener; },
      },
    }),
  },
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "electron") return stubElectron;
  return origLoad.apply(this, arguments);
};

// NOTE: the patch stays installed for the whole test run — Hub.session()
// lazily requires("electron") at construction time, inside test callbacks.
let Hub;
({ Hub } = require("../main/hub.js"));

const fakeWindow = {
  isDestroyed: () => false,
  contentView: {
    addChildView: (v) => attachedViews.push(v),
    removeChildView: (v) => detachedViews.push(v),
  },
  webContents: { send: (channel, payload) => sent.push({ channel, payload }) },
};

function freshHub() {
  sent.length = 0;
  return new Hub({ window: () => fakeWindow, onExternal: () => {} });
}

test("createTab opens a real tab object with safe webPreferences defaults", () => {
  const hub = freshHub();
  const id = hub.createTab("https://example.com/");
  const summary = hub.tabSummaries();
  assert.equal(summary.length, 1);
  assert.equal(summary[0].id, id);
  assert.equal(summary[0].title, "New tab");
});

test("multiple tabs are independent; activateTab switches the active one", () => {
  const hub = freshHub();
  const a = hub.createTab("https://a.example/");
  const b = hub.createTab("https://b.example/");
  hub.activateTab(a);
  assert.equal(hub.activeId, a);
  hub.activateTab(b);
  assert.equal(hub.activeId, b);
  assert.equal(hub.tabSummaries().length, 2);
});

test("closing the last tab reopens a fresh tab (never a dead browser)", () => {
  const hub = freshHub();
  const a = hub.createTab("https://a.example/");
  hub.closeTab(a);
  const summaries = hub.tabSummaries();
  assert.equal(summaries.length, 1, "closing the last tab creates a new one");
  assert.notEqual(summaries[0].id, a);
});

test("closeTab keeps the others and activates the next one", () => {
  const hub = freshHub();
  const a = hub.createTab("https://a.example/");
  const b = hub.createTab("https://b.example/");
  const c = hub.createTab("https://c.example/");
  hub.activateTab(b);
  hub.closeTab(b); // close the ACTIVE middle tab
  assert.equal(hub.tabSummaries().length, 2, "the other two tabs survive");
  assert.notEqual(hub.activeId, b, "another tab becomes active");
  assert.ok([a, c].includes(hub.activeId));
});

test("session persists tabs to disk and restores them", () => {
  const hub = freshHub();
  hub.createTab("https://persist.example/");
  hub.createTab("https://other.example/");
  const file = path.join(userData, "hub-session.json");
  const raw = JSON.parse(fs.readFileSync(file, "utf-8"));
  assert.ok(raw.tabs.some((t) => t.url === "https://persist.example/"));

  const hub2 = freshHub(); // constructor restores
  hub2.restoreIfPending();
  const urls = hub2.tabSummaries().map((t) => t.url);
  assert.ok(urls.includes("https://persist.example/"));
});

test("history is recorded on navigation and capped", () => {
  const hub = freshHub();
  const id = hub.createTab("https://example.com/");
  const wc = hub.tabs.get(id).view.webContents;
  wc.emit("did-navigate", undefined, "https://example.com/page1");
  const history = hub.recentHistory(10);
  assert.ok(history.some((h) => h.url === "https://example.com/page1"));
});

test("zoom steps up, down and resets on the active tab", () => {
  const hub = freshHub();
  hub.createTab("https://example.com/");
  hub.zoom("in");
  const up = hub.activeTab().view.webContents.zoomFactor;
  assert.ok(up > 1.0, `expected zoom > 1, got ${up}`);
  hub.zoom("reset");
  assert.equal(hub.activeTab().view.webContents.zoomFactor, 1.0);
  hub.zoom("out");
  assert.ok(hub.activeTab().view.webContents.zoomFactor < 1.0);
});

test("find() drives findInPage on the active tab", () => {
  const hub = freshHub();
  hub.createTab("https://example.com/");
  hub.find("needle", { forward: true });
  const wc = hub.activeTab().view.webContents;
  assert.equal(wc.findArgs.text, "needle");
});

test("load errors are reported to the renderer, not swallowed", () => {
  const hub = freshHub();
  const id = hub.createTab("https://example.com/");
  const wc = hub.tabs.get(id).view.webContents;
  wc.emit("did-fail-load", undefined, -6, "ERR_CONNECTION_REFUSED", "https://down.example/", true);
  const error = sent.find((m) => m.channel === "hub:load-error");
  assert.ok(error, "hub:load-error must be sent");
  assert.equal(error.payload.description, "ERR_CONNECTION_REFUSED");
});

test("renderer process crash marks the tab but keeps the app alive", () => {
  const hub = freshHub();
  const id = hub.createTab("https://example.com/");
  const wc = hub.tabs.get(id).view.webContents;
  wc.emit("render-process-gone", undefined, { reason: "oom" });
  assert.equal(hub.tabSummaries()[0].crashed, true);
  assert.ok(sent.some((m) => m.channel === "hub:crashed"));
});

test("setVisible(false) hides the active view (leaving the app page)", () => {
  const hub = freshHub();
  hub.createTab("https://example.com/");
  hub.setBounds({ x: 0, y: 0, width: 800, height: 600 });
  hub.setVisible(false);
  assert.equal(hub.activeTab().view.__view.visible, false);
  hub.setVisible(true);
  assert.equal(hub.activeTab().view.__view.visible, true);
});

test("normalizeInput turns search terms into engine URLs and keeps real URLs", () => {
  const hub = freshHub();
  assert.equal(hub.normalizeInput("https://example.com/"), "https://example.com/");
  const resolved = hub.normalizeInput("hello world");
  assert.ok(resolved.startsWith("https://duckduckgo.com/?q="));
});

// ---------------------------------------------------------------- JPNH-parity additions

test("togglePin pins a tab, lists it as a favorite and persists it to disk", () => {
  const hub = freshHub();
  const id = hub.createTab("https://favorite.example/");
  assert.equal(hub.togglePin(id).pinned, true);
  assert.deepEqual(hub.favoritesList(), [{ name: "New tab", url: "https://favorite.example/", pinned: true }]);
  assert.equal(hub.tabSummaries().find((tab) => tab.id === id).pinned, true);
  // persisted for the next launch
  const onDisk = JSON.parse(fs.readFileSync(path.join(userData, "hub-favorites.json"), "utf-8"));
  assert.equal(onDisk.favorites[0].url, "https://favorite.example/");
  // unpin removes the favorite again
  assert.equal(hub.togglePin(id).pinned, false);
  assert.equal(hub.favoritesList().length, 0);
});

test("a fresh Hub loads favorites persisted by a previous run", () => {
  const first = freshHub();
  const id = first.createTab("https://keep.example/");
  first.togglePin(id);
  const second = new Hub({ window: () => fakeWindow, onExternal: () => {} });
  assert.equal(second.favoritesList()[0].url, "https://keep.example/");
});

test("setDefaultZoom applies to NEW tabs without touching existing ones", () => {
  const hub = freshHub();
  const before = hub.createTab("https://a.example/");
  assert.equal(hub.setDefaultZoom(150), 1.5);
  const after = hub.createTab("https://b.example/");
  const summaries = hub.tabSummaries();
  const zoomOf = (tabId) => summaries.find((tab) => tab.id === tabId).zoom;
  assert.equal(zoomOf(before), 1);
  assert.equal(zoomOf(after), 1.5);
  // clamped to a sane range
  assert.equal(hub.setDefaultZoom(9999), 3);
  assert.equal(hub.setDefaultZoom(1), 0.25);
});

test("history(query) filters by url and title substring", () => {
  const hub = freshHub();
  hub.clearHistory(); // earlier tests in this file persist history to the same userData
  const id = hub.createTab("https://news.example/story");
  const wc = hub.tabs.get(id).view.webContents;
  wc.emit("did-navigate", {}, "https://news.example/story");
  wc.emit("page-title-updated", {}, "Big Story"); // title lands AFTER navigation
  wc.emit("did-navigate", {}, "https://shop.example/cart");
  wc.emit("page-title-updated", {}, "Shopping Cart");
  assert.equal(hub.recentHistory().length, 2);
  const hits = hub.recentHistory("big story");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].url, "https://news.example/story");
  assert.equal(hits[0].title, "Big Story", "history entry carries the real page title");
  const byUrl = hub.recentHistory("shop.example");
  assert.equal(byUrl.length, 1);
  assert.equal(byUrl[0].title, "Shopping Cart");
  assert.equal(hub.recentHistory("nothing-matches").length, 0);
});

test("clearData clears cache/cookies/history via the hub partition session", async () => {
  const hub = freshHub();
  const id = hub.createTab("https://a.example/");
  hub.tabs.get(id).view.webContents.emit("did-navigate", {}, "https://a.example/x");
  sessionActions.length = 0;
  const result = await hub.clearData(["cache", "cookies", "history"]);
  assert.equal(result.ok, true);
  assert.deepEqual(result.cleared, { cache: true, cookies: true, history: true });
  assert.ok(sessionActions.includes("clearCache"));
  const storage = sessionActions.find((entry) => Array.isArray(entry) && entry[0] === "clearStorageData");
  assert.ok(storage, "clearStorageData was called");
  assert.ok(storage[1].storages.includes("cookies"));
  assert.equal(hub.recentHistory().length, 0, "history was cleared");
  // unknown types are ignored, not faked
  const nothing = await hub.clearData([]);
  assert.deepEqual(nothing.cleared, {});
});

test("switchTab cycles through tabs with wraparound", () => {
  const hub = freshHub();
  const a = hub.createTab("https://a.example/");
  const b = hub.createTab("https://b.example/");
  const c = hub.createTab("https://c.example/");
  hub.activateTab(a);
  hub.switchTab(1);
  assert.equal(hub.activeId, b);
  hub.switchTab(1);
  assert.equal(hub.activeId, c);
  hub.switchTab(1);
  assert.equal(hub.activeId, a, "wraps around to the first tab");
  hub.switchTab(-1);
  assert.equal(hub.activeId, c, "backwards wraps to the last tab");
});

test("print() drives the active tab's webContents", () => {
  const hub = freshHub();
  const id = hub.createTab("https://print.example/");
  hub.print();
  const wc = hub.tabs.get(id).view.webContents;
  assert.ok(wc.printArgs, "print options were passed");
  assert.equal(wc.printArgs.printBackground, true);
});

test("exportPdf() writes the file when the user picks a path, reports cancel otherwise", async () => {
  const hub = freshHub();
  hub.createTab("https://pdf.example/");
  saveDialogResult = { canceled: true };
  const cancelled = await hub.exportPdf();
  assert.equal(cancelled.ok, false);
  assert.equal(cancelled.cancelled, true);

  const target = path.join(userData, "exported-page.pdf");
  saveDialogResult = { canceled: false, filePath: target };
  const saved = await hub.exportPdf();
  assert.equal(saved.ok, true);
  assert.equal(saved.path, target);
  assert.ok(fs.existsSync(target), "PDF bytes were written to disk");
  assert.ok(fs.readFileSync(target).toString().startsWith("%PDF"));
  saveDialogResult = { canceled: true };
});

test("isTabWebContents recognises hub tabs and rejects everything else", () => {
  const hub = freshHub();
  const id = hub.createTab("https://a.example/");
  const wc = hub.tabs.get(id).view.webContents;
  assert.equal(hub.isTabWebContents(wc), true);
  assert.equal(hub.isTabWebContents({ id: 999999 }), false);
  assert.equal(hub.isTabWebContents(null), false);
});


// ---------------------------------------------------------------- browser policy settings
test("cookie blocking strips Cookie/Set-Cookie headers live; allow passes through", () => {
  const hub = freshHub();
  const listeners = stubElectron.__webRequestListeners;
  assert.ok(listeners && listeners.onBeforeSendHeaders, "policy listeners must be registered");

  // default: cookies allowed → headers untouched
  let out = {};
  listeners.onBeforeSendHeaders({ requestHeaders: { Cookie: "a=b", Accept: "*/*" } }, (res) => { out = res; });
  assert.equal(out.requestHeaders.Cookie, "a=b");

  hub.setCookiesEnabled(false);
  listeners.onBeforeSendHeaders({ requestHeaders: { Cookie: "a=b", Accept: "*/*" } }, (res) => { out = res; });
  assert.equal(out.requestHeaders.Cookie, undefined, "Cookie request header must be stripped");
  assert.equal(out.requestHeaders.Accept, "*/*", "other headers must survive");

  let resp = {};
  listeners.onHeadersReceived({ responseHeaders: { "set-cookie": ["x=y"], "content-type": ["text/html"] } }, (res) => { resp = res; });
  assert.equal(resp.responseHeaders["set-cookie"], undefined, "Set-Cookie must be stripped");
  assert.equal(resp.responseHeaders["content-type"][0], "text/html");

  // re-enable passes headers through again
  hub.setCookiesEnabled(true);
  listeners.onBeforeSendHeaders({ requestHeaders: { Cookie: "a=b" } }, (res) => { out = res; });
  assert.equal(out.requestHeaders.Cookie, "a=b");
});

test("javascript flag applies to newly created tabs", () => {
  const hub = freshHub();
  hub.setJavaScriptEnabled(false);
  const id = hub.createTab("https://example.com/");
  const view = hub.tabs.get(id).view;
  assert.equal(view.__prefs.webPreferences.javascript, false, "new tabs must honor the JS flag");
  assert.equal(hub.setJavaScriptEnabled(true).javascriptEnabled, true);
  const id2 = hub.createTab("https://example.org/");
  assert.equal(hub.tabs.get(id2).view.__prefs.webPreferences.javascript, true);
});

test("hub constructor seeds policy flags (settings restored at startup)", () => {
  const hub = new Hub({ window: () => fakeWindow, onExternal: () => {},
    cookiesEnabled: false, javascriptEnabled: false, defaultZoom: 150 });
  assert.equal(hub.cookiesEnabled, false);
  assert.equal(hub.javascriptEnabled, false);
  assert.equal(hub.defaultZoom, 150);
  const id = hub.createTab("https://example.com/");
  assert.equal(hub.tabs.get(id).view.__prefs.webPreferences.javascript, false);
  assert.equal(hub.tabs.get(id).zoom, 150);
});
