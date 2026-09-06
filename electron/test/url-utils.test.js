"use strict";
/** Unit tests for the pure URL helpers (run with: node --test test/). */
const test = require("node:test");
const assert = require("node:assert");
const { isDrmHost, normalizeInput, truncate, uniquePath } = require("../main/url-utils.js");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

test("isDrmHost detects DRM streaming hosts", () => {
  assert.equal(isDrmHost("netflix.com"), true);
  assert.equal(isDrmHost("www.netflix.com"), true);
  assert.equal(isDrmHost("NL.SUB.netflix.com".toLowerCase()), true);
  assert.equal(isDrmHost("disneyplus.com"), true);
  assert.equal(isDrmHost("tv.apple.com"), true);
});

test("isDrmHost rejects ordinary hosts", () => {
  assert.equal(isDrmHost("youtube.com"), false);
  assert.equal(isDrmHost("notnetflix.com.example.org"), false);
  assert.equal(isDrmHost(""), false);
  assert.equal(isDrmHost(null), false);
  assert.equal(isDrmHost("netflix.community-forum.org"), false);
});

test("normalizeInput passes through URLs, upgrades bare domains", () => {
  assert.equal(normalizeInput("https://example.org/x"), "https://example.org/x");
  assert.equal(normalizeInput("http://example.org"), "http://example.org");
  assert.equal(normalizeInput("example.org"), "https://example.org");
  assert.equal(normalizeInput("sub.example.org/watch?v=1"), "https://sub.example.org/watch?v=1");
  assert.equal(normalizeInput("  example.org  "), "https://example.org");
});

test("normalizeInput returns null for searches (caller searches)", () => {
  assert.equal(normalizeInput("night runner 2024"), null);
  assert.equal(normalizeInput("what is the best movie"), null);
  assert.equal(normalizeInput("example.org with space"), null);
});

test("normalizeInput falls back to the home url for empty input", () => {
  assert.equal(normalizeInput("", "https://duckduckgo.com"), "https://duckduckgo.com");
  assert.equal(normalizeInput("   "), "https://duckduckgo.com");
});

test("truncate shortens labels with an ellipsis", () => {
  assert.equal(truncate("hello", 10), "hello");
  assert.equal(truncate("hello world", 8), "hello w…");
  assert.equal(truncate("a  b   c", 4), "a b…");
});

test("uniquePath avoids overwriting existing files", (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "jmdb-unique-"));
  fs.writeFileSync(path.join(dir, "video.mkv"), "x");
  fs.writeFileSync(path.join(dir, "video (1).mkv"), "x");
  assert.equal(uniquePath(dir, "video.mkv"), path.join(dir, "video (2).mkv"));
  assert.equal(uniquePath(dir, "other.mkv"), path.join(dir, "other.mkv"));
  assert.equal(uniquePath(dir, "new.mp4"), path.join(dir, "new.mp4"));
});
