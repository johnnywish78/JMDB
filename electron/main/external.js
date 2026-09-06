"use strict";
/** External browser opening: prefer an installed Chrome/Chromium if the user
 * asked for it (DRM sites etc.), always fall back to the system default. */
const { spawn } = require("node:child_process");
const { shell } = require("electron");

const CANDIDATES = [
  "google-chrome",
  "google-chrome-stable",
  "chromium",
  "chromium-browser",
  "chrome",
  "microsoft-edge",
  "microsoft-edge-stable",
  "vivaldi",
  "brave-browser",
  "firefox",
];

function list() {
  const pathEnv = process.env.PATH || "";
  const dirs = pathEnv.split(path.delimiter).filter(Boolean);
  const found = [];
  for (const dir of dirs) {
    for (const name of CANDIDATES) {
      try {
        const fs = require("node:fs");
        const candidate = require("node:path").join(dir, name);
        fs.accessSync(candidate, fs.constants.X_OK);
        if (!found.includes(name)) found.push(name);
      } catch {
        /* keep scanning */
      }
    }
  }
  return found;
}

function openChrome(url) {
  const available = list();
  if (available.length === 0) return { ok: false, reason: "no-browser-found" };
  const name = available[0];
  try {
    const child = spawn(name, [url], { detached: true, stdio: "ignore" });
    child.unref();
    return { ok: true, browser: name };
  } catch (error) {
    return { ok: false, reason: String(error) };
  }
}

function open(url, { preferChrome = false } = {}) {
  if (preferChrome) {
    const result = openChrome(url);
    if (result.ok) return result;
    // fall through to the default handler
    shell.openExternal(url);
    return { ok: true, browser: "system-default" };
  }
  shell.openExternal(url);
  return { ok: true, browser: "system-default" };
}

module.exports = { ExternalBrowser: { list, open, openChrome }, CANDIDATES };
