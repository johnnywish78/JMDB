const App = {
  port: 8765,
  currentPage: 'home',
  libraries: [],
  
  async init() {
    if (window.jmdb) this.port = await window.jmdb.getBackendPort();
    this.setupNav();
    this.setupSearch();
    this.setupTheme();
    this.setupAddLibrary();
    this.nav('home');
    await this.loadLibraries();
  },

  setupNav() {
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        this.nav(item.dataset.page);
      });
    });
  },

  setupSearch() {
    const input = document.getElementById('global-search');
    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && input.value.trim().length >= 2) {
          this.nav('search', { q: input.value.trim() });
        }
      });
    }
  },

  setupTheme() {
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', () => this.toggleTheme());
  },

  setupAddLibrary() {
    const btn = document.getElementById('add-library-btn');
    if (btn) btn.addEventListener('click', () => this.showAddLibraryModal());
  },

  setActive(page) {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    const active = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (active) active.classList.add('active');
  },

  nav(page, params = {}) {
    this.currentPage = page;
    this.setActive(page);
    const container = document.getElementById('page-container');
    if (!container) return;
    container.innerHTML = '';
    
    const pages = {
      'home': () => this.renderHome(container),
      'movies': () => this.renderLibrary(container, 'movie', 'Movies', '🎬'),
      'tvshows': () => this.renderLibrary(container, 'tv_show', 'TV Shows', '📺'),
      'music': () => this.renderLibrary(container, 'music', 'Music', '🎵'),
      'people': () => this.renderPeople(container),
      'favorites': () => this.renderFavorites(container),
      'watchlist': () => this.renderEmpty(container, '⭐', 'Watchlist', 'Your watchlist is empty'),
      'collections': () => this.renderCollections(container),
      'search': () => this.renderSearch(container, params),
      'services': () => this.renderServices(container),
      'statistics': () => this.renderStatistics(container),
      'settings': () => this.renderSettings(container),
      'browser': () => Browser.init(container),
      'browser-about': () => this.renderAbout(container),
      'browser-settings': () => this.renderBrowserSettings(container),
      'browser-history': () => this.renderEmpty(container, '🕐', 'Browser History', 'No browsing history'),
      'browser-bookmarks': () => this.renderEmpty(container, '⭐', 'Bookmarks', 'No bookmarks yet'),
      'browser-downloads': () => this.renderEmpty(container, '⬇️', 'Downloads', 'No downloads'),
      'library-manager': () => this.renderLibraryManager(container)
    };
    (pages[page] || pages['home'])();
  },

  async loadLibraries() {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library`);
      const data = await res.json();
      this.libraries = data.libraries || [];
    } catch (e) { 
      console.error("Failed to load libraries", e); 
      this.libraries = [];
    }
  },

  async renderHome(container) {
    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Home</h1>
        <p class="page-subtitle">Your library at a glance</p>
      </div>
      <div id="stats-area"></div>
      <div id="recent-area"></div>
    `;
    await this.loadHomeStats();
    await this.loadHomeRecent();
  },

  async loadHomeStats() {
    const area = document.getElementById('stats-area');
    if (!area) return;
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/media?limit=1000`);
      const data = await res.json();
      const items = data.items || [];
      const movies = items.filter(i => i.media_type === 'movie').length;
      const tv = items.filter(i => i.media_type === 'tv_show').length;
      const music = items.filter(i => i.media_type === 'music').length;
      area.innerHTML = `
        <div class="stats-grid">
          <div class="stat-card"><div class="stat-icon"></div><div><div class="stat-value">${movies}</div><div class="stat-label">Movies</div></div></div>
          <div class="stat-card"><div class="stat-icon">📺</div><div><div class="stat-value">${tv}</div><div class="stat-label">TV Shows</div></div></div>
          <div class="stat-card"><div class="stat-icon"></div><div><div class="stat-value">${music}</div><div class="stat-label">Music</div></div></div>
        </div>`;
    } catch (e) {
      area.innerHTML = '<div class="stats-grid"><div class="stat-card"><div class="stat-icon">️</div><div><div class="stat-value">0</div><div class="stat-label">Backend unreachable</div></div></div></div>';
    }
  },

  async loadHomeRecent() {
    const area = document.getElementById('recent-area');
    if (!area) return;
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/media/recent?limit=10`);
      const data = await res.json();
      if (data.items && data.items.length > 0) {
        area.innerHTML = `<div class="section"><div class="section-header"><h2 class="section-title">Recently Added</h2></div><div class="card-grid">${data.items.map(i => this.mediaCard(i)).join('')}</div></div>`;
      } else {
        area.innerHTML = `<div class="section"><div class="section-header"><h2 class="section-title">Recently Added</h2></div><div class="empty-state"><div class="empty-state-icon">🎬</div><div class="empty-state-title">Your library is empty</div><p>Click "+ Add Library" to get started.</p></div></div>`;
      }
    } catch (e) { area.innerHTML = ''; }
  },

  mediaCard(item) {
    const colors = ['#1e3a5f', '#5f1e3a', '#3a5f1e', '#5f3a1e'];
    const color = colors[item.id % colors.length];
    return `<div class="media-card" onclick="App.toast('Detail view for ${this.esc(item.title)} coming soon', 'info')"><div class="media-card-poster" style="background:linear-gradient(135deg, ${color}, #0f172a);"><div style="font-size:48px;opacity:0.3;"></div></div><div class="media-card-info"><div class="media-card-title">${this.esc(item.title)}</div><div class="media-card-meta">${item.year || ''} · ${item.media_type}</div></div></div>`;
  },

  async renderLibrary(container, type, title, icon) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">${title}</h1></div><div id="lib-content"><div class="empty-state"><div class="loading-spinner"></div></div></div>`;
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/media?limit=100&media_type=${type}`);
      const data = await res.json();
      const content = document.getElementById('lib-content');
      if (data.items && data.items.length > 0) {
        content.innerHTML = `<div class="card-grid">${data.items.map(i => this.mediaCard(i)).join('')}</div>`;
      } else {
        content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">${icon}</div><div class="empty-state-title">No ${title.toLowerCase()} yet</div><p>Scan a library folder to add ${title.toLowerCase()}.</p></div>`;
      }
    } catch (e) {}
  },

  async renderPeople(container) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">People</h1></div><div class="empty-state"><div class="empty-state-icon">👤</div><div class="empty-state-title">No people in database</div></div>`;
  },

  async renderFavorites(container) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">Favorites</h1></div><div class="empty-state"><div class="empty-state-icon">❤️</div><div class="empty-state-title">No favorites yet</div></div>`;
  },

  async renderCollections(container) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">Collections</h1></div><div class="empty-state"><div class="empty-state-icon">📁</div><div class="empty-state-title">No collections yet</div></div>`;
  },

  async renderSearch(container, params) {
    const q = params.q || '';
    container.innerHTML = `<div class="page-header"><h1 class="page-title">Search: "${this.esc(q)}"</h1></div><div id="search-results"></div>`;
    if (q) {
      try {
        const res = await fetch(`http://127.0.0.1:${this.port}/api/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        const area = document.getElementById('search-results');
        let html = '';
        if (data.media && data.media.length > 0) {
          html += `<div class="section"><div class="section-header"><h2 class="section-title">Media (${data.media.length})</h2></div><div class="card-grid">${data.media.map(i => this.mediaCard(i)).join('')}</div></div>`;
        }
        if (!html) html = `<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-title">No results</div></div>`;
        area.innerHTML = html;
      } catch (e) {}
    }
  },

  async renderServices(container) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">Services</h1><p class="page-subtitle">Configure external service integrations</p></div><div id="svc-content"></div>`;
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/services`);
      const data = await res.json();
      const content = document.getElementById('svc-content');
      content.innerHTML = `<div class="settings-section"><div class="settings-section-title">Metadata Providers</div>${(data.services || []).filter(s => s.category === 'metadata').map(s => this.serviceCard(s)).join('')}</div><div class="settings-section"><div class="settings-section-title">Integrations</div>${(data.services || []).filter(s => s.category === 'integration').map(s => this.serviceCard(s)).join('')}</div>`;
    } catch (e) {}
  },

  serviceCard(s) {
    // Real brand logos
    const logos = {
      'YouTube': 'https://www.youtube.com/s/desktop/1234567/img/favicon_144x144.png',
      'Spotify': 'https://www.spotify.com/favicon.ico',
      'Telegram': 'https://telegram.org/favicon.ico',
      'TV Time': 'https://www.tvtime.com/favicon.ico',
      'TMDB': 'https://www.themoviedb.org/assets/2/v4/logos/v2/blue_short-2e7b30f73a401112541bb54791b2b7e481d48e2715360978976e4f375b1bb247.png',
      'OMDb': 'https://www.omdbapi.com/favicon.ico',
      'IMDb': 'https://www.imdb.com/favicon.ico'
    };
    
    const logoUrl = logos[s.name] || '';
    
    return `<div class="settings-item" style="padding:16px;">
      <div style="display:flex;align-items:center;gap:16px;">
        ${logoUrl ? `<img src="${logoUrl}" alt="${s.name}" style="width:40px;height:40px;border-radius:8px;">` : '<div style="width:40px;height:40px;background:var(--bg-tertiary);border-radius:8px;"></div>'}
        <div>
          <div class="settings-item-title">${this.esc(s.name)}</div>
          <div class="settings-item-desc">${s.health_status || 'unknown'} · ${s.enabled ? 'Enabled' : 'Disabled'}</div>
        </div>
      </div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-secondary btn-sm" onclick="App.testService(${s.id})">Test</button>
        <label class="toggle"><input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="App.toggleService(${s.id}, this.checked)"><span class="toggle-slider"></span></label>
      </div>
    </div>`;
  },

  async testService(id) {
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/services/${id}/test`, { method: 'POST' });
      this.toast('Service tested', 'success');
      this.nav('services');
    } catch (e) { this.toast('Test failed', 'error'); }
  },

  async toggleService(id, enabled) {
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/services/${id}`, { method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ enabled }) });
      this.toast(`Service ${enabled ? 'enabled' : 'disabled'}`, 'success');
    } catch (e) {}
  },

  async renderStatistics(container) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">Statistics</h1></div><div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-title">Statistics will appear here</div></div>`;
  },

  renderSettings(container) {
    container.innerHTML = `
      <div class="page-header"><h1 class="page-title">Settings</h1></div>
      <div class="settings-section"><div class="settings-section-title">General</div>
        <div class="settings-item"><div><div class="settings-item-title">Theme</div><div class="settings-item-desc">Choose your preferred theme</div></div><select class="form-select" style="width:200px;" onchange="App.setTheme(this.value)"><option value="dark">Dark</option><option value="light">Light</option></select></div>
      </div>
      <div class="settings-section"><div class="settings-section-title">Metadata API Keys</div>
        <div class="settings-item"><div><div class="settings-item-title">TMDB API Key</div><div class="settings-item-desc">Required for real posters and metadata</div></div><input type="password" class="form-input" id="set-tmdb" placeholder="Enter TMDB API Key" style="width:300px;"></div>
        <div class="settings-item"><div><div class="settings-item-title">Auto-fetch on Scan</div><div class="settings-item-desc">Automatically search TMDB when adding new files</div></div><label class="toggle"><input type="checkbox" id="set-autofetch" checked><span class="toggle-slider"></span></label></div>
        <div style="margin-top:16px; text-align:right;"><button class="btn btn-primary" onclick="App.saveMetadataSettings()">Save Metadata Settings</button></div>
      </div>`;
    this.loadMetadataSettings();
  },

  async loadMetadataSettings() {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/settings/metadata`);
      const data = await res.json();
      const tmdbInput = document.getElementById("set-tmdb");
      const autoFetchInput = document.getElementById("set-autofetch");
      if (tmdbInput && data.tmdb_api_key) tmdbInput.value = data.tmdb_api_key;
      if (autoFetchInput) autoFetchInput.checked = data.auto_fetch_metadata;
    } catch (e) {}
  },

  async saveMetadataSettings() {
    const tmdbKey = document.getElementById("set-tmdb").value.trim();
    const autoFetch = document.getElementById("set-autofetch").checked;
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/settings/metadata`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ tmdb_api_key: tmdbKey, auto_fetch_metadata: autoFetch })
      });
      this.toast("Metadata settings saved successfully!", "success");
    } catch (e) {
      this.toast("Failed to save settings", "error");
    }
  },

  setTheme(theme) {
    document.body.className = `theme-${theme}`;
    this.toast(`Theme: ${theme}`, 'success');
  },

  renderBrowserSettings(container) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">Browser Settings</h1></div><div class="settings-section"><div class="settings-section-title">General</div><div class="settings-item"><div><div class="settings-item-title">Homepage</div></div><input type="text" class="form-input" value="https://www.google.com" style="width:300px;"></div></div>`;
  },

  renderAbout(container) {
    container.innerHTML = `
      <div style="text-align:center;padding:40px;">
        <div style="width:120px;height:120px;background:linear-gradient(135deg,var(--accent),var(--accent-hover));border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:60px;font-weight:bold;color:#000;margin:0 auto 24px;">J</div>
        <h1 style="font-size:32px;font-weight:700;margin-bottom:4px;">JMDB</h1>
        <p style="font-size:16px;color:var(--text-muted);margin-bottom:32px;">Johnny's Media Database</p>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;max-width:500px;margin:0 auto 32px;text-align:left;">
          <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:8px;padding:12px 16px;"><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px;">Application Version</div><div style="font-size:14px;font-family:monospace;">1.0.0</div></div>
          <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:8px;padding:12px 16px;"><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px;">Electron Version</div><div style="font-size:14px;font-family:monospace;" id="ab-elec">Loading...</div></div>
          <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:8px;padding:12px 16px;"><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px;">Python Version</div><div style="font-size:14px;font-family:monospace;" id="ab-py">Loading...</div></div>
          <div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:8px;padding:12px 16px;"><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px;">Browser Engine</div><div style="font-size:14px;font-family:monospace;">Chromium</div></div>
        </div>
      </div>`;
    if (window.jmdb && window.jmdb.getAppVersion) {
      window.jmdb.getAppVersion().then(v => {
        document.getElementById('ab-elec').textContent = v.electron || 'N/A';
      }).catch(() => {});
    }
    fetch(`http://127.0.0.1:${this.port}/api/health`).then(r=>r.json()).then(d => { document.getElementById('ab-py').textContent = d.python || 'N/A'; }).catch(() => {});
  },

  renderEmpty(container, icon, title, text) {
    container.innerHTML = `<div class="page-header"><h1 class="page-title">${title}</h1></div><div class="empty-state"><div class="empty-state-icon">${icon}</div><div class="empty-state-title">${title}</div><p>${text}</p></div>`;
  },

  async renderLibraryManager(container) {
    await this.loadLibraries();
    container.innerHTML = `
      <div class="page-header" style="display:flex;justify-content:space-between;align-items:center;">
        <div><h1 class="page-title">Library Manager</h1><p class="page-subtitle">Manage your media locations</p></div>
        <button class="btn btn-primary" onclick="App.showAddLibraryModal()">+ Add Library</button>
      </div>
      <div id="lib-list">
        ${this.libraries.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">📁</div><div class="empty-state-title">No libraries added</div><p>Click "+ Add Library" to start.</p></div>' : 
          this.libraries.map(lib => `
            <div class="settings-section" style="display:flex;justify-content:space-between;align-items:center;">
              <div>
                <div class="settings-item-title">${this.esc(lib.name)}</div>
                <div class="settings-item-desc">${this.esc(lib.path)} · ${lib.media_type} · Status: ${lib.scan_status}</div>
              </div>
              <div style="display:flex;gap:8px;">
                <button class="btn btn-secondary btn-sm" onclick="App.scanLibrary(${lib.id})">Scan</button>
                <button class="btn btn-danger btn-sm" onclick="App.deleteLibrary(${lib.id})">Delete</button>
              </div>
            </div>
          `).join('')}
      </div>
    `;
  },

  showAddLibraryModal() {
    const body = `
      <div class="form-group">
        <label class="form-label">Library Name</label>
        <input type="text" class="form-input" id="lib-name" placeholder="My Movies">
      </div>
      <div class="form-group">
        <label class="form-label">Media Type</label>
        <select class="form-select" id="lib-type">
          <option value="movie">Movies</option>
          <option value="tv_show">TV Shows</option>
          <option value="music">Music</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Folder Path</label>
        <div style="display:flex;gap:8px;">
          <input type="text" class="form-input" id="lib-path" placeholder="/path/to/media" style="flex:1;">
          <button class="btn btn-secondary" onclick="App.browseFolder()">Browse</button>
        </div>
      </div>`;
    const footer = `<button class="btn btn-secondary" onclick="document.getElementById('active-modal').remove()">Cancel</button><button class="btn btn-primary" onclick="App.createLibrary()">Create Library</button>`;
    this.showModal('Add Library', body, footer);
  },

  async browseFolder() {
    if (window.jmdb && window.jmdb.openDirectory) {
      try {
        const path = await window.jmdb.openDirectory();
        if (path) {
          document.getElementById('lib-path').value = path;
        }
      } catch (e) { console.error(e); }
    } else {
      this.toast('File dialog not available', 'error');
    }
  },

  async createLibrary() {
    const name = document.getElementById('lib-name').value.trim();
    const type = document.getElementById('lib-type').value;
    const path = document.getElementById('lib-path').value.trim();
    if (!name || !path) { this.toast('Name and Path are required', 'error'); return; }
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library`, { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ name, media_type: type, path }) 
      });
      const data = await res.json();
      this.toast(`Library "${data.name}" created successfully!`, 'success');
      document.getElementById('active-modal').remove();
      await this.loadLibraries();
      if (this.currentPage === 'library-manager') this.renderLibraryManager(document.getElementById('page-container'));
    } catch (e) { 
      console.error(e);
      this.toast('Failed to create library', 'error'); 
    }
  },

  async scanLibrary(id) {
    this.toast('Scan started...', 'info');
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library/${id}/scan`, { method: 'POST' });
      this.toast('Scan started in background. Check status in a moment.', 'success');
      
      // Poll for completion
      const checkStatus = async () => {
        const statusRes = await fetch(`http://127.0.0.1:${this.port}/api/library/scan-status`);
        const status = await statusRes.json();
        if (!status.active) {
          this.toast(`Scan complete! Added ${status.media_added} items.`, 'success');
          await this.loadLibraries();
          if (this.currentPage === 'library-manager') this.renderLibraryManager(document.getElementById('page-container'));
        } else {
          setTimeout(checkStatus, 2000);
        }
      };
      setTimeout(checkStatus, 2000);
      
    } catch (e) { 
      console.error(e);
      this.toast('Scan failed', 'error'); 
    }
  },

  async deleteLibrary(id) {
    if (!confirm('Are you sure? This will remove the library but keep your media files.')) return;
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/library/${id}`, { method: 'DELETE' });
      this.toast('Library deleted', 'success');
      await this.loadLibraries();
      if (this.currentPage === 'library-manager') this.renderLibraryManager(document.getElementById('page-container'));
    } catch (e) {
      console.error(e);
      this.toast('Failed to delete library', 'error');
    }
  },

  showModal(title, body, footer) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'active-modal';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:1000;';
    overlay.innerHTML = `<div style="background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:12px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto;"><div style="padding:20px 24px;border-bottom:1px solid var(--border-color);display:flex;align-items:center;justify-content:space-between;"><h3 style="font-size:18px;font-weight:600;">${this.esc(title)}</h3><button onclick="document.getElementById('active-modal').remove()" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button></div><div style="padding:24px;">${body}</div>${footer ? `<div style="padding:16px 24px;border-top:1px solid var(--border-color);display:flex;justify-content:flex-end;gap:8px;">${footer}</div>` : ''}</div>`;
    document.body.appendChild(overlay);
  },

  toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || ''}</span><span>${this.esc(msg)}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3000);
  },

  toggleTheme() {
    const isDark = document.body.classList.contains('theme-dark');
    document.body.classList.toggle('theme-dark');
    document.body.classList.toggle('theme-light');
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = isDark ? '☀️' : '🌙';
  },

  esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }
};
document.addEventListener('DOMContentLoaded', () => App.init());
