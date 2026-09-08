/** App bootstrap: navigation, topbar, theme, live events, route registry. */
import { api } from "./api.js";
import { store, on, loadSettings, connectEvents, toggleTheme, applyTheme } from "./store.js";
import { el, clear, icon, toast, spinner } from "./ui.js";
import { currentRoute, navigate, onChange } from "./router.js";
import { openPlayer } from "./player.js";

import home from "./pages/home.js";
import movies from "./pages/movies.js";
import tv from "./pages/tv.js";
import music from "./pages/music.js";
import people from "./pages/people.js";
import search from "./pages/search.js";
import favorites from "./pages/favorites.js";
import watchlist from "./pages/watchlist.js";
import history from "./pages/history.js";
import collections from "./pages/collections.js";
import collectionDetail from "./pages/collection-detail.js";
import recommendations from "./pages/recommendations.js";
import statistics from "./pages/statistics.js";
import services from "./pages/services.js";
import settings from "./pages/settings.js";
import browser from "./pages/browser.js";
import movieDetail from "./pages/movie-detail.js";
import showDetail from "./pages/show-detail.js";
import seasonDetail from "./pages/season-detail.js";
import episodeDetail from "./pages/episode-detail.js";
import personDetail from "./pages/person-detail.js";
import albumDetail from "./pages/album-detail.js";
import artistDetail from "./pages/artist-detail.js";

const NAV = [
  { section: "Library" },
  { path: "/home", label: "Home", icon: "home" },
  { path: "/movies", label: "Movies", icon: "film" },
  { path: "/tv", label: "TV Shows", icon: "tv" },
  { path: "/music", label: "Music", icon: "music" },
  { path: "/people", label: "People", icon: "users" },
  { path: "/recommendations", label: "Recommended", icon: "sparkles" },
  { section: "Your lists" },
  { path: "/favorites", label: "Favorites", icon: "heart" },
  { path: "/watchlist", label: "Watchlist", icon: "bookmark" },
  { path: "/history", label: "History", icon: "history" },
  { path: "/collections", label: "Collections", icon: "folder" },
  { section: "More" },
  { path: "/services", label: "Services", icon: "globe" },
  { path: "/browser", label: "Browser Hub", icon: "globe" },
  { path: "/statistics", label: "Statistics", icon: "chart" },
  { path: "/settings", label: "Settings", icon: "settings" },
];

const ROUTES = [
  { match: /^\/home$/, render: home },
  { match: /^\/movies$/, render: movies },
  { match: /^\/tv$/, render: tv },
  { match: /^\/music$/, render: music },
  { match: /^\/people$/, render: people },
  { match: /^\/search$/, render: search },
  { match: /^\/favorites$/, render: favorites },
  { match: /^\/watchlist$/, render: watchlist },
  { match: /^\/history$/, render: history },
  { match: /^\/collections$/, render: collections },
  { match: /^\/collections\/(\d+)$/, render: collectionDetail },
  { match: /^\/recommendations$/, render: recommendations },
  { match: /^\/statistics$/, render: statistics },
  { match: /^\/services$/, render: services },
  { match: /^\/browser$/, render: browser },
  { match: /^\/settings$/, render: settings },
  { match: /^\/movie\/(\d+)$/, render: movieDetail },
  { match: /^\/show\/(\d+)$/, render: showDetail },
  { match: /^\/season\/(\d+)$/, render: seasonDetail },
  { match: /^\/episode\/(\d+)$/, render: episodeDetail },
  { match: /^\/person\/(\d+)$/, render: personDetail },
  { match: /^\/album\/(\d+)$/, render: albumDetail },
  { match: /^\/artist\/(\d+)$/, render: artistDetail },
];

const page = () => document.getElementById("page");

async function renderRoute(route) {
  const target = page();
  // leaving the browser page hides the native web views
  if (window.jmdb?.hub && route.path !== "/browser") {
    window.jmdb.hub.setVisible(false).catch(() => {});
  }
  for (const entry of ROUTES) {
    const match = route.path.match(entry.match);
    if (match) {
      clear(target);
      target.scrollTop = 0;
      target.classList.remove("full-bleed");
      clear(target).append(spinner());
      try {
        clear(target);
        await entry.render(target, route, match.slice(1));
      } catch (error) {
        clear(target);
        target.append(
          el("div", { class: "error-note" },
            `Couldn't load this page: ${error.message || error}`));
        console.error(error);
      }
      updateNav(route);
      notifySmokeReady();
      return;
    }
  }
  navigate("/home");
}

/** Smoke harness only (JMDB_SMOKE=1 → preload exposes window.jmdb.smoke):
 * report that the renderer booted and finished rendering its first real
 * page. No-op in normal runs. */
let smokeReadySent = false;
function notifySmokeReady() {
  if (smokeReadySent) return;
  smokeReadySent = true;
  try {
    window.jmdb?.smoke?.ready?.();
  } catch {
    /* smoke-only channel; never affects normal use */
  }
}

function updateNav(route) {
  document.querySelectorAll("#nav a").forEach((link) => {
    const href = link.getAttribute("href").replace(/^#/, "");
    const active = href === route.path || (route.path.startsWith(href + "/") && href !== "/home");
    link.classList.toggle("active", active);
  });
}

function buildNav() {
  const nav = document.getElementById("nav");
  clear(nav);
  for (const item of NAV) {
    if (item.section) {
      nav.append(el("div", { class: "nav-section" }, item.section));
      continue;
    }
    nav.append(el("a", { href: `#${item.path}` }, icon(item.icon), el("span", { class: "label" }, item.label)));
  }
}

/* ---------------------------------------------------------------- events */
function wireGlobalEvents() {
  // scans
  on("scan_started", () => {
    const pill = document.getElementById("scan-pill");
    pill.classList.remove("hidden");
    const text = document.getElementById("scan-pill-text");
    if (text) text.textContent = "Scanning…";
  });
  on("scan_progress", (data) => {
    const pill = document.getElementById("scan-pill");
    pill.classList.remove("hidden");
    const text = document.getElementById("scan-pill-text");
    if (text) {
      const seen = data.files_seen ? ` — ${data.files_seen} files` : "";
      if (data.phase === "matching") text.textContent = `Matching media${seen}`;
      else if (data.phase === "artwork") text.textContent = `Attaching artwork${seen}`;
      else if (data.paused) text.textContent = "Scan paused";
      else {
        const where = data.current_path ? ` ${String(data.current_path).split("/").pop()}` : "";
        text.textContent = `Scanning${where}${seen}`;
      }
    }
  });
  const hidePill = () => document.getElementById("scan-pill").classList.add("hidden");

  // One reporter for BOTH the WebSocket event and the REST polling fallback,
  // deduplicated by a signature of the result so a scan that finishes while
  // both paths are active toasts exactly once.
  let lastScanSignature = null;
  function reportScanFinished(data) {
    if (!data || !data.status) return;
    const signature = [
      data.status, data.files_indexed, data.files_seen, data.movies_added,
      data.shows_added, data.episodes_added, data.tracks_added, data.errors,
      data.duration_seconds,
    ].join("|");
    if (signature === lastScanSignature) return;
    lastScanSignature = signature;
    hidePill();
    if (data.status === "completed") {
      // success summaries honor the notify_scan setting; failures always surface
      if (store.settings.notify_scan !== false) {
        toast(
          `Scan finished in ${Math.max(1, Math.round(data.duration_seconds || 0))}s: ` +
          `${data.files_indexed || 0} files indexed, ` +
          `${data.movies_added || 0} movies / ${data.shows_added || 0} shows / ` +
          `${data.episodes_added || 0} episodes / ${data.tracks_added || 0} tracks added` +
          (data.errors ? ` (${data.errors} errors)` : ""),
          "success");
      }
    } else {
      toast(`Scan ${data.status || "finished"}${data.message ? `: ${data.message}` : ""}`, "error");
    }
    refreshCurrentPage();
  }
  on("scan_finished", reportScanFinished);
  on("scan_failed", (data) => {
    hidePill();
    toast(`Scan failed: ${data.error || "unknown error"}`, "error");
  });
  on("scan_finished_error", (data) => {
    hidePill();
    toast(`Scan failed: ${data.error || "unknown error"}`, "error");
  });

  on("library_changed", () => refreshCurrentPage());
  on("metadata_updated", (data) => {
    if (store.settings.notify_metadata !== false) {
      toast(`Metadata updated: ${data.title || "item"}`, "info");
    }
    refreshCurrentPage();
  });
  on("toast", (data) => toast(data.message || "", data.level === "error" ? "error" : "info"));
  on("PlaybackProgress", () => { /* player consumes this */ });
}

let refreshTimer = null;
function refreshCurrentPage() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => {
    if (document.querySelector(".player")) return; // don't yank the page mid-playback
    renderRoute(currentRoute());
  }, 400);
}

onChange((route) => renderRoute(route));

/* ---------------------------------------------------------------- topbar */
function wireTopbar() {
  const searchInput = document.getElementById("global-search");
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && searchInput.value.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchInput.value.trim())}`);
    }
  });

  document.getElementById("btn-theme").addEventListener("click", toggleTheme);

  document.getElementById("btn-scan").addEventListener("click", async () => {
    try {
      await api.post("/api/scan", {});
      document.getElementById("scan-pill").classList.remove("hidden");
    } catch (error) {
      toast(error.status === 409 ? "A scan is already running" : `Scan failed: ${error.message}`, "error");
    }
  });

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });
}

/* ---------------------------------------------------------------- boot */
function renderTokenGate() {
  const target = page();
  target.replaceChildren();
  const input = el("input", {
    class: "input", type: "password", placeholder: "Launch token",
    style: { width: "320px" }, spellcheck: "false",
  });
  const go = () => {
    const value = input.value.trim();
    if (!value) return;
    sessionStorage.setItem("jmdb_token", value);
    target.replaceChildren(el("div", { class: "spinner-wrap" }, el("div", { class: "spinner" })));
    boot();
  };
  input.addEventListener("keydown", (event) => { if (event.key === "Enter") go(); });
  target.append(
    el("div", { class: "empty", style: { paddingTop: "120px" } },
      el("h3", {}, "This JMDB backend wants its launch token"),
      el("p", {}, "The desktop app passes it automatically (boot cookie). " +
        "In a browser, paste this backend's launch token once; it stays for this session."),
      el("div", { style: { display: "flex", gap: "10px", justifyContent: "center", marginTop: "16px" } },
        input,
        el("button", { class: "btn primary", onclick: go }, "Continue")),
      sessionStorage.getItem("jmdb_token") ? el("p", { style: { fontSize: "12px" } }, "(the previous token was rejected — a new launch has a new token)") : null));
  input.focus();
}

async function boot() {
  buildNav();
  wireTopbar();
  wireGlobalEvents();
  try {
    await loadSettings();
    store.appInfo = await api.get("/api/app/info");
  } catch (error) {
    if (error.status === 401) {
      renderTokenGate();
      return;
    }
    page().append(
      el("div", { class: "error-note" }, `Backend unreachable: ${error.message}. Retrying…`));
    setTimeout(boot, 2000);
    return;
  }
  connectEvents();
  // Polling fallback for scan status: covers WebSocket outages (missing
  // websockets package, reconnect windows) with the SAME reporting path as
  // the WS events — pill while running, one deduplicated finish toast.
  let pollerSawRunning = false;
  setInterval(async () => {
    try {
      const status = await api.get("/api/scan/status");
      const pill = document.getElementById("scan-pill");
      if (status.running) {
        pollerSawRunning = true;
        pill.classList.remove("hidden");
        const text = document.getElementById("scan-pill-text");
        if (text) {
          text.textContent = `Scanning… ${status.files_indexed || 0} files` +
            (status.phase && status.phase !== "indexing" ? ` (${status.phase})` : "");
        }
      } else {
        pill.classList.add("hidden");
        // only report a finish the poller itself witnessed starting; the WS
        // path reports its own (both funnel through the dedup signature)
        if (pollerSawRunning && status.last_result) {
          pollerSawRunning = false;
          reportScanFinished(status.last_result);
        } else {
          pollerSawRunning = false;
        }
      }
    } catch {
      /* backend restarting */
    }
  }, 2000);

  if (!location.hash) location.hash = "#/home";
  else renderRoute(currentRoute());
}

boot();
