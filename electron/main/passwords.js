"use strict";
/** Local password vault for the Browser Hub.
 *
 * Security model (honest, no pretending):
 * - Secrets are encrypted at rest with the OS-backed key store when
 *   Electron's safeStorage is available (Linux libsecret, macOS Keychain,
 *   Windows DPAPI). When it is NOT available, the vault falls back to
 *   AES-256-GCM with a locally generated 256-bit key file (0600) in the
 *   user data directory — better than plaintext, weaker than an OS keychain;
 *   the UI states which backend is active.
 * - Passwords NEVER leave the main process except on an explicit reveal or
 *   copy of one entry. list() returns entries without passwords.
 * - Nothing here logs secrets (or even usernames) — errors carry entry ids.
 * - No autofill: injecting stored credentials into arbitrary web content is
 *   the risky part real password managers spend years hardening; this vault
 *   exposes save/search/reveal/copy instead, and the UI says so.
 *
 * Storage: <userData>/passwords-vault.json
 *   { "backend": "safeStorage" | "local-key", "entries": [ { id, domain,
 *     username, secret, notes, created_at, updated_at } ] }
 * where "secret" is base64: safeStorage blob, or "v1:" + base64(iv|tag|ct).
 */
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const VAULT_FILE = "passwords-vault.json";
const KEY_FILE = "vault.key";

class PasswordVault {
  /** deps: { app, safeStorage, clipboard } are injected for testability. */
  constructor({ app, safeStorage, clipboard, log = () => {} }) {
    this.app = app;
    this.safeStorage = safeStorage;
    this.clipboard = clipboard;
    this.log = log; // only operational messages; NEVER secret material
    this.dir = path.join(app.getPath("userData"));
    this.file = path.join(this.dir, VAULT_FILE);
    this.entries = [];
    this.backend = null; // resolved on first use (safeStorage needs the app ready)
  }

  // -- backend resolution --------------------------------------------------

  encryptionBackend() {
    if (this.backend) return this.backend;
    try {
      if (this.safeStorage && this.safeStorage.isEncryptionAvailable()) {
        this.backend = "safeStorage";
        return this.backend;
      }
    } catch {
      /* fall through to the local-key backend */
    }
    this.backend = "local-key";
    return this.backend;
  }

  encrypt(plain) {
    if (this.encryptionBackend() === "safeStorage") {
      return this.safeStorage.encryptString(plain).toString("base64");
    }
    const key = this.localKey();
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
    const ct = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
    const tag = cipher.getAuthTag();
    return "v1:" + Buffer.concat([iv, tag, ct]).toString("base64");
  }

  decrypt(blob) {
    if (this.encryptionBackend() === "safeStorage") {
      return this.safeStorage.decryptString(Buffer.from(blob, "base64"));
    }
    if (!blob.startsWith("v1:")) throw new Error("unreadable entry");
    const raw = Buffer.from(blob.slice(3), "base64");
    const iv = raw.subarray(0, 12);
    const tag = raw.subarray(12, 28);
    const ct = raw.subarray(28);
    const decipher = crypto.createDecipheriv("aes-256-gcm", this.localKey(), iv);
    decipher.setAuthTag(tag);
    return Buffer.concat([decipher.update(ct), decipher.final()]).toString("utf8");
  }

  localKey() {
    const keyPath = path.join(this.dir, KEY_FILE);
    try {
      const existing = fs.readFileSync(keyPath);
      if (existing.length === 32) return existing;
    } catch {
      /* generate below */
    }
    const key = crypto.randomBytes(32);
    fs.mkdirSync(this.dir, { recursive: true });
    fs.writeFileSync(keyPath, key, { mode: 0o600 });
    return key;
  }

  // -- persistence ----------------------------------------------------------

  load() {
    try {
      const data = JSON.parse(fs.readFileSync(this.file, "utf8"));
      this.entries = Array.isArray(data.entries) ? data.entries : [];
      this.fileBackend = data.backend || null;
    } catch {
      this.entries = [];
      this.fileBackend = null;
    }
  }

  save() {
    fs.mkdirSync(this.dir, { recursive: true });
    const payload = { backend: this.encryptionBackend(), entries: this.entries };
    fs.writeFileSync(this.file, JSON.stringify(payload, null, 2), { mode: 0o600 });
  }

  ensureLoaded() {
    if (this.entries === null || this._loaded !== true) {
      this.load();
      this._loaded = true;
    }
  }

  // -- entry CRUD (renderer-facing; never returns secrets except reveal) ----

  list() {
    this.ensureLoaded();
    return this.entries.map((entry) => ({
      id: entry.id, domain: entry.domain, username: entry.username,
      notes: entry.notes || "", created_at: entry.created_at, updated_at: entry.updated_at,
    }));
  }

  backendName() {
    return this.encryptionBackend();
  }

  add({ domain, username, password, notes = "" }) {
    this.ensureLoaded();
    if (!domain || !username || typeof password !== "string" || !password) {
      return { ok: false, error: "domain, username and password are required" };
    }
    const now = new Date().toISOString();
    const id = this.entries.reduce((max, e) => Math.max(max, e.id), 0) + 1;
    this.entries.push({
      id, domain: String(domain).trim(), username: String(username).trim(),
      secret: this.encrypt(String(password)), notes: String(notes || ""),
      created_at: now, updated_at: now,
    });
    this.save();
    this.log(`vault: entry ${id} added`); // ids only, never contents
    return { ok: true, id };
  }

  update(id, { domain, username, password, notes }) {
    this.ensureLoaded();
    const entry = this.entries.find((e) => e.id === Number(id));
    if (!entry) return { ok: false, error: "entry not found" };
    if (domain !== undefined) entry.domain = String(domain).trim();
    if (username !== undefined) entry.username = String(username).trim();
    if (notes !== undefined) entry.notes = String(notes);
    if (password) entry.secret = this.encrypt(String(password));
    entry.updated_at = new Date().toISOString();
    this.save();
    this.log(`vault: entry ${id} updated`);
    return { ok: true };
  }

  remove(id) {
    this.ensureLoaded();
    const before = this.entries.length;
    this.entries = this.entries.filter((e) => e.id !== Number(id));
    if (this.entries.length === before) return { ok: false, error: "entry not found" };
    this.save();
    this.log(`vault: entry ${id} removed`);
    return { ok: true };
  }

  /** Explicit user action only: decrypt one entry's secret. */
  reveal(id) {
    this.ensureLoaded();
    const entry = this.entries.find((e) => e.id === Number(id));
    if (!entry) return { ok: false, error: "entry not found" };
    try {
      return { ok: true, password: this.decrypt(entry.secret) };
    } catch {
      // wrong key / damaged entry — never leak details, never crash the UI
      return { ok: false, error: "locked (decryption failed)" };
    }
  }

  /** Explicit user action only: decrypt one entry into the clipboard. */
  copy(id) {
    const result = this.reveal(id);
    if (!result.ok) return result;
    if (!this.clipboard) return { ok: false, error: "clipboard unavailable" };
    this.clipboard.writeText(result.password);
    return { ok: true };
  }
}

module.exports = { PasswordVault };
