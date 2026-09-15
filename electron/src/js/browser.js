const Browser = {
  webview: null,
  history: [],
  historyIndex: -1,
  tabs: [{ id: 1, url: 'https://www.google.com', title: 'Google' }],
  activeTabId: 1,
  tabCounter: 1,

  init(container) {
    container.innerHTML = `
      <div class="browser-container" style="display:flex;flex-direction:column;height:100%;background:var(--bg-primary);">
        <!-- Tab Bar -->
        <div class="browser-tabs" style="display:flex;gap:4px;padding:8px 8px 0;background:var(--bg-secondary);border-bottom:1px solid var(--border-color);overflow-x:auto;">
          <div id="browser-tab-list" style="display:flex;gap:4px;flex:1;"></div>
          <button class="btn btn-sm btn-secondary" id="browser-new-tab" onclick="Browser.newTab()" title="New Tab" style="font-size:16px;padding:4px 10px;">+</button>
        </div>
        <!-- Navigation Bar -->
        <div class="browser-nav" style="display:flex;gap:8px;padding:8px 12px;background:var(--bg-secondary);border-bottom:1px solid var(--border-color);align-items:center;">
          <button class="btn btn-sm btn-secondary" id="btn-back" onclick="Browser.back()" title="Back" style="font-size:16px;padding:4px 8px;">◀</button>
          <button class="btn btn-sm btn-secondary" id="btn-fwd" onclick="Browser.fwd()" title="Forward" style="font-size:16px;padding:4px 8px;">▶</button>
          <button class="btn btn-sm btn-secondary" id="btn-reload" onclick="Browser.reload()" title="Reload" style="font-size:16px;padding:4px 8px;">⟳</button>
          <button class="btn btn-sm btn-secondary" id="btn-home" onclick="Browser.goHome()" title="Home" style="font-size:16px;padding:4px 8px;">🏠</button>
          <input type="text" id="b-url" value="https://www.google.com" 
            onkeydown="if(event.key==='Enter')Browser.navigate()" 
            onfocus="this.select()"
            style="flex:1;background:var(--bg-tertiary);border:1px solid var(--border-color);color:var(--text-primary);padding:8px 16px;border-radius:20px;outline:none;font-size:14px;">
          <button class="btn btn-sm btn-secondary" id="btn-menu" onclick="Browser.toggleMenu()" title="Menu" style="font-size:16px;padding:4px 8px;">☰</button>
        </div>
        <!-- Webview -->
        <div style="flex:1;position:relative;overflow:hidden;background:white;">
          <webview id="browser-webview" src="https://www.google.com" partition="persist:jmdb-browser" style="width:100%;height:100%;border:none;"></webview>
          <div id="browser-loading-bar" style="position:absolute;top:0;left:0;height:2px;background:var(--accent);width:0%;transition:width 0.3s;z-index:10;"></div>
        </div>
        <!-- Menu Dropdown -->
        <div id="browser-menu" class="dropdown-menu right-aligned" style="display:none;position:absolute;top:90px;right:20px;min-width:240px;z-index:500;background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius);box-shadow:var(--shadow);">
          <div class="dropdown-section">
            <div class="dropdown-header">Tabs</div>
            <a class="dropdown-item" onclick="Browser.newTab()">📄 New Tab <span style="float:right;color:var(--text-muted);font-size:11px;">Ctrl+T</span></a>
            <a class="dropdown-item" onclick="Browser.closeTab()">✕ Close Tab <span style="float:right;color:var(--text-muted);font-size:11px;">Ctrl+W</span></a>
          </div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-section">
            <div class="dropdown-header">Navigation</div>
            <a class="dropdown-item" onclick="Browser.goHome()">🏠 Home</a>
            <a class="dropdown-item" onclick="Browser.toggleDevTools()">🔧 Toggle DevTools</a>
          </div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-section">
            <div class="dropdown-header">Actions</div>
            <a class="dropdown-item" onclick="Browser.printPage()">🖨️ Print</a>
            <a class="dropdown-item" onclick="Browser.saveAsPDF()">📥 Save as PDF</a>
            <a class="dropdown-item" onclick="Browser.toggleFullscreen()">⛶ Fullscreen</a>
          </div>
          <div class="dropdown-divider"></div>
          <div class="dropdown-section">
            <div class="dropdown-header">Settings</div>
            <a class="dropdown-item" onclick="App.nav('settings')">⚙️ Browser Settings</a>
          </div>
        </div>
      </div>
    `;

    this.webview = document.getElementById('browser-webview');
    this.renderTabs();

    this.webview.addEventListener('did-navigate', (e) => {
      document.getElementById('b-url').value = e.url;
      this.updateHistory(e.url);
      this.updateNavButtons();
      this.setTabTitle(this.activeTabId, e.url.split('/')[2] || e.url);
      const loadingBar = document.getElementById('browser-loading-bar');
      if (loadingBar) loadingBar.style.width = '0%';
    });

    this.webview.addEventListener('did-start-loading', () => {
      const loadingBar = document.getElementById('browser-loading-bar');
      if (loadingBar) loadingBar.style.width = '60%';
    });

    this.webview.addEventListener('did-stop-loading', () => {
      const loadingBar = document.getElementById('browser-loading-bar');
      if (loadingBar) loadingBar.style.width = '100%';
      setTimeout(() => { if (loadingBar) loadingBar.style.width = '0%'; }, 500);
    });

    this.webview.addEventListener('new-window', (e) => {
      e.preventDefault();
      this.newTabWithURL(e.url);
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('#browser-menu') && !e.target.closest('#btn-menu')) {
        const m = document.getElementById('browser-menu');
        if (m) m.style.display = 'none';
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.key === 't') { e.preventDefault(); this.newTab(); }
      if (e.ctrlKey && e.key === 'w') { e.preventDefault(); this.closeTab(); }
      if (e.ctrlKey && e.key === 'l') { e.preventDefault(); document.getElementById('b-url')?.focus(); }
    });
  },

  renderTabs() {
    const list = document.getElementById('browser-tab-list');
    if (!list) return;
    list.innerHTML = this.tabs.map(tab => `
      <div class="browser-tab ${tab.id === this.activeTabId ? 'active' : ''}" 
           data-tab-id="${tab.id}" onclick="Browser.switchTab(${tab.id})"
           style="display:flex;align-items:center;gap:8px;padding:6px 12px;background:var(--bg-tertiary);border-radius:6px 6px 0 0;cursor:pointer;font-size:13px;max-width:200px;min-width:100px;overflow:hidden;">
        <span class="tab-title" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${this.escapeHtml(tab.title || tab.url)}</span>
        <span class="tab-close" onclick="event.stopPropagation();Browser.closeTabIndex(${tab.id})" style="font-size:14px;opacity:0.5;cursor:pointer;">✕</span>
      </div>
    `).join('');
  },

  switchTab(tabId) {
    this.activeTabId = tabId;
    const tab = this.tabs.find(t => t.id === tabId);
    if (tab && this.webview) {
      this.webview.src = tab.url;
      document.getElementById('b-url').value = tab.url;
    }
    this.renderTabs();
    this.updateNavButtons();
  },

  newTab() {
    this.newTabWithURL('https://www.google.com');
  },

  newTabWithURL(url) {
    this.tabCounter++;
    const newTab = { id: this.tabCounter, url: url || 'https://www.google.com', title: url?.split('/')[2] || 'New Tab' };
    this.tabs.push(newTab);
    this.activeTabId = newTab.id;
    if (this.webview) this.webview.src = newTab.url;
    document.getElementById('b-url').value = newTab.url;
    this.renderTabs();
    this.updateNavButtons();
  },

  closeTab() {
    if (this.tabs.length <= 1) {
      this.goHome();
      return;
    }
    const idx = this.tabs.findIndex(t => t.id === this.activeTabId);
    this.tabs.splice(idx, 1);
    if (this.activeTabId === this.tabs[this.tabs.length - 1]?.id) {
      this.switchTab(this.activeTabId);
    } else if (this.tabs.length > 0) {
      this.switchTab(this.tabs[Math.min(idx, this.tabs.length - 1)].id);
    }
  },

  closeTabIndex(tabId) {
    if (this.tabs.length <= 1) return;
    const idx = this.tabs.findIndex(t => t.id === tabId);
    if (idx === -1) return;
    this.tabs.splice(idx, 1);
    if (this.activeTabId === tabId) {
      const newIndex = Math.min(idx, this.tabs.length - 1);
      this.switchTab(this.tabs[newIndex].id);
    }
    this.renderTabs();
  },

  setTabTitle(tabId, title) {
    const tab = this.tabs.find(t => t.id === tabId);
    if (tab) {
      tab.title = title;
      this.renderTabs();
    }
  },

  navigate() {
    let url = document.getElementById('b-url')?.value.trim();
    if (!url) return;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = url.includes('.') && !url.includes(' ') ? 'https://' + url : 'https://www.google.com/search?q=' + encodeURIComponent(url);
    }
    if (this.webview) this.webview.src = url;
  },

  back() {
    if (this.webview?.canGoBack()) this.webview.goBack();
  },

  fwd() {
    if (this.webview?.canGoForward()) this.webview.goForward();
  },

  reload() {
    this.webview?.reload();
  },

  goHome() {
    const homeUrl = 'https://www.google.com';
    if (this.webview) this.webview.src = homeUrl;
    document.getElementById('b-url').value = homeUrl;
  },

  updateHistory(url) {
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push(url);
    this.historyIndex = this.history.length - 1;
  },

  updateNavButtons() {
    const backBtn = document.getElementById('btn-back');
    const fwdBtn = document.getElementById('btn-fwd');
    if (backBtn) backBtn.disabled = !this.webview?.canGoBack();
    if (fwdBtn) fwdBtn.disabled = !this.webview?.canGoForward();
  },

  toggleMenu() {
    const m = document.getElementById('browser-menu');
    if (m) m.style.display = m.style.display === 'none' ? 'block' : 'none';
  },

  toggleDevTools() {
    if (this.webview) {
      this.webview.openDevTools();
    }
    this.toggleMenu();
  },

  printPage() {
    if (this.webview) {
      try { this.webview.print(); } catch (e) { console.error('Print failed:', e); }
    }
    this.toggleMenu();
  },

  saveAsPDF() {
    if (this.webview) {
      try {
        this.webview.printToPDF({}).then(() => App.toast('PDF exported', 'success')).catch(() => App.toast('PDF export failed', 'error'));
      } catch (e) { console.error('PDF failed:', e); }
    }
    this.toggleMenu();
  },

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen();
    }
    this.toggleMenu();
  },

  escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};

window.Browser = Browser;
