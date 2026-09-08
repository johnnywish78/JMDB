import { api } from "../api.js";
import { el, clear, toast, confirmDialog, promptDialog, formatBytes } from "../ui.js";
import { store, saveSettings, on } from "../store.js";
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
  const locationsList = el("div", {});
  const renderLocations = (locations, summaryData) => {
    clear(locationsList);
    for (const location of locations || []) {
      locationsList.append(el("div", { class: "location-row" },
        el("span", { class: "path", title: location.path }, location.path),
        el("span", { class: "status" }, `${location.file_count || 0} files · ${location.last_scan_status || "never scanned"}`),
        el("button", {
          class: "btn small",
          onclick: async () => {
            try {
              await api.post(`/api/scan?location_id=${location.id}`, {});
              toast(`Scan started for ${location.path}`, "success");
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
    if (!(locations || []).length) {
      locationsList.append(el("div", { class: "hint" }, "No locations yet — add a folder below."));
    }
    const summary = summaryData || {};
    locationsList.append(el("div", { style: { marginTop: "14px", color: "var(--text-dim)", fontSize: "12.5px" } },
      `Library: ${summary.movies ?? 0} movies · ${summary.shows ?? 0} shows · ${summary.episodes ?? 0} episodes · ` +
      `${summary.albums ?? 0} albums · ${summary.tracks ?? 0} tracks · ${summary.missing ?? 0} missing files`));
  };
  renderLocations(library.locations, library.summary);
  librarySection.append(locationsList);

  // live scan status row (WS events + /api/scan/status fallback)
  const scanStatus = el("div", { class: "scan-status hidden" });
  librarySection.append(scanStatus);
  const updateScanStatus = (status) => {
    if (status && status.running) {
      scanStatus.classList.remove("hidden");
      const phase = status.phase === "matching" ? "matching media" : status.phase === "artwork" ? "attaching artwork" : "indexing files";
      scanStatus.textContent = `Scanning — ${phase} · ${status.files_seen || 0} files seen · ${status.files_indexed || 0} indexed`;
    } else {
      scanStatus.classList.add("hidden");
    }
  };
  updateScanStatus(await api.get("/api/scan/status").catch(() => null));
  // live updates while the settings page is open
  const offProgress = on("scan_progress", (data) => updateScanStatus({
    running: true, phase: data.phase, files_seen: data.files_seen, files_indexed: data.files_indexed,
  }));
  const offFinished = on("scan_finished", async () => {
    updateScanStatus(null);
    try {
      const fresh = await api.get("/api/library");
      renderLocations(fresh.locations, fresh.summary);
    } catch { /* page navigation handles refresh */ }
  });
  const offWatcher = setInterval(() => {
    if (!container.isConnected) {
      offProgress(); offFinished(); clearInterval(offWatcher);
    }
  }, 2000);

  const addRow = el("div", { style: { display: "flex", gap: "10px", marginTop: "12px" } });
  const pathInput = el("input", { class: "input", placeholder: "/path/to/media folder (or Browse…)", style: { flex: "1" } });
  addRow.append(
    pathInput,
    el("button", {
      class: "btn", title: "Choose a folder with the native picker",
      onclick: async () => {
        if (!window.jmdb?.dialog?.pickFolder) {
          toast("Folder picker is available in the desktop app — type a path instead", "info");
          return;
        }
        const picked = await window.jmdb.dialog.pickFolder();
        if (picked) { pathInput.value = picked; pathInput.focus(); }
      },
    }, "Browse…"),
    el("button", {
      class: "btn primary", onclick: async () => {
        const path = pathInput.value.trim();
        if (!path) return;
        try {
          const result = await api.post("/api/library/locations", { path });
          // only real success gets a success toast; the API raises 400/409 otherwise
          pathInput.value = "";
          toast(result.message || "Location added — run a scan to index it", "success");
          renderLocations(result.locations, library.summary);
        } catch (error) {
          toast(error.status === 409 ? "Already in your library" : `Couldn't add: ${error.message}`, "error");
        }
      },
    }, "Add location"),
    el("button", {
      class: "btn", onclick: async () => {
        try {
          await api.post("/api/scan", {});
          toast("Full scan started", "success");
          updateScanStatus({ running: true, phase: "indexing", files_seen: 0, files_indexed: 0 });
        } catch (error) {
          toast(error.status === 409 ? "A scan is already running" : error.message, "error");
        }
      },
    }, "Scan everything"));
  librarySection.append(addRow);
  container.append(librarySection);

  /* ------------------------------------------------ playback */
  const playbackSection = section("Playback", "Player behavior. The backend owns resume, watched-marking and next-episode decisions.");
  playbackSection.append(
    toggleRow("Autoplay next episode", "Continue to the next episode when one ends", "autoplay_next", values.autoplay_next),
    numberRow("Default volume", "Player volume percent (0–100)", "player_default_volume", values.player_default_volume, 0, 100),
    numberRow("Seek step", "Seconds the ←/→/J/L keys jump in the player", "seek_step_seconds", values.seek_step_seconds, 1, 120),
    numberRow("Volume step", "Percent the ↑/↓ keys change the volume", "volume_step", values.volume_step, 1, 50),
    textRow("Default subtitle language", "Two-letter language code (e.g. en, de) — matching subtitles are selected automatically when playback starts", "default_subtitle_language", values.default_subtitle_language),
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
  browserSection.append(numberRow("Default zoom for new tabs", "Percent (50–300). Existing tabs keep their own zoom.", "browser_default_zoom", values.browser_default_zoom, 50, 300));
  browserSection.append(toggleRow(
    "Allow cookies in Browser Hub",
    "Applies to the hub session immediately; off also affects new sites you open",
    "browser_allow_cookies", values.browser_allow_cookies,
    (value) => window.jmdb?.hub?.setCookiesEnabled(value !== false)));
  browserSection.append(toggleRow(
    "Enable JavaScript",
    "Affects tabs opened from now on (restored tabs keep their setting)",
    "browser_enable_javascript", values.browser_enable_javascript,
    (value) => window.jmdb?.hub?.setJavaScriptEnabled(value !== false)));
  container.append(browserSection);

  /* ------------------------------------------------ metadata */
  const metaSection = section("Metadata & artwork", "Where JMDB gets its data. Movies/TV/people are queried in the order shown until a provider answers; music uses the music chain. Providers without a key are skipped honestly — local file metadata is always kept. TV Time and EMDB have no public API and are never queried.");
  try {
    const catalog = await api.get("/api/providers");
    metaSection.append(el("div", { class: "provider-chains" },
      el("div", { class: "chain" },
        el("span", { class: "chain-label" }, "Movies / TV: "),
        (catalog.movie_tv_chain || []).map((id, i) => el("span", { class: "chain-item" }, `${i ? " → " : ""}${id}`))),
      el("div", { class: "chain" },
        el("span", { class: "chain-label" }, "Music: "),
        (catalog.music_chain || []).map((id, i) => el("span", { class: "chain-item" }, `${i ? " → " : ""}${id}`)))));
    for (const provider of catalog.items || []) {
      metaSection.append(providerCard(provider));
    }
  } catch (error) {
    metaSection.append(el("div", { class: "hint" }, `Provider catalog unavailable: ${error.message}`));
  }
  metaSection.append(
    toggleRow("Auto-refresh metadata", "Not active in this build — the value is saved for when background enrichment ships; metadata comes from local files and provider keys above", "auto_enrich_metadata", values.auto_enrich_metadata),
    numberRow("Refresh after days", "Not active in this build — saved for future background enrichment", "auto_refresh_metadata_days", values.auto_refresh_metadata_days, 1, 365),
    textRow("Metadata language", "Not active in this build — providers currently answer in English; the value is saved for future use", "metadata_language", values.metadata_language));
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

/** One provider row: honest state, masked key, save + real Test action. */
function providerCard(provider) {
  const card = el("div", { class: `provider-card ${provider.configured ? "ok" : ""}` });

  const state = provider.requires_key
    ? (provider.configured
        ? el("span", { class: "badge good" }, `key set${provider.key_source ? ` (${provider.key_source})` : ""}`)
        : el("span", { class: "badge" }, "API key required"))
    : el("span", { class: "badge good" }, provider.id === "tvtime" ? "no public API" : "no key needed");

  const head = el("div", { class: "setting-row" },
    el("div", { class: "labels" },
      el("div", { class: "t" },
        el("a", { href: provider.website || "#", target: "_blank", rel: "noreferrer noopener" }, provider.name),
        " ", state),
      el("div", { class: "s" }, provider.supplies || "")),
    el("span", { class: "provider-used-for" }, provider.used_for || ""));
  card.append(head);

  if (provider.id === "tvtime") {
    card.append(el("div", { class: "hint" },
      "TV Time has no public API — it opens as a website from Services; nothing to configure here."));
    return card;
  }
  if (provider.health && provider.health.last_error) {
    card.append(el("div", { class: "hint provider-error" }, `Last provider error: ${provider.health.last_error}`));
  }

  const input = el("input", {
    class: "input", type: "password", autocomplete: "off", spellcheck: "false",
    placeholder: provider.key_masked ? `current: ${provider.key_masked}` : "paste API key",
    style: { width: "240px" },
  });
  const result = el("span", { class: "provider-test-result" });
  const saveBtn = el("button", {
    class: "btn small",
    onclick: async () => {
      const value = input.value.trim();
      if (!value && !provider.key_masked) { result.textContent = ""; return; }
      try {
        const res = await api.put(`/api/providers/${provider.id}/key`, { key: value });
        input.value = "";
        input.placeholder = `current: ${res.key_masked}`;
        result.textContent = "";
        toast(res.message || "Key saved", "success");
        navigate("/settings"); // refresh configured badges honestly
      } catch (error) {
        toast(`Couldn't save key: ${error.message}`, "error");
      }
    },
  }, provider.key_masked ? "Update key" : "Save key");

  const testBtn = provider.testable ? el("button", {
    class: "btn small",
    onclick: async () => {
      result.textContent = "testing…";
      result.className = "provider-test-result";
      try {
        const candidate = input.value.trim();
        const res = await api.post(`/api/providers/${provider.id}/test`, candidate ? { key: candidate } : {});
        result.textContent = `${res.ok ? "✓" : "✗"} ${res.detail || ""}`;
        result.className = `provider-test-result ${res.ok ? "good" : "bad"}`;
      } catch (error) {
        result.textContent = `✗ ${error.message}`;
        result.className = "provider-test-result bad";
      }
    },
  }, "Test") : null;

  const controls = el("div", { class: "provider-controls" }, input, saveBtn);
  if (testBtn) controls.append(testBtn);
  controls.append(result);
  if (provider.env_var) {
    controls.append(el("span", { class: "provider-env" }, `env override: ${provider.env_var}`));
  }
  card.append(controls);
  return card;
}

async function persist(patch) {
  await saveSettings(patch);
}

function toggleRow(title, subtitle, key, value, onApply = null) {
  const input = el("input", { type: "checkbox" });
  input.checked = value !== false && value !== 0;
  input.addEventListener("change", async () => {
    try {
      await persist({ [key]: input.checked });
      // live-apply hook (e.g. Browser Hub policy changes) — only after the
      // value is actually saved; silently skipped where the bridge is absent
      if (onApply) await onApply(input.checked);
    } catch {
      /* persist shows its own error toast */
    }
  });
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
