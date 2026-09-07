"use strict";
/** PermissionManager tests (electron/main/permissions.js) with a stubbed
 * electron module: hub-tab asks surface as the in-page dialog and are answered
 * via respondFromRenderer; other requests use the native dialog; timeouts fall
 * back to native. The code under test is the real file. */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Module = require("node:module");

const userData = fs.mkdtempSync(path.join(os.tmpdir(), "jmdb-perm-test-"));

const sent = [];
const nativeDialogs = [];
let nativeResponse = 0;

const stubElectron = {
  app: {
    getPath: (name) => (name === "userData" ? userData : os.tmpdir()),
    isPackaged: true,
    getName: () => "JMDB",
  },
  dialog: {
    showMessageBox: async (win, options) => {
      nativeDialogs.push({ win, options });
      return { response: nativeResponse };
    },
  },
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "electron") return stubElectron;
  return origLoad.apply(this, arguments);
};

const { PermissionManager } = require("../main/permissions.js");

const fakeWindow = {
  isDestroyed: () => false,
  webContents: { send: (channel, payload) => sent.push({ channel, payload }) },
};

const fakeHubTab = { getURL: () => "https://site.example/page" };
const fakeAppUi = { getURL: () => "http://127.0.0.1:8123/app/" };

function freshManager(hubLookup) {
  sent.length = 0;
  nativeDialogs.length = 0;
  // persisted decisions from earlier tests must not leak between cases
  fs.rmSync(path.join(userData, "permissions.json"), { force: true });
  const manager = new PermissionManager(fakeWindow);
  manager.setHubLookup(hubLookup || (() => false));
  return manager;
}

test("unknown permissions are denied without any dialog", async () => {
  const manager = freshManager();
  let granted = "unset";
  await manager.handle(fakeHubTab, "totally-unknown-permission", (ok) => { granted = ok; });
  assert.equal(granted, false);
  assert.equal(nativeDialogs.length, 0, "no dialog for unknown permissions");
});

test("hub-tab requests go to the in-page dialog and Allow answers once", async () => {
  const manager = freshManager(() => true);
  let granted = "unset";
  await manager.handle(fakeHubTab, "geolocation", (ok) => { granted = ok; });
  assert.equal(granted, "unset", "not decided until the renderer answers");
  assert.equal(sent.length, 1);
  assert.equal(sent[0].channel, "permissions:asked");
  assert.equal(sent[0].payload.origin, "https://site.example");
  assert.ok(sent[0].payload.message.includes("location"));

  manager.respondFromRenderer({ id: sent[0].payload.id, allowed: true });
  assert.equal(granted, true, "callback resolved with allow");
  // "once" answers are NOT persisted as standing decisions
  assert.equal(manager.list().length, 0);
});

test("Always-allow answers are persisted per origin and skip asking next time", async () => {
  const manager = freshManager(() => true);
  let granted = "unset";
  await manager.handle(fakeHubTab, "notifications", (ok) => { granted = ok; });
  manager.respondFromRenderer({ id: sent[0].payload.id, allowed: true, remember: true });
  assert.equal(granted, true);
  assert.equal(manager.list().length, 1, "decision persisted");

  let second = "unset";
  await manager.handle(fakeHubTab, "notifications", (ok) => { second = ok; });
  assert.equal(second, true, "no second ask — standing decision applied");
  assert.equal(sent.length, 1, "no second permissions:asked");
});

test("hub-tab requests fall back to the NATIVE dialog when the renderer never answers", async () => {
  const manager = freshManager(() => true);
  manager.askTimeoutMs = 10; // test-only override of the 30s production timeout
  let granted = "unset";
  await manager.handle(fakeHubTab, "geolocation", (ok) => { granted = ok; });
  assert.equal(sent.length, 1, "renderer was asked first");
  await new Promise((resolve) => setTimeout(resolve, 40));
  assert.equal(nativeDialogs.length, 1, "native dialog shown after timeout");
  nativeResponse = 0; // "Allow once"
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(granted, true, "native answer resolved the request");
});

test("non-hub requests use the native dialog directly", async () => {
  const manager = freshManager(() => false);
  nativeResponse = 1; // "Always allow"
  let granted = "unset";
  await manager.handle(fakeAppUi, "geolocation", (ok) => { granted = ok; });
  assert.equal(granted, true);
  assert.equal(nativeDialogs.length, 1);
  assert.equal(sent.length, 0, "no in-page dialog for the app UI");
  assert.equal(manager.list().length, 1, "always-allow persisted");
});

test("renderer responses for unknown ids are ignored safely", () => {
  const manager = freshManager(() => true);
  manager.respondFromRenderer({ id: 424242, allowed: true });
  assert.equal(manager.list().length, 0);
  assert.doesNotThrow(() => manager.respondFromRenderer({}));
});
