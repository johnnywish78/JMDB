/**
 * JMDB — Browser Hub
 * Multi-tab browser using Electron <webview> tags.
 */
let _tabs = [];
let _activeTabId = null;
let _tabIdCounter = 0;

async function renderBrowser(params = {}) {
  const body = document.getElementById('contentBody');

  // Initialize tabs if needed
  if (_tabs.length === 0) {
    const homeUrl = params.url || AppState.settings.browser_home || 'https://duckduckgo.com';
    _tabs = [{ id: ++_tabIdCounter, title: 'New Tab', url: homeUrl, pinned: false }];
    _activeTabId = _tabs[0].id;
  }

  body.innerHTML = `
    <div class="browser-container" style="height:100%;display:flex;flex-direction:column;">
      <div class="browser-tabs" id="browserTabs"></div>
      <div class="browser-toolbar" id="browserToolbar"></div>
      <div class="browser-loading-bar"><div class="browser-loading-progress" id="loadingProgress"></div></div>
      <div class="browser-views" id="browserViews"></div>
    </div>`;
  body.classList.remove('hidden');
  document.getElementById('contentLoading').classList.add('hidden');

  renderTabs();
  renderToolbar();
  await ensureWebView(_activeTabId);
}

function renderTabs() {
  const container = document.getElementById('browserTabs');
  if (!container) return;
  let html = '';
  for (const tab of _tabs) {
    html += `
      <div class="browser-tab ${tab.id === _activeTabId ? 'active' : ''}" data-tab-id="${tab.id}" onclick="switchTab(${tab.id})">
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;">${esc(tab.title)}</span>
        <span class="browser-tab-close" onclick="event.stopPropagation();closeTab(${tab.id})">✕</span>
      </div>`;
  }
  html += `<button class="browser-new-tab" onclick="newTab()">+</button>`;
  container.innerHTML = html;
}

function renderToolbar() {
  const active = _tabs.find(t => t.id === _activeTabId);
  if (!active) return;
  const container = document.getElementById('browserToolbar');
  if (!container) return;
  container.innerHTML = `
    <button class="browser-nav-btn" onclick="browserBack()" title="Back">◀</button>
    <button class="browser-nav-btn" onclick="browserForward()" title="Forward">▶</button>
    <button class="browser-nav-btn" onclick="browserReload()" title="Reload">↺</button>
    <button class="browser-nav-btn" onclick="browserHome()" title="Home">⌂</button>
    <input class="browser-url-bar" type="text" value="${esc(active.url)}" id="browserUrlBar"
           onkeydown="if(event.key==='Enter')navigateTo(this.value)" placeholder="Search or enter URL…">
    <button class="browser-nav-btn" onclick="browserBookmark()" title="Bookmark">☆</button>
    <button class="browser-nav-btn" onclick="browserExternal()" title="Open externally">↗</button>
  `;
  const input = document.getElementById('browserUrlBar');
  if (input) input.focus();
}

function getActiveWebview() {
  return document.querySelector(`#webview-tab-${_activeTabId}`);
}

async function ensureWebView(tabId) {
  const viewsContainer = document.getElementById('browserViews');
  if (!viewsContainer) return;

  // Remove old views
  viewsContainer.innerHTML = '';

  const tab = _tabs.find(t => t.id === tabId);
  if (!tab) return;

  const viewDiv = document.createElement('div');
  viewDiv.className = 'browser-view';
  viewDiv.id = `browser-view-${tabId}`;

  const webview = document.createElement('webview');
  webview.id = `webview-tab-${tabId}`;
  webview.style.width = '100%';
  webview.style.height = '100%';
  webview.setAttribute('nodeintegration', 'false');
  webview.setAttribute('contextisolation', 'true');
  webview.setAttribute('partition', 'persist:jmdb-browser');

  // Handle navigation
  webview.addEventListener('did-navigate', (e) => {
    tab.url = e.url;
    tab.title = webview.getTitle() || e.url;
    renderTabs();
    renderToolbar();
    updateLoadingBar(100);
  });

  webview.addEventListener('did-navigate-in-page', (e) => {
    tab.url = e.url;
    renderToolbar();
  });

  webview.addEventListener('page-title-updated', (e) => {
    tab.title = e.title;
    renderTabs();
  });

  webview.addEventListener('load-commit', () => {
    updateLoadingBar(30);
  });

  webview.addEventListener('dom-ready', () => {
    updateLoadingBar(100);
  });

  webview.addEventListener('console-message', (e) => {
    if (e.level === 2) console.error('[webview]', e.message);
  });

  webview.addEventListener('crashed', () => {
    AppState.toast('Page crashed. Try reloading.', 'error');
    updateLoadingBar(0);
  });

  viewDiv.appendChild(webview);
  viewsContainer.appendChild(viewDiv);

  // Load URL
  webview.loadURL(normalizeUrl(tab.url));
}

function updateLoadingBar(pct) {
  const bar = document.getElementById('loadingProgress');
  if (bar) bar.style.width = pct + '%';
}

function normalizeUrl(url) {
  url = (url || '').trim();
  if (!url) return 'https://duckduckgo.com';
  if (/^https?:\/\//i.test(url)) return url;
  if (/^[^\s]+\.[^\s]/.test(url)) return 'https://' + url;
  return 'https://duckduckgo.com/?q=' + encodeURIComponent(url);
}

function switchTab(tabId) {
  _activeTabId = tabId;
  renderTabs();
  renderToolbar();
  ensureWebView(tabId);
}

function newTab() {
  const tab = { id: ++_tabIdCounter, title: 'New Tab', url: AppState.settings.browser_home || 'https://duckduckgo.com', pinned: false };
  _tabs.push(tab);
  _activeTabId = tab.id;
  renderTabs();
  renderToolbar();
  ensureWebView(tab.id);
}

function closeTab(tabId) {
  const idx = _tabs.findIndex(t => t.id === tabId);
  if (idx === -1) return;
  _tabs.splice(idx, 1);
  if (_tabs.length === 0) { newTab(); return; }
  if (_activeTabId === tabId) {
    _activeTabId = _tabs[Math.min(idx, _tabs.length - 1)].id;
    renderTabs();
    renderToolbar();
    ensureWebView(_activeTabId);
  }
}

function navigateTo(inputUrl) {
  const active = _tabs.find(t => t.id === _activeTabId);
  if (!active) return;
  active.url = normalizeUrl(inputUrl);
  const wv = getActiveWebview();
  if (wv) wv.loadURL(active.url);
}

function browserBack() {
  const wv = getActiveWebview();
  if (wv && wv.canGoBack()) wv.goBack();
}

function browserForward() {
  const wv = getActiveWebview();
  if (wv && wv.canGoForward()) wv.goForward();
}

function browserReload() {
  const wv = getActiveWebview();
  if (wv) wv.reload();
}

function browserHome() {
  const url = AppState.settings.browser_home || 'https://duckduckgo.com';
  navigateTo(url);
}

function browserBookmark() {
  const active = _tabs.find(t => t.id === _activeTabId);
  if (!active) return;
  const name = active.title || active.url;
  API.post('/api/bookmarks', { name, url: active.url }).then(() => {
    AppState.toast('Bookmark saved!', 'success');
  }).catch(() => AppState.toast('Failed to save bookmark', 'error'));
}

function browserExternal() {
  const active = _tabs.find(t => t.id === _activeTabId);
  if (active) jmdb.openExternal(active.url);
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 't') { e.preventDefault(); newTab(); }
  if (e.ctrlKey && e.key === 'w') { e.preventDefault(); closeTab(_activeTabId); }
  if (e.ctrlKey && e.key === 'l') {
    e.preventDefault();
    const input = document.getElementById('browserUrlBar');
    if (input) { input.focus(); input.select(); }
  }
  if (e.ctrlKey && e.key === 'r') { e.preventDefault(); browserReload(); }
  if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); browserBack(); }
  if (e.altKey && e.key === 'ArrowRight') { e.preventDefault(); browserForward(); }
});
