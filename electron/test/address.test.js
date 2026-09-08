"use strict";
/** Address input resolution — the configured search engine must actually
 * drive address-bar searches (regression: engine setting was ignored and
 * every search silently went to DuckDuckGo). */
const test = require("node:test");
const assert = require("node:assert");
const Module = require("node:module");

// The resolver lives in the renderer ESM tree; load it as text and evaluate
// as ESM via data URL so node's CJS test runner can exercise it.
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(
  path.join(__dirname, "..", "src", "js", "address.js"),
  "utf-8",
);

async function loadModule() {
  const mod = await import(
    "data:text/javascript;base64," + Buffer.from(source, "utf-8").toString("base64")
  );
  return mod;
}

test("SEARCH_ENGINES exposes the five documented engines", async () => {
  const { SEARCH_ENGINES } = await loadModule();
  assert.deepEqual(Object.keys(SEARCH_ENGINES).sort(),
    ["bing", "brave", "duckduckgo", "google", "startpage"]);
});

test("plain terms resolve to the CONFIGURED engine, not a default", async () => {
  const { resolveAddressInput, SEARCH_ENGINES } = await loadModule();
  assert.equal(
    resolveAddressInput("breaking bad", SEARCH_ENGINES.google),
    "https://www.google.com/search?q=breaking%20bad",
  );
  assert.equal(
    resolveAddressInput("breaking bad", SEARCH_ENGINES.brave),
    "https://search.brave.com/search?q=breaking%20bad",
  );
  assert.equal(
    resolveAddressInput("x", SEARCH_ENGINES.startpage),
    "https://www.startpage.com/sp/search?query=x",
  );
});

test("explicit URLs pass through untouched", async () => {
  const { resolveAddressInput, SEARCH_ENGINES } = await loadModule();
  for (const url of [
    "https://youtube.com/watch?v=abc",
    "http://example.org/path?q=1",
    "file:///tmp/x",
  ]) {
    assert.equal(resolveAddressInput(url, SEARCH_ENGINES.google), url);
  }
});

test("bare domains get https, localhost gets http", async () => {
  const { resolveAddressInput, SEARCH_ENGINES } = await loadModule();
  assert.equal(resolveAddressInput("example.com", SEARCH_ENGINES.google), "https://example.com");
  assert.equal(resolveAddressInput("www.tvtime.com/en", SEARCH_ENGINES.google), "https://www.tvtime.com/en");
  assert.equal(resolveAddressInput("localhost:8737", SEARCH_ENGINES.google), "http://localhost:8737");
});

test("empty input resolves to the engine home page", async () => {
  const { resolveAddressInput, SEARCH_ENGINES } = await loadModule();
  assert.equal(resolveAddressInput("", SEARCH_ENGINES.bing), SEARCH_ENGINES.bing);
});
