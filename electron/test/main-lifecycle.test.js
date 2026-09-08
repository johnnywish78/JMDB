"use strict";
/** Real main.js startup lifecycle test.
 *
 * Regression for the real-Electron startup crash:
 *   UnhandledPromiseRejectionWarning: Error: registerIpc: hub, downloads and
 *   permissions instances are required
 * main.js used to call registerIpc() inside app.whenReady() BEFORE boot()
 * created the managers, so the shared registry guard threw and the app never
 * came up. Source scans cannot see ordering, so this file EXECUTES the real
 * main.js with faithful electron stubs (the Python backend is the only stub
 * module) and asserts the lifecycle contract:
 *
 *   whenReady → boot(): backend → window → managers (with the REAL window)
 *   → vault → Hub → registerIpc (exactly once, all instances live) → loadURL
 */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Module = require("node:module");

const ELECTRON_DIR = path.join(__dirname, "..");

function buildStubs() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "jmdb-lifecycle-"));
  const handlers = new Map();
  const registrations = [];
  const windows = [];
  const sessions = new Map();
  const rejections = [];

  const ipcMain = {
    handle(channel, handler) {
      if (handlers.has(channel)) {
        throw new Error(`Attempted to register a second handler for '${channel}'`);
      }
      handlers.set(channel, handler);
      registrations.push(channel);
    },
    handleOnce(channel, handler) {
      handlers.set(channel, handler);
      registrations.push(channel);
    },
  };

  class FakeWebContents {
    constructor() {
      this.sent = [];
      this.handlers = new Map();
      this.navigationHistory = { goBack() {}, goForward() {} };
    }
    send(channel, payload) { this.sent.push({ channel, payload }); }
    setWindowOpenHandler() {}
    on(event, cb) { this.handlers.set(event, cb); }
    once(event, cb) { this.handlers.set(event, cb); }
    async loadURL() {}
    async executeJavaScript() { return true; }
    reload() {}
  }

  class FakeBrowserWindow {
    constructor(options) {
      this.options = options;
      this.webContents = new FakeWebContents();
      this.listeners = new Map();
      windows.push(this);
    }
    once(event, cb) { this.listeners.set(event, cb); }
    on(event, cb) { this.listeners.set(event, cb); }
    async loadURL() {}
    isDestroyed() { return false; }
    isMinimized() { return false; }
    restore() {}
    focus() {}
    show() {}
  }

  class FakeWebContentsView {
    constructor(options) {
      this.options = options;
      this.webContents = new FakeWebContents();
      this.visible = true;
    }
    setVisible() {}
    setBounds() {}
  }

  const app = {
    _ready: null,
    setName() {},
    isPackaged: true,
    getVersion: () => "0.0.0-test",
    requestSingleInstanceLock: () => true,
    on() {},
    whenReady() {
      if (!this._ready) this._ready = Promise.resolve();
      return this._ready;
    },
    getPath(name) {
      if (name === "userData") return path.join(tmp, "userData");
      if (name === "downloads") return path.join(tmp, "downloads");
      return tmp;
    },
    quit() {},
    exit() {},
  };

  const session = {
    fromPartition(name) {
      if (!sessions.has(name)) {
        sessions.set(name, {
          _listeners: new Map(),
          setPermissionRequestHandler() {},
          webRequest: {
            onBeforeSendHeaders() {},
            onHeadersReceived() {},
            onSendHeaders() {},
          },
          on(event, cb) { this._listeners.set(event, cb); },
        });
      }
      return sessions.get(name);
    },
  };

  const electron = {
    app,
    BrowserWindow: FakeBrowserWindow,
    WebContentsView: FakeWebContentsView,
    clipboard: { writeText() {} },
    dialog: {
      showOpenDialog: async () => ({ canceled: true, filePaths: [] }),
      showMessageBox: async () => ({ response: 2 }),
    },
    ipcMain,
    Menu: { buildFromTemplate: () => ({ popup() {} }) },
    nativeTheme: { on() {}, shouldUseDarkColors: false },
    safeStorage: { isEncryptionAvailable: () => false },
    session,
    shell: { openExternal: async () => ({ ok: true }), showItemInFolder() {} },
  };

  // the only stubbed app module: the backend would spawn a real Python process
  const backendStub = {
    BackendProcess: class {
      constructor() { this.url = null; this.token = null; }
      async start() {
        this.url = "http://127.0.0.1:45999";
        this.token = "lifecycle-test-token";
        return { url: this.url, token: this.token };
      }
      async stop() {}
      kill() {}
    },
  };

  return { tmp, handlers, registrations, windows, sessions, rejections, electron, backendStub, app };
}

function withStubs(stubs, fn) {
  const origLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === "electron") return stubs.electron;
    // main.js requires "./main/backend"; keep every other app module real
    if (request === "./main/backend") return stubs.backendStub;
    return origLoad.apply(this, arguments);
  };
  try {
    return fn();
  } finally {
    Module._load = origLoad;
  }
}

async function runMainJs(stubs) {
  const onUnhandled = (reason) => stubs.rejections.push(reason);
  process.on("unhandledRejection", onUnhandled);
  const origFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ values: {} }) });

  // the hook must stay installed for the whole async boot: managers require
  // "electron" again from inside their constructors (module-level + ctor-time)
  const origLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === "electron") return stubs.electron;
    if (request === "./main/backend") return stubs.backendStub;
    return origLoad.apply(this, arguments);
  };

  try {
    // fresh module graph so the stubs bind to this run's ipcMain
    for (const key of Object.keys(require.cache)) {
      if (key.startsWith(ELECTRON_DIR + path.sep) && !key.includes(`${path.sep}node_modules${path.sep}`)) {
        delete require.cache[key];
      }
    }
    require(path.join(ELECTRON_DIR, "main.js"));
    await stubs.app.whenReady();
    // let boot() settle: backend.start() + settings fetch are awaited inside
    for (let i = 0; i < 20 && !stubs.handlers.has("hub:setVisible"); i++) {
      await new Promise((resolve) => setImmediate(resolve));
    }
    await new Promise((resolve) => setImmediate(resolve));
  } finally {
    Module._load = origLoad;
    globalThis.fetch = origFetch;
    process.off("unhandledRejection", onUnhandled);
  }
}

test("main.js boots the lifecycle and registers IPC after its managers exist", async () => {
  const stubs = buildStubs();
  try {
    await runMainJs(stubs);

    // THE regression: the old whenReady ordering aborted here with
    // "registerIpc: hub, downloads and permissions instances are required"
    assert.deepEqual(stubs.rejections, [], "no unhandled rejection during startup");

    // the shared surface is fully registered before the renderer loads
    for (const channel of [
      "app:info", "open-external", "dialog:pickFolder",
      "hub:createTab", "hub:setVisible", "hub:tabs", "hub:setCookiesEnabled",
      "downloads:list", "permissions:respond", "passwords:list",
    ]) {
      assert.ok(stubs.handlers.has(channel), `missing IPC handler: ${channel}`);
    }

    // registered exactly once (the ipcMain stub throws on a second handler,
    // which would surface as a rejection above)
    assert.equal(stubs.registrations.length, new Set(stubs.registrations).size,
      "duplicate IPC registration");

    // handlers are bound to the REAL instances created by boot()
    const info = await stubs.handlers.get("app:info")();
    assert.equal(info.backendUrl, "http://127.0.0.1:45999",
      "app:info must report the live backend (registration happened after boot owned it)");
    await stubs.handlers.get("hub:setVisible")(null, true); // must not throw
    assert.deepEqual(await stubs.handlers.get("downloads:list")(), []);
    const vault = await stubs.handlers.get("passwords:list")();
    assert.equal(vault.ok, true);

    // managers captured the real window: a session download must stream
    // progress to the renderer (with the old ordering the managers were
    // constructed before createWindow() and held a null window forever)
    assert.equal(stubs.windows.length, 1, "exactly one main window");
    const hubSession = stubs.sessions.get("persist:jmdb");
    const willDownload = hubSession._listeners.get("will-download");
    assert.ok(willDownload, "DownloadManager listens for will-download");
    willDownload(
      {},
      {
        getFilename: () => "lifecycle-check.bin",
        getTotalBytes: () => 10,
        getReceivedBytes: () => 10,
        getURL: () => "https://example.com/lifecycle-check.bin",
        getMimeType: () => "application/octet-stream",
        setSavePath() {},
        on() {},
        once() {},
      },
      null,
    );
    const sent = stubs.windows[0].webContents.sent;
    assert.ok(sent.some((m) => m.channel === "downloads:updated"),
      "download progress must reach the main window");
  } finally {
    fs.rmSync(stubs.tmp, { recursive: true, force: true });
  }
});
