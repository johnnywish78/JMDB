"use strict";
/** Regression: electron/main/external.js used `path.delimiter` without
 * importing node:path — every call to ExternalBrowser.list() (e.g. the
 * app:info IPC used by Settings → About) threw
 *   ReferenceError: path is not defined (external.js:22:30)
 * The module is loaded here with a stubbed electron module, which is exactly
 * how the real main process loads it (the bug was in plain Node scope). */
const test = require("node:test");
const assert = require("node:assert");
const Module = require("node:module");

const origLoad = Module._load;
const opened = [];
const stubElectron = {
  shell: { openExternal: (url) => opened.push(url) },
};

Module._load = function (request, parent, isMain) {
  if (request === "electron") return stubElectron;
  return origLoad.apply(this, arguments);
};

let ExternalBrowser;
try {
  ({ ExternalBrowser } = require("../main/external.js"));
} finally {
  Module._load = origLoad;
}

test("module loads and list() does not throw (path is defined)", () => {
  const found = ExternalBrowser.list();
  assert.ok(Array.isArray(found), "list() must return an array");
});

test("open() falls back to the system default browser", () => {
  opened.length = 0;
  const result = ExternalBrowser.open("https://example.com/");
  assert.deepEqual(result, { ok: true, browser: "system-default" });
  assert.deepEqual(opened, ["https://example.com/"]);
});

test("open(url, preferChrome) still opens something when no Chrome exists", () => {
  opened.length = 0;
  const result = ExternalBrowser.open("https://example.com/x", { preferChrome: true });
  assert.equal(result.ok, true);
  assert.ok(opened.includes("https://example.com/x"));
});

test("list() discovers an executable browser on a fake PATH", () => {
  const fs = require("node:fs");
  const os = require("node:os");
  const path = require("node:path");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fakebin-"));
  const fake = path.join(dir, "chromium");
  fs.writeFileSync(fake, "#!/bin/sh\nexit 0\n");
  fs.chmodSync(fake, 0o755);
  const previous = process.env.PATH;
  process.env.PATH = `${dir}`;
  try {
    const found = ExternalBrowser.list();
    assert.ok(found.includes("chromium"), `expected chromium in ${JSON.stringify(found)}`);
  } finally {
    process.env.PATH = previous;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
