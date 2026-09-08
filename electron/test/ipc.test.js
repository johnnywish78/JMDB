"use strict";
/** Shared IPC surface tests (electron/main/ipc.js).
 *
 * Regression for the smoke failure class: smoke.js used to boot the renderer
 * without registering the hub IPC surface, so the first hub:setVisible call
 * from the renderer ("No handler registered") failed. main.js and smoke.js
 * now both register through main/ipc.js — this file proves the shared surface
 * covers EVERY channel the preload bridge can invoke, so that class of bug
 * cannot come back.
 */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");

function withStubbedElectron(stub, fn) {
  const origLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === "electron") return stub;
    return origLoad.apply(this, arguments);
  };
  try {
    return fn();
  } finally {
    Module._load = origLoad;
  }
}

/** Every channel the preload bridge can invoke, extracted from the real
 * preload.js source (so this test fails when preload grows a channel that
 * the shared IPC surface forgets to register). */
function preloadInvokeChannels() {
  const source = fs.readFileSync(path.join(__dirname, "..", "preload.js"), "utf-8");
  const channels = new Set();
  for (const match of source.matchAll(/invoke\("([^"]+)"/g)) channels.add(match[1]);
  for (const match of source.matchAll(/hubChannel\("([^"]+)"\)/g)) channels.add(`hub:${match[1]}`);
  return [...channels].filter((channel) => !channel.startsWith("smoke:"));
}

function makeStub() {
  const handlers = new Map();
  return {
    handlers,
    electron: {
      app: { getVersion: () => "0.0.0-test", isPackaged: true },
      dialog: { showOpenDialog: async () => ({ canceled: true, filePaths: [] }) },
      ipcMain: {
        handle: (channel, handler) => handlers.set(channel, handler),
      },
    },
  };
}

function fakeManagers() {
  const calls = { setVisible: [], createTab: [] };
  return {
    calls,
    hub: {
      createTab: (url) => { calls.createTab.push(url); return Promise.resolve(1); },
      closeTab: () => {}, activateTab: () => {}, navigate: () => {},
      back: () => {}, forward: () => {}, reload: () => {}, stop: () => {}, home: () => {},
      find: () => {}, clearFind: () => {}, zoom: () => {}, reopenTab: () => {},
      tabSummaries: () => [], setBounds: () => {},
      setVisible: (visible) => calls.setVisible.push(visible),
      recentHistory: () => [], clearHistory: () => {}, togglePin: () => {},
      favoritesList: () => [], switchTab: () => {}, print: () => {}, exportPdf: () => {},
      clearData: () => {}, setDefaultZoom: () => {},
      setCookiesEnabled: () => ({ ok: true }), setJavaScriptEnabled: () => ({ ok: true }),
    },
    downloads: {
      list: () => [], cancel: () => {}, pause: () => {}, resume: () => {}, openInFolder: () => {},
    },
    permissions: { respondFromRenderer: () => {} },
    vault: {
      list: () => [], backendName: () => "safeStorage",
      add: () => ({ ok: true }), update: () => ({ ok: true }), remove: () => ({ ok: true }),
      reveal: () => ({ ok: true }), copy: () => ({ ok: true }),
    },
    backend: { url: "http://127.0.0.1:9999" },
    getWindow: () => null,
  };
}

function freshRegisterIpc(stub, deps) {
  const resolved = require.resolve(path.join(__dirname, "..", "main", "ipc.js"));
  delete require.cache[resolved]; // bind to THIS stub's ipcMain
  return withStubbedElectron(stub.electron, () => require("../main/ipc.js").registerIpc(deps));
}

test("registerIpc covers every channel the preload can invoke", () => {
  const stub = makeStub();
  const deps = fakeManagers();
  freshRegisterIpc(stub, deps);
  const missing = preloadInvokeChannels().filter((channel) => !stub.handlers.has(channel));
  assert.deepEqual(missing, [], "preload channels without an IPC handler");
});

test("hub:setVisible delegates to the registered hub instance", async () => {
  const stub = makeStub();
  const deps = fakeManagers();
  freshRegisterIpc(stub, deps);
  const handler = stub.handlers.get("hub:setVisible");
  assert.ok(handler, "hub:setVisible must be registered");
  await handler(null, false);
  await handler(null, true);
  assert.deepEqual(deps.calls.setVisible, [false, true]);
});

test("registerIpc refuses incomplete manager sets", () => {
  const stub = makeStub();
  const deps = fakeManagers();
  delete deps.hub;
  assert.throws(
    () => freshRegisterIpc(stub, deps),
    /hub, downloads and permissions/
  );
});

test("main.js and smoke.js both register through the shared module", () => {
  const main = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf-8");
  const smoke = fs.readFileSync(path.join(__dirname, "..", "smoke.js"), "utf-8");
  assert.match(main, /registerIpc\(\{/, "main.js must call the shared registerIpc");
  assert.match(smoke, /registerIpc\(\{/, "smoke.js must call the shared registerIpc");
});

test("smoke.js sets JMDB_SMOKE before creating the window", () => {
  const smoke = fs.readFileSync(path.join(__dirname, "..", "smoke.js"), "utf-8");
  const flag = smoke.indexOf('process.env.JMDB_SMOKE = "1"');
  const window = smoke.indexOf("new BrowserWindow");
  assert.ok(flag !== -1, "smoke.js must set JMDB_SMOKE=1");
  assert.ok(window !== -1 && flag < window, "the flag must be set before the window exists");
});

test("preload exposes smoke.ready only when JMDB_SMOKE=1", () => {
  function loadWith(env) {
    const captured = {};
    const stub = {
      contextBridge: { exposeInMainWorld: (name, api) => { captured[name] = api; } },
      ipcRenderer: { invoke: () => Promise.resolve(true), on: () => {}, send: () => {}, removeListener: () => {} },
    };
    const previous = process.env.JMDB_SMOKE;
    if (env === undefined) delete process.env.JMDB_SMOKE;
    else process.env.JMDB_SMOKE = env;
    try {
      withStubbedElectron(stub, () => {
        const resolved = require.resolve(path.join(__dirname, "..", "preload.js"));
        delete require.cache[resolved];
        require(resolved);
      });
    } finally {
      if (previous === undefined) delete process.env.JMDB_SMOKE;
      else process.env.JMDB_SMOKE = previous;
    }
    return captured.jmdb;
  }

  const normal = loadWith(undefined);
  assert.equal(normal.smoke, undefined, "no smoke surface in normal runs");

  const smokeApi = loadWith("1");
  assert.ok(smokeApi.smoke && typeof smokeApi.smoke.ready === "function",
    "JMDB_SMOKE=1 must expose smoke.ready()");
});

test("app.js notifies smoke readiness after the first rendered route", () => {
  const source = fs.readFileSync(path.join(__dirname, "..", "src", "js", "app.js"), "utf-8");
  assert.match(source, /notifySmokeReady\(\);/, "renderRoute must call notifySmokeReady()");
  assert.match(source, /window\.jmdb\?\.smoke\?\.ready\?\.\(\)/, "it must ping the preload bridge");
});
