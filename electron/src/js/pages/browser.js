/** Browser Hub page (renderer side). The actual web content renders in
 * native WebContentsView tabs owned by the main process; this page draws the
 * tab strip + toolbar, syncs the content bounds, and hosts the overlays
 * (find bar, downloads, history, DRM notice). When the user navigates to any
 * other app page, the views are hidden. */
import { api } from "../api.js";
import { el, clear, icon } from "../ui.js";
import { store } from "../store.js";

const SEARCH_ENGINES = {
  duckduckgo: "https://duckduckgo.com/?q=",
  google: "https://www.google.com/search?q=",
  bing: "https://www.bing.com/search?q=",
  brave: "https://search.brave.com/search?q=",
  startpage: "https://www.startpage.com/sp/search?query=",
};

export default async function render(container, route) {
  const hub = window.jmdb?.hub;
  if (!hub) {
    container.append(el("div", { class: "error-note" },
      "The Browser Hub is only available inside the JMDB desktop app (Electron). Start it with `python run.py`."));
    return;
  }

  container.classList.add("full-bleed");
  await hub.setVisible(true);

  const engine = SEARCH_ENGINES[store.settings.browser_search_engine] || SEARCH_ENGINES.duckduckgo;

  /* ------------------------------------------------------------- DOM */
  const root = el("div", { class: "hub" });
  const tabsRow = el("div", { class: "hub-tabs" });
  const toolbar = el("div", { class: "hub-toolbar" });
  const content = el("div", { class: "hub-content" });
  root.append(tabsRow, toolbar, content);
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

  toolbar.append(backBtn, forwardBtn, reloadBtn, homeBtn, addressBar, zoomBadge,
    findBtn, downloadsBtn, historyBtn, bookmarkBtn, externalBtn);

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

  addressInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") hub.navigate(addressInput.value);
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

  /* ------------------------------------------------------------- history */
  let historyPanel = null;
  async function renderHistory() {
    historyPanel?.remove();
    const entries = await hub.history().catch(() => []);
    historyPanel = el("div", { class: "hub-history" });
    const head = el("div", { class: "page-head" },
      el("div", {}, el("h1", {}, "Browser history"),
        el("div", { class: "sub" }, `${entries.length} recent entries, stored locally`)),
      el("div", { class: "spacer" }),
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
  offs.push(window.jmdb.on("hub:tabs", (list) => { tabs = list; renderTabs(); }));
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
  offs.push(window.jmdb.on("downloads:updated", (list) => {
    downloads = list;
    downloadsBtn.style.color = downloads.some((item) => item.state === "progressing") ? "var(--accent)" : "";
    if (downloadsOpen) renderDownloads();
  }));

  // initial state: list tabs; if none, restore-or-create the first tab; activate the first
  tabs = await hub.tabs();
  if (!tabs.length) {
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

  // cleanup when navigating away from the hub page
  const disconnect = () => {
    if (!container.isConnected) {
      observer.disconnect();
      document.removeEventListener("keydown", keyHandler);
      for (const off of offs) off();
      hideBanner();
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
