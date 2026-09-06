import { api } from "../api.js";
import { el, toast, confirmDialog, promptDialog, formatBytes } from "../ui.js";
import { store, saveSettings } from "../store.js";
import { navigate } from "../router.js";

export default async function render(container) {
  const [settings, library, appInfo] = await Promise.all([
    api.get("/api/settings"),
    api.get("/api/library"),
    api.get("/api/app/info"),
  ]);
  const values = settings.values || {};
  const schema = (settings.schema && settings.schema.fields) || [];

  container.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Settings"),
      el("div", { class: "sub" }, "Appearance, library, playback and metadata"))));

  /* ------------------------------------------------ appearance */
  const appearance = section("Appearance", "Dark, light or follow your system. The choice is saved to your profile and applied on every start.");
  const themeRow = el("div", { class: "setting-row" },
    el("div", { class: "labels" }, el("div", { class: "t" }, "Theme"), el("div", { class: "s" }, "Applies immediately")),
    el("div", { class: "chip-row" },
      ...["dark", "light", "system"].map((theme) => {
        const chip = el("button", { class: `chip ${(values.theme || "system") === theme ? "active" : ""}` }, theme[0].toUpperCase() + theme.slice(1));
        chip.addEventListener("click", async () => {
          await saveSettings({ theme });
          navigate("/settings");
        });
        return chip;
      })));
  appearance.append(themeRow);
  container.append(appearance);

  /* ------------------------------------------------ library */
  const librarySection = section("Library locations", "Folders JMDB scans for movies, TV and music. Add a folder, then scan it.");
  for (const location of library.locations || []) {
    librarySection.append(el("div", { class: "location-row" },
      el("span", { class: "path", title: location.path }, location.path),
      el("span", { class: "status" }, `${location.file_count || 0} files · ${location.last_scan_status || "never scanned"}`),
      el("button", {
        class: "btn small",
        onclick: async () => {
          try {
            await api.post(`/api/scan?location_id=${location.id}`, {});
            toast("Scan started", "success");
          } catch (error) {
            toast(error.status === 409 ? "A scan is already running" : error.message, "error");
          }
        },
      }, "Scan"),
      el("button", {
        class: "btn small danger",
        onclick: async () => {
          const sure = await confirmDialog({
            title: "Remove this location?",
            body: `JMDB will stop scanning ${location.path}. Files already in your library are kept.`,
            confirmLabel: "Remove", danger: true,
          });
          if (sure) {
            await api.del(`/api/library/locations/${location.id}`);
            navigate("/settings");
          }
        },
      }, "Remove")));
  }
  const addRow = el("div", { style: { display: "flex", gap: "10px", marginTop: "12px" } });
  const pathInput = el("input", { class: "input", placeholder: "/path/to/media folder", style: { flex: "1" } });
  addRow.append(
    pathInput,
    el("button", {
      class: "btn primary", onclick: async () => {
        const path = pathInput.value.trim();
        if (!path) return;
        try {
          await api.post("/api/library/locations", { path });
          pathInput.value = "";
          toast("Location added — run a scan to index it", "success");
          navigate("/settings");
        } catch (error) {
          toast(`Couldn't add: ${error.message}`, "error");
        }
      },
    }, "Add location"),
    el("button", {
      class: "btn", onclick: async () => {
        try {
          await api.post("/api/scan", {});
          toast("Full scan started", "success");
        } catch (error) {
          toast(error.status === 409 ? "A scan is already running" : error.message, "error");
        }
      },
    }, "Scan everything"));
  librarySection.append(addRow);
  const summary = library.summary || {};
  librarySection.append(el("div", { style: { marginTop: "14px", color: "var(--text-dim)", fontSize: "12.5px" } },
    `Library: ${summary.movies ?? 0} movies · ${summary.shows ?? 0} shows · ${summary.episodes ?? 0} episodes · ` +
    `${summary.albums ?? 0} albums · ${summary.tracks ?? 0} tracks · ${summary.missing ?? 0} missing files`));
  container.append(librarySection);

  /* ------------------------------------------------ playback */
  const playbackSection = section("Playback", "Player behavior. The backend owns resume, watched-marking and next-episode decisions.");
  playbackSection.append(
    toggleRow("Autoplay next episode", "Continue to the next episode when one ends", "autoplay_next", values.autoplay_next),
    numberRow("Default volume", "Player volume percent (0–100)", "player_default_volume", values.player_default_volume, 0, 100),
    numberRow("Mark watched at", "Percentage of the file after which an item counts as watched", "mark_watched_pct", values.mark_watched_pct, 10, 100),
    numberRow("Resume threshold", "Minimum seconds before we offer to resume", "resume_min_seconds", values.resume_min_seconds, 0, 600),
    textRow("External player", "Optional path to an external player (mpv/VLC). Leave empty for auto-detect.", "external_player_path", values.external_player_path));
  container.append(playbackSection);

  /* ------------------------------------------------ browser */
  const browserSection = section("Browser Hub", "The embedded multi-tab browser. Site logins persist in the app's own session partition.");
  const engineRow = el("div", { class: "setting-row" },
    el("div", { class: "labels" }, el("div", { class: "t" }, "Search engine"), el("div", { class: "s" }, "Used for address-bar searches")),
    (() => {
      const select = el("select", { class: "select" },
        ...["duckduckgo", "google", "bing", "brave", "startpage"].map((engine) =>
          el("option", { value: engine, selected: engine === (values.browser_search_engine || "duckduckgo") ? "selected" : null }, engine[0].toUpperCase() + engine.slice(1))));
      select.addEventListener("change", async () => {
        await saveSettings({ browser_search_engine: select.value });
        toast("Search engine saved", "success");
      });
      return select;
    })());
  browserSection.append(engineRow);
  browserSection.append(toggleRow("Allow cookies in Browser Hub", "Persistent logins via the app session partition", "browser_allow_cookies", values.browser_allow_cookies));
  browserSection.append(toggleRow("Enable JavaScript", "Disabling breaks most modern sites", "browser_enable_javascript", values.browser_enable_javascript));
  container.append(browserSection);

  /* ------------------------------------------------ metadata */
  const metaSection = section("Metadata & artwork", "Providers JMDB queries for movie/show/music details. TMDB and OMDb need free API keys; without keys only local file metadata is used. TV Time and EMDB have no public API and are never queried.");
  const providerNote = el("div", { class: "setting-row" },
    el("div", { class: "labels" },
      el("div", { class: "t" }, "Provider keys"),
      el("div", { class: "s" }, "Stored via your environment/secrets — the app never logs them.")));
  metaSection.append(providerNote);
  metaSection.append(
    toggleRow("Auto-refresh metadata", "Refresh stale details automatically when items appear", "auto_enrich_metadata", values.auto_enrich_metadata),
    numberRow("Refresh after days", "Re-query metadata older than this many days", "auto_refresh_metadata_days", values.auto_refresh_metadata_days, 1, 365),
    textRow("Metadata language", "Preferred language for titles and overviews (e.g. en-US, de-DE)", "metadata_language", values.metadata_language));
  container.append(metaSection);

  /* ------------------------------------------------ notifications */
  const notifSection = section("Notifications", "In-app toasts for background work.");
  notifSection.append(
    toggleRow("Scan notifications", "Tell me when scans finish", "notify_scan", values.notify_scan),
    toggleRow("Metadata notifications", "Tell me when metadata updates", "notify_metadata", values.notify_metadata));
  container.append(notifSection);

  /* ------------------------------------------------ about */
  const about = section("About", "");
  about.append(el("div", { class: "setting-row" },
    el("div", { class: "labels" },
      el("div", { class: "t" }, `JMDB ${appInfo.version || ""}`),
      el("div", { class: "s" },
        `Python ${appInfo.python || "?"} · ${appInfo.platform || ""} · database at ${appInfo.database_path || "?"}`))));
  if (window.jmdb?.app?.info) {
    window.jmdb.app.info().then((info) => {
      about.append(el("div", { class: "setting-row" },
        el("div", { class: "labels" },
          el("div", { class: "t" }, `Electron ${info.electron || ""}`),
          el("div", { class: "s" }, `Chromium ${info.chrome || ""} · external browsers: ${(info.externalBrowsers || []).join(", ") || "none detected"}`))));
    }).catch(() => {});
  }
  container.append(about);
}

/* ------------------------------------------------------------ helpers */
function section(title, hint) {
  return el("div", { class: "settings-section" },
    el("h3", {}, title),
    hint ? el("p", { class: "hint" }, hint) : el("span"));
}

async function persist(patch) {
  await saveSettings(patch);
}

function toggleRow(title, subtitle, key, value) {
  const input = el("input", { type: "checkbox" });
  input.checked = value !== false && value !== 0;
  input.addEventListener("change", () => persist({ [key]: input.checked }));
  return el("div", { class: "setting-row" },
    el("div", { class: "labels" }, el("div", { class: "t" }, title), el("div", { class: "s" }, subtitle)),
    el("label", { class: "switch" }, input, el("span", { class: "track" }), el("span", { class: "thumb" })));
}

function numberRow(title, subtitle, key, value, min, max) {
  const input = el("input", { class: "input", type: "number", min: String(min), max: String(max), value: String(value ?? ""), style: { width: "110px" } });
  input.addEventListener("change", () => {
    const parsed = Number(input.value);
    if (Number.isFinite(parsed)) persist({ [key]: parsed });
  });
  return el("div", { class: "setting-row" },
    el("div", { class: "labels" }, el("div", { class: "t" }, title), el("div", { class: "s" }, subtitle)),
    input);
}

function textRow(title, subtitle, key, value) {
  const input = el("input", { class: "input", type: "text", value: value ?? "", style: { width: "260px" } });
  input.addEventListener("change", () => persist({ [key]: input.value }));
  return el("div", { class: "setting-row" },
    el("div", { class: "labels" }, el("div", { class: "t" }, title), el("div", { class: "s" }, subtitle)),
    input);
}
