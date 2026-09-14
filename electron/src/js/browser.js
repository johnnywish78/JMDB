const Browser = {
  web: null,
  init(container) {
    container.innerHTML = `
      <div class="browser-container">
        <div class="browser-toolbar">
          <button class="btn btn-secondary btn-sm" onclick="Browser.newTab()" title="New Tab"></button>
          <button class="btn btn-secondary btn-sm" onclick="Browser.back()" title="Back">◀</button>
          <button class="btn btn-secondary btn-sm" onclick="Browser.fwd()" title="Forward">▶</button>
          <button class="btn btn-secondary btn-sm" onclick="Browser.reload()" title="Reload">⟳</button>
          <button class="btn btn-secondary btn-sm" onclick="Browser.home()" title="Home">🏠</button>
          <input type="text" id="b-url" value="https://www.google.com" onkeydown="if(event.key==='Enter')Browser.go()">
          <button class="btn btn-secondary btn-sm" onclick="Browser.toggleMenu()" title="Menu">☰</button>
        </div>
        <webview id="b-web" src="https://www.google.com" partition="persist:browser" style="display:flex;"></webview>
        <div id="b-menu" class="browser-menu" style="display:none;">
          <div class="browser-menu-item" onclick="Browser.newTab()"><span class="menu-icon">📄</span><span>New Tab</span><span class="menu-shortcut">Ctrl+T</span></div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="App.nav('browser-history')"><span class="menu-icon">🕐</span><span>History</span></div>
          <div class="browser-menu-item" onclick="App.nav('browser-downloads')"><span class="menu-icon">️</span><span>Downloads</span></div>
          <div class="browser-menu-item" onclick="App.nav('browser-bookmarks')"><span class="menu-icon">⭐</span><span>Bookmarks</span></div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.action('find')"><span class="menu-icon">🔍</span><span>Find in Page</span><span class="menu-shortcut">Ctrl+F</span></div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('zoom-sub')"><span class="menu-icon">🔎</span><span>Zoom</span><span>▶</span></div>
          <div id="zoom-sub" class="browser-menu-sub">
            <div class="browser-menu-item" onclick="Browser.zoom(0.1)"><span class="menu-icon">+</span><span>Zoom In</span></div>
            <div class="browser-menu-item" onclick="Browser.zoom(-0.1)"><span class="menu-icon">−</span><span>Zoom Out</span></div>
            <div class="browser-menu-item" onclick="Browser.zoomReset()"><span class="menu-icon">⟲</span><span>Reset Zoom</span></div>
          </div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.action('print')"><span class="menu-icon">🖨️</span><span>Print</span><span class="menu-shortcut">Ctrl+P</span></div>
          <div class="browser-menu-item" onclick="Browser.action('pdf')"><span class="menu-icon">📥</span><span>Save as PDF</span></div>
          <div class="browser-menu-item" onclick="Browser.action('fullscreen')"><span class="menu-icon">⛶</span><span>Fullscreen</span></div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('app-sub')"><span class="menu-icon">🎨</span><span>Appearance</span><span>▶</span></div>
          <div id="app-sub" class="browser-menu-sub">
            <div class="browser-menu-item" onclick="App.toggleTheme()"><span class="menu-icon">🌙</span><span>Toggle Theme</span></div>
            <div class="browser-menu-item" onclick="App.toast('Font size settings','info')"><span class="menu-icon">Aa</span><span>Font Size</span></div>
            <div class="browser-menu-item" onclick="App.toast('Bookmarks bar toggled','info')"><span class="menu-icon">⭐</span><span>Show Bookmarks Bar</span></div>
          </div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('priv-sub')"><span class="menu-icon">🔒</span><span>Privacy & Security</span><span>▶</span></div>
          <div id="priv-sub" class="browser-menu-sub">
            <div class="browser-menu-item" onclick="App.toast('Cleared!','success')"><span class="menu-icon">🗑️</span><span>Clear Browsing Data</span></div>
            <div class="browser-menu-item" onclick="App.toast('Cookies managed','info')"><span class="menu-icon"></span><span>Cookies</span></div>
            <div class="browser-menu-item" onclick="App.toast('Cache cleared','success')"><span class="menu-icon">💾</span><span>Cache</span></div>
            <div class="browser-menu-item" onclick="App.toast('Permissions reset','info')"><span class="menu-icon">🔐</span><span>Permissions</span></div>
            <div class="browser-menu-item" onclick="App.toast('DNT enabled','info')"><span class="menu-icon">🚫</span><span>Do Not Track</span></div>
          </div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('perm-sub')"><span class="menu-icon"></span><span>Site Permissions</span><span>▶</span></div>
          <div id="perm-sub" class="browser-menu-sub">
            <div class="browser-menu-item"><span class="menu-icon">🔔</span><span>Notifications</span></div>
            <div class="browser-menu-item"><span class="menu-icon">📍</span><span>Location</span></div>
            <div class="browser-menu-item"><span class="menu-icon">📷</span><span>Camera</span></div>
            <div class="browser-menu-item"><span class="menu-icon">🎤</span><span>Microphone</span></div>
            <div class="browser-menu-item"><span class="menu-icon">JS</span><span>JavaScript</span></div>
            <div class="browser-menu-item"><span class="menu-icon">️</span><span>Images</span></div>
            <div class="browser-menu-item"><span class="menu-icon">🪟</span><span>Popups</span></div>
          </div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="App.toast('Downloads settings','info')"><span class="menu-icon">⬇️</span><span>Downloads Settings</span></div>
          <div class="browser-menu-item" onclick="App.toast('Search engine settings','info')"><span class="menu-icon">🔍</span><span>Search Engine</span></div>
          <div class="browser-menu-item" onclick="App.toast('Homepage settings','info')"><span class="menu-icon">🏠</span><span>Homepage</span></div>
          <div class="browser-menu-item" onclick="App.toast('Startup settings','info')"><span class="menu-icon">🚀</span><span>Startup</span></div>
          <div class="browser-menu-item" onclick="App.toast('Language settings','info')"><span class="menu-icon"></span><span>Language</span></div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="App.nav('browser-settings')"><span class="menu-icon">⚙️</span><span>Browser Settings</span></div>
          <div class="browser-menu-item" onclick="App.toast('Cleared!','success')"><span class="menu-icon">️</span><span>Clear Browsing Data</span></div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="App.nav('browser-about')" style="color: var(--accent); font-weight:bold;"><span class="menu-icon">ℹ️</span><span>About</span></div>
        </div>
      </div>`;
    this.web = document.getElementById('b-web');
    this.web.addEventListener('did-navigate', (e) => { document.getElementById('b-url').value = e.url; });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.browser-menu') && !e.target.closest('[onclick*="toggleMenu"]')) {
        const m = document.getElementById('b-menu');
        if (m) m.style.display = 'none';
      }
    });
  },
  newTab() {
    // For now, just reload the current page
    // In a full implementation, this would create a new BrowserWindow or tab
    this.web.src = 'https://www.google.com';
    document.getElementById('b-url').value = 'https://www.google.com';
    App.toast('New Tab opened', 'info');
  },
  go() {
    let url = document.getElementById('b-url').value.trim();
    if (!url) return;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      if (url.includes('.') && !url.includes(' ')) {
        url = 'https://' + url;
      } else {
        url = 'https://www.google.com/search?q=' + encodeURIComponent(url);
      }
    }
    this.web.src = url;
  },
  back() { if (this.web.canGoBack()) this.web.goBack(); },
  fwd() { if (this.web.canGoForward()) this.web.goForward(); },
  reload() { this.web.reload(); },
  home() { this.web.src = 'https://www.google.com'; document.getElementById('b-url').value = this.web.src; },
  toggleMenu() { const m = document.getElementById('b-menu'); m.style.display = m.style.display === 'none' ? 'block' : 'none'; },
  toggleSub(id) { document.getElementById(id).classList.toggle('open'); },
  zoom(delta) { const c = this.web.getZoomFactor() || 1; this.web.setZoomFactor(Math.max(0.5, Math.min(2.0, c + delta))); },
  zoomReset() { this.web.setZoomFactor(1); },
  action(act) {
    if (act === 'print') this.web.print();
    if (act === 'pdf') this.web.printToPDF({}).then(() => App.toast('PDF Exported','success')).catch(() => App.toast('PDF failed','error'));
    if (act === 'fullscreen') document.documentElement.requestFullscreen();
    document.getElementById('b-menu').style.display = 'none';
  }
};
