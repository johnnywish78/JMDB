"use strict";
/** Every Electron main-process module must LOAD (with a stubbed electron
 * module). This is the class of bug where external.js used `path` without
 * importing it — it only exploded at runtime inside Electron. Loading each
 * module here catches missing imports and top-level typos without the
 * (unavailable) Electron binary. */
const test = require("node:test");
const assert = require("node:assert");
const Module = require("node:module");

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "electron") {
    return {
      app: { getPath: () => "/tmp", isPackaged: true, getName: () => "JMDB", on: () => {}, whenReady: () => Promise.resolve(), requestSingleInstanceLock: () => true },
      BrowserWindow: class {},
      WebContentsView: class {},
      dialog: {},
      ipcMain: { handle: () => {} },
      session: { fromPartition: () => ({ on: () => {} }) },
      nativeTheme: { on: () => {} },
      Menu: { buildFromTemplate: () => ({ popup: () => {} }) },
      clipboard: {},
      shell: { openExternal: () => {} },
    };
  }
  return origLoad.apply(this, arguments);
};

const MODULES = [
  "../main/backend.js",
  "../main/context-menu.js",
  "../main/downloads.js",
  "../main/external.js",
  "../main/hub.js",
  "../main/permissions.js",
  "../main/url-utils.js",
];

for (const name of MODULES) {
  test(`${name} loads cleanly`, () => {
    const resolved = require.resolve(name);
    delete require.cache[resolved]; // fresh load each time
    const mod = require(name);
    assert.ok(mod && Object.keys(mod).length > 0, "module must export something");
  });
}

test("main.js and preload.js parse (full app entry points)", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  for (const file of ["main.js", "preload.js"]) {
    const source = fs.readFileSync(path.join(__dirname, "..", file), "utf-8");
    new Function("require", "module", "exports", "process", source); // parse check only
  }
});

test("the folder picker IPC channel is registered (shared main/ipc.js)", () => {
  const fs = require("node:fs");
  // the surface lives in the shared module both main.js and smoke.js register
  const ipcSource = fs.readFileSync(pathJoin("main/ipc.js"), "utf-8");
  assert.match(ipcSource, /dialog:pickFolder/);
  const mainSource = fs.readFileSync(pathJoin("main.js"), "utf-8");
  assert.match(mainSource, /registerIpc\(\{/, "main.js must call the shared registerIpc");
});

function pathJoin(file) {
  const path = require("node:path");
  return require("node:path").join(__dirname, "..", file);
}
