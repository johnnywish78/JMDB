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
      return;
    }
  }
  navigate("/home");
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
    document.getElementById("scan-pill").classList.remove("hidden");
  });
  on("scan_progress", (data) => {
    const pill = document.getElementById("scan-pill");
    pill.classList.remove("hidden");
    const text = document.getElementById("scan-pill-text");
    if (text) text.textContent = data.current_path ? `Scanning ${data.current_path.split("/").pop()}…` : "Scanning…";
  });
  const hidePill = () => document.getElementById("scan-pill").classList.add("hidden");
  on("scan_finished", (data) => {
    hidePill();
    if (data && data.result) {
      const result = data.result;
      toast(
        `Scan finished: ${result.files_indexed || 0} files indexed, ` +
        `${result.movies_added || 0} movies / ${result.shows_added || 0} shows / ` +
        `${result.episodes_added || 0} episodes / ${result.tracks_added || 0} tracks added`,
        "success");
      refreshCurrentPage();
    }
  });
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
async function boot() {
  buildNav();
  wireTopbar();
  wireGlobalEvents();
  try {
    await loadSettings();
    store.appInfo = await api.get("/api/app/info");
  } catch (error) {
    page().append(
      el("div", { class: "error-note" }, `Backend unreachable: ${error.message}. Retrying…`));
    setTimeout(boot, 2000);
    return;
  }
  connectEvents();
  // polling fallback for scan status (in case WS reconnects late)
  setInterval(async () => {
    try {
      const status = await api.get("/api/scan/status");
      const pill = document.getElementById("scan-pill");
      if (status.running) {
        pill.classList.remove("hidden");
        const text = document.getElementById("scan-pill-text");
        if (text) text.textContent = `Scanning… ${status.files_seen || 0} files`;
      } else {
        pill.classList.add("hidden");
      }
    } catch {
      /* backend restarting */
    }
  }, 5000);

  if (!location.hash) location.hash = "#/home";
  else renderRoute(currentRoute());
}

boot();
