/** Browser Hub page (renderer side). The actual web content renders in
 * native WebContentsView tabs owned by the main process; this page draws the
 * tab strip + toolbar, syncs the content bounds, and hosts the overlays
 * (find bar, downloads, history, DRM notice). When the user navigates to any
 * other app page, the views are hidden. */
import { api } from "../api.js";
import { el, clear, icon, toast, confirmDialog } from "../ui.js";
import { store, saveSettings } from "../store.js";
import { SEARCH_ENGINES, resolveAddressInput } from "../address.js";

export default async function render(container, route) {
  const hub = window.jmdb?.hub;
  if (!hub) {
    container.append(el("div", { class: "error-note" },
      "The Browser Hub is only available inside the JMDB desktop app (Electron). Start it with `python run.py`."));
    return;
  }

  container.classList.add("full-bleed");
  await hub.setVisible(true);
  // keep main's new-tab zoom in sync with the profile setting
  if (store.settings.browser_default_zoom) {
    hub.setDefaultZoom(store.settings.browser_default_zoom).catch(() => {});
  }
  // live browser-policy settings (Settings page persists them; the hub applies)
  if (typeof store.settings.browser_allow_cookies !== "undefined") {
    hub.setCookiesEnabled(store.settings.browser_allow_cookies !== false).catch(() => {});
  }
  if (typeof store.settings.browser_enable_javascript !== "undefined") {
    hub.setJavaScriptEnabled(store.settings.browser_enable_javascript !== false).catch(() => {});
  }

  const engineKey = store.settings.browser_search_engine || "duckduckgo";
  const engine = SEARCH_ENGINES[engineKey] || SEARCH_ENGINES.duckduckgo;
  /** Resolve address-bar input against the CONFIGURED search engine:
   * URLs/domains pass through; anything else becomes a search URL. */
  const resolveInput = (input) => resolveAddressInput(input, engine);

  /* ------------------------------------------------------------- DOM */
  const root = el("div", { class: "hub" });
  const tabsRow = el("div", { class: "hub-tabs" });
  const toolbar = el("div", { class: "hub-toolbar" });
  const favBar = el("div", { class: "hub-favs hidden" });
  const content = el("div", { class: "hub-content" });
  root.append(tabsRow, toolbar, favBar, content);
  container.append(root);

  // back / forward / reload / home
  const backBtn = navButton("M15 5l-7 7 7 7", "Back (Alt+←)");
  const forwardBtn = navButton("M9 5l7 7-7 7", "Forward (Alt+→)");
  const reloadBtn = navButton("M21 12a9 9 0 1 1-3-6.7M21 3v6h-6", "Reload (Ctrl+R)");
  const homeBtn = navButton("M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5", "Home");

  // address bar
  const lockIcon = el("span", { class: "lock" });
  lockIcon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>`;
  const addressInput = el("input", {
    type: "text", placeholder: `Search with ${store.settings.browser_search_engine || "DuckDuckGo"} or enter address`,
    spellcheck: "false", autocomplete: "off",
  });
  const addressBar = el("div", { class: "addressbar" }, lockIcon, addressInput);

  const zoomBadge = el("span", { class: "badge hidden", title: "Zoom (Ctrl+/-/0)" }, "100%");
  const findBtn = toolbarButton("Find in page (Ctrl+F)", "M11 4a7 7 0 0 1 7 7 7 7 0 0 1-7 7 7 7 0 0 1-7-7 7 7 0 0 1 7-7zM20 20l-3.5-3.5");
  const downloadsBtn = toolbarButton("Downloads", "M12 3v12m0 0l-4.5-4.5M12 15l4.5-4.5M4 20h16");
  const historyBtn = toolbarButton("History", "M3 12a9 9 0 1 0 3-6.7M3 3v6h6M12 7v5l3.5 2");
  const bookmarkBtn = toolbarButton("Bookmark this page", "M6 3.5h12V21l-6-4.2L6 21z");
  const externalBtn = toolbarButton("Open in external browser", "M14 4h6v6M20 4l-9 9M19 13v6a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6");
  const zoomOutBtn = toolbarButton("Zoom out (Ctrl+-)", "M5 12h14");
  const zoomInBtn = toolbarButton("Zoom in (Ctrl+=)", "M12 5v14M5 12h14");
  const pinBtn = toolbarButton("Pin this tab as a favorite", "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z");
  const menuBtn = toolbarButton("Browser menu", "M4 6h16M4 12h16M4 18h16");
  const passwordsBtn = toolbarButton("Password vault", "M6 11h12v9H6zM9 11V8a3 3 0 0 1 6 0v3");

  toolbar.append(backBtn, forwardBtn, reloadBtn, homeBtn, addressBar,
    zoomOutBtn, zoomInBtn, zoomBadge,
    findBtn, downloadsBtn, historyBtn, bookmarkBtn, pinBtn, externalBtn, passwordsBtn, menuBtn);

  const underlay = el("div", { class: "underlay" },
    el("div", {},
      el("h3", {}, "Browser Hub"),
      el("p", { style: { color: "var(--text-dim)", lineHeight: "1.6" } },
        "Multi-tab browsing with a persistent session — logins to your services survive restarts. "),
      el("p", { style: { color: "var(--text-faint)", fontSize: "12.5px" } },
        "Ctrl+T new tab · Ctrl+W close · Ctrl+L address · Ctrl+F find · Ctrl+= zoom")));
  content.append(underlay);

  /* ------------------------------------------------------------- state */
  let tabs = [];
  let activeTab = null;
  let findOpen = false;
  let downloadsOpen = false;
  let historyOpen = false;
  let vaultOpen = false;
  let vaultEntries = [];
  let vaultBackendName = "";
  let downloads = [];
  let findCount = { activeMatchOrdinal: 0, matches: 0 };

  /* ------------------------------------------------------------- wiring */
  backBtn.addEventListener("click", () => hub.back());
  forwardBtn.addEventListener("click", () => hub.forward());
  reloadBtn.addEventListener("click", () => hub.reload());
  homeBtn.addEventListener("click", () => hub.navigate("https://duckduckgo.com"));
  externalBtn.addEventListener("click", () => {
    if (activeTab?.url) window.jmdb.external.open(activeTab.url);
  });
  zoomInBtn.addEventListener("click", () => hub.zoom("in").then(refreshZoom));
  zoomOutBtn.addEventListener("click", () => hub.zoom("out").then(refreshZoom));
  pinBtn.addEventListener("click", () => { if (activeTab) hub.togglePin(activeTab.id); });
  menuBtn.addEventListener("click", () => toggleMenu());

  addressInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") hub.navigate(resolveInput(addressInput.value));
    if (event.key === "Escape") addressInput.blur();
  });
  addressInput.addEventListener("focus", () => addressInput.select());

  bookmarkBtn.addEventListener("click", async () => {
    if (!activeTab?.url) return;
    try {
      await api.post("/api/bookmarks", { title: activeTab.title || activeTab.url, url: activeTab.url });
      bookmarkBtn.style.color = "var(--accent)";
    } catch (error) {
      console.warn("bookmark failed", error);
    }
  });

  findBtn.addEventListener("click", () => toggleFind(true));
  downloadsBtn.addEventListener("click", () => { downloadsOpen = !downloadsOpen; renderDownloads(); });
  passwordsBtn.addEventListener("click", async () => {
    vaultOpen = !vaultOpen;
    if (vaultOpen) await loadVault();
    renderVault();
  });
  historyBtn.addEventListener("click", async () => {
    historyOpen = !historyOpen;
    if (historyOpen) await renderHistory();
    else historyPanel?.remove(), (historyPanel = null);
  });

  // keyboard shortcuts (when the toolbar/page has focus; web content focus is
  // handled by the main process via before-input-event)
  const keyHandler = (event) => {
    if (!container.isConnected) {
      document.removeEventListener("keydown", keyHandler);
      return;
    }
    const ctrl = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();
    if (event.altKey && event.key === "ArrowLeft") { event.preventDefault(); hub.back(); }
    else if (event.altKey && event.key === "ArrowRight") { event.preventDefault(); hub.forward(); }
    else if (ctrl && key === "t") { event.preventDefault(); hub.createTab("https://duckduckgo.com"); }
    else if (ctrl && key === "w") { event.preventDefault(); hub.closeTab(activeTab?.id); }
    else if (ctrl && key === "l") { event.preventDefault(); addressInput.focus(); }
    else if (ctrl && key === "r") { event.preventDefault(); hub.reload(); }
    else if (ctrl && key === "f") { event.preventDefault(); toggleFind(true); }
    else if (ctrl && key === "p") { event.preventDefault(); hub.print(); }
    else if (ctrl && event.key === "Tab") { event.preventDefault(); hub.switchTab(event.shiftKey ? -1 : 1); }
    else if (ctrl && (event.key === "+" || event.key === "=")) { event.preventDefault(); hub.zoom("in").then(refreshZoom); }
    else if (ctrl && key === "-") { event.preventDefault(); hub.zoom("out").then(refreshZoom); }
    else if (ctrl && key === "0") { event.preventDefault(); hub.zoom("reset").then(refreshZoom); }
    else if (event.key === "F5") { event.preventDefault(); hub.reload(); }
  };
  document.addEventListener("keydown", keyHandler);

  /* ------------------------------------------------------------- bounds */
  const reportBounds = () => {
    const rect = content.getBoundingClientRect();
    hub.setBounds({ x: rect.x, y: rect.y, width: rect.width, height: rect.height });
  };
  const observer = new ResizeObserver(reportBounds);
  observer.observe(content);
  reportBounds();

  /* ------------------------------------------------------------- tabs UI */
  function renderTabs() {
    clear(tabsRow);
    for (const tab of tabs) {
      const node = el("div", { class: `hub-tab ${tab.id === activeTab?.id ? "active" : ""}`, onclick: () => hub.activateTab(tab.id) });
      if (tab.loading) {
        node.append(el("span", { class: "spin" }));
      } else if (tab.favicon) {
        node.append(el("img", { class: "favicon", src: tab.favicon, onerror: "this.style.display='none'" }));
      } else {
        const globe = el("span", { class: "favicon" });
        globe.textContent = "◉";
        node.append(globe);
      }
      if (tab.pinned) node.append(el("span", { class: "pin-star", title: "Pinned favorite" }, "★"));
      node.append(el("span", { class: "label" }, tab.title || tab.url || "New tab"));
      const close = el("button", { class: "close", title: "Close tab (Ctrl+W)", onclick: (event) => { event.stopPropagation(); hub.closeTab(tab.id); } }, "×");
      node.append(close);
      tabsRow.append(node);
    }
    const newTab = el("button", { class: "hub-newtab", title: "New tab (Ctrl+T)", onclick: () => hub.createTab("https://duckduckgo.com") }, "+");
    tabsRow.append(newTab);
    underlay.style.display = tabs.length ? "none" : "grid";
  }

  function renderActive() {
    if (!activeTab) return;
    if (document.activeElement !== addressInput) {
      addressInput.value = activeTab.url || "";
    }
    const isHttps = String(activeTab.url || "").startsWith("https://");
    lockIcon.style.color = isHttps ? "var(--good)" : "var(--text-faint)";
    backBtn.disabled = !activeTab.canGoBack;
    pinBtn.classList.toggle("pinned", Boolean(activeTab.pinned));
    pinBtn.title = activeTab.pinned ? "Unpin this tab" : "Pin this tab as a favorite";
    refreshZoom();
    document.title = activeTab.title ? `${activeTab.title} — JMDB` : "JMDB";
  }

  async function refreshZoom() {
    const factor = (await hub.tabs().catch(() => []))
      .find((tab) => tab.id === activeTab?.id)?.zoom || 1;
    const pct = Math.round(factor * 100);
    zoomBadge.textContent = `${pct}%`;
    zoomBadge.classList.toggle("hidden", pct === 100);
  }

  /* ------------------------------------------------------------- find bar */
  let findBar = null;
  function toggleFind(open) {
    findOpen = open;
    if (!open) {
      findBar?.remove();
      findBar = null;
      hub.clearFind();
      return;
    }
    if (findBar) { findBar.querySelector("input").focus(); return; }
    const input = el("input", { type: "text", placeholder: "Find in page…" });
    const count = el("span", { class: "count" }, "0/0");
    const prev = el("button", { class: "find-nav", title: "Previous (Shift+Enter)" }, "↑");
    const next = el("button", { class: "find-nav", title: "Next (Enter)" }, "↓");
    const close = el("button", { class: "find-nav", title: "Close (Esc)" }, "×");
    findBar = el("div", { class: "hub-findbar" }, input, count, prev, next, close);
    content.append(findBar);
    input.focus();
    const run = (forward) => hub.find(input.value, { forward, findNext: findBar.dataset.searched === "1" });
    input.addEventListener("input", () => { findBar.dataset.searched = ""; run(true); });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); run(!event.shiftKey); findBar.dataset.searched = "1"; }
      if (event.key === "Escape") toggleFind(false);
    });
    prev.addEventListener("click", () => { run(false); findBar.dataset.searched = "1"; });
    next.addEventListener("click", () => { run(true); findBar.dataset.searched = "1"; });
    close.addEventListener("click", () => toggleFind(false));
  }

  /* ------------------------------------------------------------- downloads */
  let downloadsPanel = null;
  function renderDownloads() {
    downloadsPanel?.remove();
    downloadsPanel = null;
    if (!downloadsOpen) return;
    downloadsPanel = el("div", { class: "hub-downloads" }, el("h4", {}, `Downloads (${downloads.length})`));
    for (const item of downloads.slice(0, 30)) {
      const pct = item.total ? Math.round((item.received / item.total) * 100) : 0;
      const row = el("div", { class: "dl-row" },
        el("div", { class: "top" },
          el("span", { class: "name", title: item.filename }, item.filename),
          el("span", { class: "state" }, item.state)),
        item.state === "progressing" ? el("div", { class: "bar" }, el("span", { style: { width: `${pct}%` } })) : null,
        el("div", { class: "actions" },
          item.state === "progressing" ? el("button", { class: "btn small", onclick: () => window.jmdb.downloads.pause(item.id) }, "Pause") : null,
          item.state === "paused" ? el("button", { class: "btn small", onclick: () => window.jmdb.downloads.resume(item.id) }, "Resume") : null,
          item.state === "progressing" ? el("button", { class: "btn small danger", onclick: () => window.jmdb.downloads.cancel(item.id) }, "Cancel") : null,
          item.state === "completed" ? el("button", { class: "btn small", onclick: () => window.jmdb.downloads.openInFolder(item.id) }, "Show in folder") : null));
      downloadsPanel.append(row);
    }
    if (!downloads.length) downloadsPanel.append(el("div", { style: { color: "var(--text-dim)", fontSize: "12.5px" } }, "No downloads yet."));
    content.append(downloadsPanel);
  }

  /* ------------------------------------------------------------- password vault */
  let vaultPanel = null;
  let vaultQuery = "";

  async function loadVault() {
    if (!window.jmdb?.passwords) return;
    const result = await window.jmdb.passwords.list().catch(() => null);
    if (result && result.ok) {
      vaultEntries = result.entries || [];
      vaultBackendName = result.backend || "";
    }
  }

  function renderVault() {
    vaultPanel?.remove();
    vaultPanel = null;
    if (!vaultOpen) return;

    if (!window.jmdb?.passwords) {
      vaultPanel = el("div", { class: "hub-vault" },
        el("h4", {}, "Password vault"),
        el("p", { style: { color: "var(--text-dim)", fontSize: "12.5px" } },
          "The vault is only available inside the JMDB desktop app."));
      content.append(vaultPanel);
      return;
    }

    vaultPanel = el("div", { class: "hub-vault" });
    vaultPanel.append(el("h4", {}, `Password vault (${vaultEntries.length})`));
    vaultPanel.append(el("p", { class: "vault-backend" },
      vaultBackendName === "safeStorage"
        ? "Encrypted with your operating system's secure storage. No autofill — copy credentials when you need them."
        : "Encrypted with a local key file (OS secure storage unavailable). No autofill — copy credentials when you need them."));

    // search
    const rowsWrap = el("div", { class: "vault-rows" });
    const search = el("input", { class: "input", type: "text", placeholder: "Search domain or username…", value: vaultQuery,
      style: { width: "100%", marginBottom: "10px" } });
    search.addEventListener("input", () => { vaultQuery = search.value; renderVaultRows(); });
    vaultPanel.append(search);
    vaultPanel.append(rowsWrap);

    // add form
    const fDomain = el("input", { class: "input", type: "text", placeholder: "example.com" });
    const fUser = el("input", { class: "input", type: "text", placeholder: "username" });
    const fPass = el("input", { class: "input", type: "password", placeholder: "password" });
    const fNotes = el("input", { class: "input", type: "text", placeholder: "note (optional)" });
    const addBtn = el("button", { class: "btn small primary" }, "Add");
    addBtn.addEventListener("click", async () => {
      const result = await window.jmdb.passwords.add({
        domain: fDomain.value, username: fUser.value, password: fPass.value, notes: fNotes.value,
      }).catch(() => null);
      if (result && result.ok) {
        fDomain.value = fUser.value = fPass.value = fNotes.value = "";
        await loadVault();
        renderVaultRows();
        toast("Saved to the vault", "success");
      } else {
        toast(`Couldn't save: ${(result && result.error) || "vault error"}`, "error");
      }
    });
    vaultPanel.append(el("div", { class: "vault-add" },
      fDomain, fUser, fPass, fNotes, addBtn));

    function renderVaultRows() {
      clear(rowsWrap);
      const query = vaultQuery.trim().toLowerCase();
      const rows = vaultEntries.filter((entry) =>
        !query || entry.domain.toLowerCase().includes(query) || entry.username.toLowerCase().includes(query));
      if (!rows.length) {
        rowsWrap.append(el("div", { style: { color: "var(--text-dim)", fontSize: "12.5px" } },
          vaultEntries.length ? "No entries match your search." : "No saved credentials yet."));
      }
      for (const entry of rows) {
        rowsWrap.append(vaultRow(entry));
      }
    }

    function vaultRow(entry) {
      const secret = el("span", { class: "vault-secret", "aria-label": "password" }, "••••••••");
      let shown = false;
      const revealBtn = el("button", { class: "btn small", title: "Show password (explicit)" }, "Show");
      revealBtn.addEventListener("click", async () => {
        if (shown) { secret.textContent = "••••••••"; shown = false; revealBtn.textContent = "Show"; return; }
        const result = await window.jmdb.passwords.reveal(entry.id).catch(() => null);
        if (result && result.ok) {
          secret.textContent = result.password;
          shown = true;
          revealBtn.textContent = "Hide";
        } else {
          toast(`Couldn't reveal: ${(result && result.error) || "locked"}`, "error");
        }
      });
      const copyBtn = el("button", { class: "btn small", title: "Copy password to clipboard" }, "Copy");
      copyBtn.addEventListener("click", async () => {
        const result = await window.jmdb.passwords.copy(entry.id).catch(() => null);
        toast(result && result.ok ? "Password copied" : "Copy failed", result && result.ok ? "success" : "error");
      });
      const editBtn = el("button", { class: "btn small" }, "Edit");
      editBtn.addEventListener("click", () => {
        row.replaceWith(vaultEditRow(entry));
      });
      const delBtn = el("button", { class: "btn small danger" }, "Delete");
      delBtn.addEventListener("click", async () => {
        const sure = await confirmDialog({
          title: "Delete vault entry?",
          body: `Delete the saved credentials for ${entry.username} @ ${entry.domain}? This cannot be undone.`,
          confirmLabel: "Delete", danger: true,
        });
        if (!sure) return;
        const result = await window.jmdb.passwords.remove(entry.id).catch(() => null);
        if (result && result.ok) { await loadVault(); renderVaultRows(); toast("Entry deleted", "success"); }
        else toast("Couldn't delete the entry", "error");
      });
      const row = el("div", { class: "vault-row" },
        el("div", { class: "top" },
          el("span", { class: "name", title: `${entry.username} @ ${entry.domain}` }, entry.domain),
          el("span", { class: "user" }, entry.username)),
        secret,
        el("div", { class: "actions" }, revealBtn, copyBtn, editBtn, delBtn));
      return row;
    }

    function vaultEditRow(entry) {
      const fDomain = el("input", { class: "input", type: "text", value: entry.domain });
      const fUser = el("input", { class: "input", type: "text", value: entry.username });
      const fPass = el("input", { class: "input", type: "password", placeholder: "new password (leave blank to keep)" });
      const fNotes = el("input", { class: "input", type: "text", value: entry.notes || "" });
      const saveBtn = el("button", { class: "btn small primary" }, "Save");
      const row = el("div", { class: "vault-row editing" },
        el("div", { class: "vault-add" }, fDomain, fUser, fPass, fNotes, saveBtn));
      saveBtn.addEventListener("click", async () => {
        const fields = { domain: fDomain.value, username: fUser.value, notes: fNotes.value };
        if (fPass.value) fields.password = fPass.value;
        const result = await window.jmdb.passwords.update(entry.id, fields).catch(() => null);
        if (result && result.ok) { await loadVault(); renderVaultRows(); toast("Entry updated", "success"); }
        else toast(`Couldn't update: ${(result && result.error) || "vault error"}`, "error");
      });
      return row;
    }

    renderVaultRows();
    content.append(vaultPanel);
  }

  /* ------------------------------------------------------------- favorites bar */
  let favSignature = "";
  async function renderFavorites() {
    const favs = await hub.favorites().catch(() => []);
    clear(favBar);
    favBar.classList.toggle("hidden", !favs.length);
    for (const fav of favs) {
      favBar.append(el("button", {
        class: "fav-chip", title: fav.url,
        onclick: () => hub.navigate(fav.url),
      }, `★ ${fav.name || fav.url}`));
    }
  }

  /* ------------------------------------------------------------- hub menu */
  let menuPanel = null;
  function closeMenu() { menuPanel?.remove(); menuPanel = null; }
  async function toggleMenu(force) {
    if (force === false || menuPanel) { closeMenu(); return; }

    const engineSelect = el("select", { class: "select" },
      ...Object.keys(SEARCH_ENGINES).map((key) => el("option", {
        value: key,
        selected: key === (store.settings.browser_search_engine || "duckduckgo") ? "selected" : null,
      }, key[0].toUpperCase() + key.slice(1))));
    engineSelect.addEventListener("change", async () => {
      try {
        await saveSettings({ browser_search_engine: engineSelect.value });
        addressInput.placeholder = `Search with ${engineSelect.value} or enter address`;
        toast(`Search engine set to ${engineSelect.value}`, "success");
      } catch {
        toast("Couldn't save the search engine", "error");
      }
    });

    const zoomInput = el("input", {
      class: "input", type: "number", min: "50", max: "300",
      value: String(store.settings.browser_default_zoom || 100),
      style: { width: "90px" },
    });
    zoomInput.addEventListener("change", async () => {
      const value = Math.min(300, Math.max(50, Number(zoomInput.value) || 100));
      zoomInput.value = String(value);
      try {
        await saveSettings({ browser_default_zoom: value });
        await hub.setDefaultZoom(value);
        toast(`New tabs will open at ${value}% zoom`, "success");
      } catch {
        toast("Couldn't save the default zoom", "error");
      }
    });

    const cacheCb = el("input", { type: "checkbox", checked: "checked" });
    const cookiesCb = el("input", { type: "checkbox" });
    const historyCb = el("input", { type: "checkbox" });
    const checkRow = (cb, label, sub) => el("label", { class: "menu-check" }, cb,
      el("span", {}, label, el("span", { class: "s" }, sub)));
    const clearBtn = el("button", { class: "btn small danger" }, "Clear browsing data");
    clearBtn.addEventListener("click", async () => {
      const types = [
        ...(cacheCb.checked ? ["cache"] : []),
        ...(cookiesCb.checked ? ["cookies"] : []),
        ...(historyCb.checked ? ["history"] : []),
      ];
      if (!types.length) { toast("Pick at least one data type", "info"); return; }
      const sure = await confirmDialog({
        title: "Clear browsing data?",
        body: "This clears the selected Browser Hub data. Clearing cookies signs you out of sites you opened in the Hub. This cannot be undone.",
        confirmLabel: "Clear", danger: true,
      });
      if (!sure) return;
      const result = await hub.clearData(types).catch((error) => ({ ok: false, error: String(error) }));
      if (result?.ok) {
        toast(`Cleared: ${Object.keys(result.cleared || {}).join(", ")}`, "success");
        if (types.includes("history") && historyOpen) await renderHistory();
      } else {
        toast(`Couldn't clear data: ${result?.error || "unknown error"}`, "error");
      }
    });

    const printBtn = el("button", { class: "btn small" }, "Print this page…");
    printBtn.addEventListener("click", () => { hub.print(); closeMenu(); });
    const pdfBtn = el("button", { class: "btn small" }, "Save page as PDF…");
    pdfBtn.addEventListener("click", async () => {
      closeMenu();
      const result = await hub.exportPdf().catch((error) => ({ ok: false, error: String(error) }));
      if (result?.ok) toast(`PDF saved to ${result.path}`, "success");
      else if (result?.cancelled) toast("PDF export cancelled", "info");
      else toast(`PDF export failed: ${result?.error || "unknown error"}`, "error");
    });

    menuPanel = el("div", { class: "hub-menu" },
      el("div", { class: "menu-head" }, el("strong", {}, "Browser settings"),
        el("button", { class: "btn small", onclick: () => closeMenu() }, "Close")),
      el("div", { class: "menu-row" },
        el("span", {}, "Search engine"),
        engineSelect),
      el("div", { class: "menu-row" },
        el("span", {}, "Default zoom for new tabs"),
        zoomInput),
      el("div", { class: "menu-sep" }),
      el("div", { class: "menu-title" }, "Clear browsing data"),
      checkRow(cacheCb, "Cached images and files", "frees disk space"),
      checkRow(cookiesCb, "Cookies and site data", "signs you out of Hub sites"),
      checkRow(historyCb, "Browsing history", "stored locally, capped at 5000"),
      clearBtn,
      el("div", { class: "menu-sep" }),
      el("div", { class: "menu-title" }, "This page"),
      el("div", { class: "menu-actions" }, printBtn, pdfBtn));
    content.append(menuPanel);
  }

  /* ------------------------------------------------------------- permission dialog */
  let permDialog = null;
  let permTimer = null;
  function hidePermissionDialog() {
    clearTimeout(permTimer);
    permDialog?.remove();
    permDialog = null;
  }
  function showPermissionDialog(request) {
    hidePermissionDialog();
    const respond = (allowed, remember) => {
      window.jmdb.permissions.respond({ id: request.id, allowed, remember: Boolean(remember) });
      hidePermissionDialog();
    };
    permDialog = el("div", { class: "hub-perm" },
      el("h4", {}, "Permission request"),
      el("p", { style: { lineHeight: "1.5" } }, request.message || `${request.origin} wants to use: ${request.permission}`),
      el("p", { style: { color: "var(--text-dim)", fontSize: "12.5px", margin: "0 0 10px" } }, request.origin || ""),
      el("div", { class: "menu-actions" },
        el("button", { class: "btn small", onclick: () => respond(false, false) }, "Deny"),
        el("button", { class: "btn small", onclick: () => respond(true, true) }, "Always allow"),
        el("button", { class: "btn small primary", onclick: () => respond(true, false) }, "Allow")));
    content.append(permDialog);
    // after 30s main falls back to the native dialog; stop showing this one
    permTimer = setTimeout(hidePermissionDialog, 30000);
  }

  /* ------------------------------------------------------------- history */
  let historyPanel = null;
  let historyQuery = "";
  async function renderHistory() {
    historyPanel?.remove();
    const entries = await hub.history(historyQuery || undefined).catch(() => []);
    const search = el("input", {
      class: "input", type: "search", placeholder: "Search history…",
      value: historyQuery, style: { width: "220px" },
    });
    search.addEventListener("input", () => {
      historyQuery = search.value;
      renderHistory();
    });
    historyPanel = el("div", { class: "hub-history" });
    const head = el("div", { class: "page-head" },
      el("div", {}, el("h1", {}, "Browser history"),
        el("div", { class: "sub" }, `${entries.length} ${historyQuery ? "matching" : "recent"} entries, stored locally`)),
      el("div", { class: "spacer" }),
      search,
      el("button", { class: "btn small danger", onclick: async () => { await hub.clearHistory(); renderHistory(); } }, "Clear history"),
      el("button", { class: "btn small", onclick: () => { historyOpen = false; historyPanel.remove(); historyPanel = null; } }, "Close"));
    historyPanel.append(head);
    const list = el("div", {});
    for (const entry of entries) {
      list.append(el("div", { class: "history-item", onclick: () => { hub.navigate(entry.url); } },
        el("span", { style: { fontWeight: 600, fontSize: "13.5px", maxWidth: "46%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, entry.title || entry.url),
        el("span", { class: "url" }, entry.url),
        el("span", { class: "when" }, new Date(entry.at).toLocaleString())));
    }
    if (!entries.length) list.append(el("div", { class: "empty" }, el("h3", {}, "Nothing here yet")));
    historyPanel.append(list);
    content.append(historyPanel);
  }

  /* ------------------------------------------------------------- DRM / errors */
  let banner = null;
  function showBanner(html, buttons) {
    banner?.remove();
    banner = el("div", { class: "hub-banner" }, el("span", {}, html));
    const row = el("div", { class: "row" });
    for (const [label, handler] of buttons) {
      row.append(el("button", { class: "btn small", onclick: handler }, label));
    }
    banner.append(row);
    content.append(banner);
  }
  function hideBanner() { banner?.remove(); banner = null; }

  /* ------------------------------------------------------------- IPC */
  const offs = [];
  offs.push(window.jmdb.on("hub:tabs", (list) => {
    tabs = list; renderTabs();
    const signature = tabs.filter((tab) => tab.pinned).map((tab) => tab.url).sort().join("|");
    if (signature !== favSignature) { favSignature = signature; renderFavorites(); }
  }));
  offs.push(window.jmdb.on("hub:tab-active", (tab) => {
    activeTab = tab; renderActive(); hideBanner();
  }));
  offs.push(window.jmdb.on("hub:drm", (data) => {
    if (data.drm && data.id === activeTab?.id) {
      showBanner(
        "This site uses DRM that the embedded browser can't play. Open it in your system browser (Chrome/Edge/Firefox) where DRM is supported.",
        [["Open externally", () => window.jmdb.external.open(data.url)], ["Dismiss", () => hideBanner()]]);
    }
  }));
  offs.push(window.jmdb.on("hub:found-in-page", (result) => {
    findCount = result;
    if (findBar) findBar.querySelector(".count").textContent = `${result.activeMatchOrdinal || 0}/${result.matches || 0}`;
  }));
  offs.push(window.jmdb.on("hub:focus-address", () => addressInput.focus()));
  offs.push(window.jmdb.on("hub:open-find", () => toggleFind(true)));
  offs.push(window.jmdb.on("hub:crashed", (data) => {
    showBanner(`The page process crashed (${data.reason || "unknown"}). You can reload the tab.`, [["Reload", () => hub.reload()], ["Dismiss", () => hideBanner()]]);
  }));
  offs.push(window.jmdb.on("hub:unresponsive", () => {
    showBanner("The page stopped responding. You can wait or reload.", [["Reload", () => hub.reload()], ["Dismiss", () => hideBanner()]]);
  }));
  offs.push(window.jmdb.on("hub:load-error", (data) => {
    showBanner(`Couldn't load ${data.url || "page"}: ${data.description || "network error"}. Check your connection; sites open in the hub need internet.`, [["Retry", () => hub.reload()], ["Dismiss", () => hideBanner()]]);
  }));
  offs.push(window.jmdb.on("permissions:asked", (request) => showPermissionDialog(request)));
  offs.push(window.jmdb.on("downloads:updated", (list) => {
    downloads = list;
    downloadsBtn.style.color = downloads.some((item) => item.state === "progressing") ? "var(--accent)" : "";
    if (downloadsOpen) renderDownloads();
  }));

  // initial state: list tabs; if none, restore-or-create the first tab; activate the first
  tabs = await hub.tabs();
  // a ?url= param (Services cards) opens that site in a new tab directly —
  // the page owns the whole tab lifecycle, no cross-page timing tricks
  const wantedUrl = route && route.params ? route.params.get("url") : null;
  if (wantedUrl && /^https?:\/\//i.test(wantedUrl)) {
    await hub.createTab(wantedUrl).catch(() => {});
    tabs = await hub.tabs();
  } else if (!tabs.length) {
    // main restores the previous session's tabs on the Hub's first activation;
    // if still none (fresh profile), open the home page in a tab
    await hub.createTab("https://duckduckgo.com").catch(() => {});
    tabs = await hub.tabs();
  }
  if (tabs.length && !tabs.some((tab) => tab.id === activeTab?.id)) {
    await hub.activateTab(tabs[0].id);
    activeTab = (await hub.tabs()).find((tab) => tab.id === tabs[0].id) || null;
  }
  renderTabs();
  renderActive();
  renderFavorites();

  // cleanup when navigating away from the hub page
  const disconnect = () => {
    if (!container.isConnected) {
      observer.disconnect();
      document.removeEventListener("keydown", keyHandler);
      for (const off of offs) off();
      hideBanner();
      closeMenu();
      hidePermissionDialog();
      window.removeEventListener("hashchange", disconnect);
    }
  };
  window.addEventListener("hashchange", disconnect);

  /* ------------------------------------------------------------- helpers */
  function navButton(path, title) {
    const button = el("button", { class: "nav-btn", title, disabled: "disabled" });
    button.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg>`;
    return button;
  }
  function toolbarButton(title, path) {
    const button = el("button", { class: "nav-btn", title });
    button.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg>`;
    return button;
  }
}
