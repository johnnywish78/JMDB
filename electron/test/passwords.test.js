"use strict";
/** Password vault tests (electron/main/passwords.js) with a stubbed electron
 * module — the vault logic is the real file; safeStorage/clipboard are fakes.
 *
 * Verifies the security-relevant behavior: no plaintext secrets in list(),
 * secrets decrypt only via reveal/copy, the local-key fallback actually
 * encrypts (file bytes differ from plaintext), persistence round-trips, and
 * nothing ever logs secret material.
 */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Module = require("node:module");

// fake safeStorage: XOR obfuscation is enough to prove the code paths differ
class FakeSafeStorage {
  constructor() { this.available = true; }
  isEncryptionAvailable() { return this.available; }
  encryptString(plain) { return Buffer.from(plain).map((b) => b ^ 0x5a); }
  decryptString(buf) { return Buffer.from(buf).map((b) => b ^ 0x5a).toString("utf8"); }
}

function makeVault({ safeStorage = null, logs = [] } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "jmdb-vault-"));
  const stub = {
    app: { getPath: () => dir },
    safeStorage,
    clipboard: {
      written: [],
      writeText(text) { this.written.push(text); },
    },
    log: (message) => logs.push(message),
  };
  const origLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === "electron") return stub; // not used by passwords.js, kept for parity
    return origLoad.apply(this, arguments);
  };
  let vault;
  try {
    const { PasswordVault } = require("../main/passwords.js");
    vault = new PasswordVault(stub);
  } finally {
    Module._load = origLoad;
  }
  return { vault, dir, clipboard: stub.clipboard, logs };
}

test("add/list: entries never contain the secret", () => {
  const { vault } = makeVault({ safeStorage: new FakeSafeStorage() });
  const added = vault.add({ domain: "example.com", username: "alice", password: "s3cret!", notes: "note" });
  assert.equal(added.ok, true);
  const list = vault.list();
  assert.equal(list.length, 1);
  assert.equal(list[0].domain, "example.com");
  assert.equal(list[0].username, "alice");
  assert.deepEqual(Object.keys(list[0]).sort(),
    ["created_at", "domain", "id", "notes", "updated_at", "username"]);
});

test("reveal/copy decrypt on explicit request only", () => {
  const { vault, clipboard } = makeVault({ safeStorage: new FakeSafeStorage() });
  const { id } = vault.add({ domain: "example.com", username: "alice", password: "hunter2" });
  const revealed = vault.reveal(id);
  assert.equal(revealed.ok, true);
  assert.equal(revealed.password, "hunter2");
  const copied = vault.copy(id);
  assert.equal(copied.ok, true);
  assert.deepEqual(clipboard.written, ["hunter2"]);
});

test("local-key fallback: file never contains plaintext; round-trips", () => {
  const { vault, dir } = makeVault({ safeStorage: null });
  vault.add({ domain: "example.com", username: "bob", password: "PlainTextSecret" });
  const raw = fs.readFileSync(path.join(dir, "passwords-vault.json"), "utf8");
  assert.ok(!raw.includes("PlainTextSecret"), "vault file must not contain the plaintext password");
  assert.equal(vault.backendName(), "local-key");

  // fresh instance reading the same file decrypts correctly
  const { PasswordVault } = require("../main/passwords.js");
  const second = new PasswordVault({
    app: { getPath: () => dir }, safeStorage: null,
    clipboard: { writeText: () => {} }, log: () => {},
  });
  const list = second.list();
  assert.equal(list.length, 1);
  assert.equal(second.reveal(list[0].id).password, "PlainTextSecret");
});

test("update/remove and persistence across instances", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "jmdb-vault-persist-"));
  const { PasswordVault } = require("../main/passwords.js");
  const mk = () => new PasswordVault({
    app: { getPath: () => dir }, safeStorage: new FakeSafeStorage(),
    clipboard: { writeText: () => {} }, log: () => {},
  });
  const one = mk();
  const { id } = one.add({ domain: "a.com", username: "u", password: "p1" });
  one.update(id, { username: "u2", password: "p2" });

  const two = mk();
  assert.deepEqual(two.list().map((e) => e.username), ["u2"]);
  assert.equal(two.reveal(id).password, "p2");
  assert.equal(two.remove(id).ok, true);
  const three = mk();
  assert.equal(three.list().length, 0);
});

test("validation + missing entries fail honestly", () => {
  const { vault } = makeVault({ safeStorage: new FakeSafeStorage() });
  assert.equal(vault.add({ domain: "", username: "u", password: "p" }).ok, false);
  assert.equal(vault.add({ domain: "d", username: "u", password: "" }).ok, false);
  assert.equal(vault.reveal(999).ok, false);
  assert.equal(vault.remove(999).ok, false);
  assert.equal(vault.update(999, { domain: "x" }).ok, false);
});

test("logs contain entry ids only, never secrets", () => {
  const logs = [];
  const { vault } = makeVault({ safeStorage: new FakeSafeStorage(), logs });
  const { id } = vault.add({ domain: "example.com", username: "alice", password: "TOPSECRET" });
  vault.update(id, { notes: "n" });
  vault.remove(id);
  const joined = logs.join(" ");
  assert.ok(!joined.includes("TOPSECRET"), "secrets must never be logged");
  assert.ok(!joined.includes("alice"), "usernames are not logged either");
  assert.ok(joined.includes(`entry ${id}`));
});

test("local key file is generated once with restrictive permissions", () => {
  const { vault, dir } = makeVault({ safeStorage: null });
  vault.add({ domain: "d.com", username: "u", password: "p" });
  const keyPath = path.join(dir, "vault.key");
  assert.ok(fs.existsSync(keyPath));
  const stat = fs.statSync(keyPath);
  assert.equal(stat.mode & 0o077, 0, "key file must not be group/world readable");
  const first = fs.readFileSync(keyPath);
  vault.add({ domain: "d2.com", username: "u", password: "p" });
  assert.deepEqual(fs.readFileSync(keyPath), first, "key is stable across saves");
});
