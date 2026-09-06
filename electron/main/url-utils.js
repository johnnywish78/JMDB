"use strict";
/** Pure URL/normalization helpers shared by the Browser Hub. No Electron imports. */
const fs = require("node:fs");
const path = require("node:path");

const DRM_DOMAINS = [
  "netflix.com",
  "disneyplus.com",
  "primevideo.com",
  "hulu.com",
  "hbomax.com",
  "max.com",
  "appletv.com",
  "tv.apple.com",
  "peacocktv.com",
  "paramountplus.com",
  "discoveryplus.com",
];

function isDrmHost(host) {
  const clean = String(host || "").toLowerCase().replace(/^www\./, "");
  return DRM_DOMAINS.some((domain) => clean === domain || clean.endsWith(`.${domain}`));
}

/** Is this an address, or a search? If a bare domain, add https://. */
function normalizeInput(input, homeUrl = "https://duckduckgo.com") {
  const text = String(input || "").trim();
  if (!text) return homeUrl;
  if (/^https?:\/\//i.test(text)) return text;
  if (/^[\w.-]+\.[a-z]{2,}([/?#].*)?$/i.test(text) && !text.includes(" ")) {
    return `https://${text}`;
  }
  return null; // caller decides how to search it
}

function truncate(text, length) {
  const clean = String(text).replace(/\s+/g, " ").trim();
  return clean.length > length ? `${clean.slice(0, length - 1)}…` : clean;
}

function uniquePath(dir, filename) {
  let candidate = path.join(dir, filename);
  if (!fs.existsSync(candidate)) return candidate;
  const ext = path.extname(filename);
  const base = path.basename(filename, ext);
  for (let i = 1; i < 1000; i++) {
    candidate = path.join(dir, `${base} (${i})${ext}`);
    if (!fs.existsSync(candidate)) return candidate;
  }
  return path.join(dir, `${base}-${Date.now()}${ext}`);
}

module.exports = { DRM_DOMAINS, isDrmHost, normalizeInput, truncate, uniquePath };
