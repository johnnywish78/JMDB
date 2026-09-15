const Settings = {
  port: 8765,
  currentSection: 'general',
  allSettings: {},

  init(container) {
    this.port = window.jmdb ? (window.jmdb.getBackendPort ? 8765 : 8765) : 8765;
    container.innerHTML = this.renderLayout();
    this.loadSettings();
    this.setupNav();
  },

  renderLayout() {
    const sections = [
      { id: 'general', label: 'General', icon: '⚙️' },
      { id: 'appearance', label: 'Appearance', icon: '🎨' },
      { id: 'library', label: 'Library', icon: '📚' },
      { id: 'locations', label: 'Locations', icon: '📁' },
      { id: 'metadata', label: 'Metadata', icon: '🏷️' },
      { id: 'services', label: 'Services', icon: '🔌' },
      { id: 'browser', label: 'Browser', icon: '🌐' },
      { id: 'player', label: 'Player', icon: '▶️' },
      { id: 'database', label: 'Database', icon: '💾' },
      { id: 'backup', label: 'Backup & Restore', icon: '📦' },
      { id: 'advanced', label: 'Advanced', icon: '🔧' }
    ];
    return `
      <div class="settings-layout" style="height:100%;">
        <nav class="settings-nav" role="navigation" aria-label="Settings sections">
          ${sections.map(s => `
            <div class="settings-nav-item ${s.id === this.currentSection ? 'active' : ''}" 
                 data-section="${s.id}" role="menuitem" tabindex="0">
              <span>${s.icon}</span> ${s.label}
            </div>
          `).join('')}
        </nav>
        <div class="settings-content" id="settings-content"></div>
      </div>
    `;
  },

  setupNav() {
    document.querySelectorAll('.settings-nav-item').forEach(item => {
      item.addEventListener('click', () => {
        this.switchSection(item.dataset.section);
      });
      item.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.switchSection(item.dataset.section);
        }
      });
    });
  },

  switchSection(sectionId) {
    this.currentSection = sectionId;
    document.querySelectorAll('.settings-nav-item').forEach(i => {
      i.classList.toggle('active', i.dataset.section === sectionId);
    });
    const content = document.getElementById('settings-content');
    if (content) {
      content.innerHTML = this.renderSection(sectionId);
      this.bindSectionEvents(sectionId);
    }
  },

  renderSection(sectionId) {
    const renderers = {
      general: () => this.renderGeneral(),
      appearance: () => this.renderAppearance(),
      library: () => this.renderLibrary(),
      locations: () => this.renderLocations(),
      metadata: () => this.renderMetadata(),
      services: () => this.renderServices(),
      browser: () => this.renderBrowser(),
      player: () => this.renderPlayer(),
      database: () => this.renderDatabase(),
      backup: () => this.renderBackup(),
      advanced: () => this.renderAdvanced()
    };
    return (renderers[sectionId] || (() => '<p>Coming soon</p>'))();
  },

  renderGeneral() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Application</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">App Name</div>
            <div class="setting-desc">JMDB - Johnny Media Database v1.0.0</div>
          </div>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Backend Port</div>
            <div class="setting-desc">Port the API server listens on</div>
          </div>
          <span class="form-input" style="width:100px;text-align:center;">8765</span>
        </div>
      </div>
    `;
  },

  renderAppearance() {
    const isDark = document.body.classList.contains('theme-dark');
    return `
      <div class="settings-section">
        <div class="settings-section-title">Theme</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Dark Mode</div>
            <div class="setting-desc">Use dark theme for the interface</div>
          </div>
          <label class="toggle">
            <input type="checkbox" id="dark-mode-toggle" ${isDark ? 'checked' : ''} onchange="Settings.toggleTheme(this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
      <div class="settings-section">
        <div class="settings-section-title">Accent Color</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Primary Accent</div>
            <div class="setting-desc">Choose the highlight color</div>
          </div>
          <input type="color" value="#f59e0b" onchange="Settings.setAccent(this.value)" style="width:48px;height:32px;border:none;background:transparent;cursor:pointer;">
        </div>
      </div>
    `;
  },

  renderLibrary() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Library Behavior</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Auto-fetch Metadata</div>
            <div class="setting-desc">Automatically fetch metadata when scanning</div>
          </div>
          <label class="toggle">
            <input type="checkbox" id="auto-metadata" ${this.allSettings.auto_fetch_metadata === 'true' ? 'checked' : ''} onchange="Settings.saveSetting('auto_fetch_metadata', this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Scan on Add Location</div>
            <div class="setting-desc">Automatically scan new locations when added</div>
          </div>
          <label class="toggle">
            <input type="checkbox" checked onchange="Settings.saveSetting('scan_on_add', this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    `;
  },

  renderLocations() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Default Locations</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Watch Directory</div>
            <div class="setting-desc">Directory to watch for new media files</div>
          </div>
          <input type="text" class="form-input" style="width:300px;" placeholder="/home/user/media" onchange="Settings.saveSetting('watch_dir', this.value)">
        </div>
      </div>
    `;
  },

  renderMetadata() {
    const tmdb = this.allSettings.tmdb_api_key || '';
    const omdb = this.allSettings.omdb_api_key || '';
    return `
      <div class="settings-section">
        <div class="settings-section-title">API Keys</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">TMDB API Key</div>
            <div class="setting-desc">Required for movie/TV metadata and posters</div>
          </div>
          <input type="password" id="set-tmdb-key" class="form-input" style="width:300px;" value="${tmdb}" placeholder="Enter TMDB API key">
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">OMDb API Key</div>
            <div class="setting-desc">Alternative metadata source</div>
          </div>
          <input type="password" id="set-omdb-key" class="form-input" style="width:300px;" value="${omdb}" placeholder="Enter OMDb API key">
        </div>
        <div style="margin-top:16px;text-align:right;">
          <button class="btn btn-primary" onclick="Settings.saveMetadataSettings()">Save API Keys</button>
        </div>
      </div>
    `;
  },

  renderServices() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Integrated Services</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">TMDB</div>
            <div class="setting-desc">Movie and TV show metadata provider</div>
          </div>
          <span style="color:var(--text-muted);font-size:12px;">Configuration in Metadata tab</span>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">IMDb</div>
            <div class="setting-desc">No native integration available</div>
          </div>
          <span style="color:var(--danger);font-size:12px;">Not configured</span>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">OMDb</div>
            <div class="setting-desc">Alternative metadata provider</div>
          </div>
          <span style="color:var(--text-muted);font-size:12px;">Configuration in Metadata tab</span>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">YouTube</div>
            <div class="setting-desc">Video content integration (coming soon)</div>
          </div>
          <span style="color:var(--accent);font-size:12px;">Planned</span>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Spotify</div>
            <div class="setting-desc">Music streaming integration (coming soon)</div>
          </div>
          <span style="color:var(--accent);font-size:12px;">Planned</span>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Telegram</div>
            <div class="setting-desc">Notifications and alerts (coming soon)</div>
          </div>
          <span style="color:var(--accent);font-size:12px;">Planned</span>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">TV Time</div>
            <div class="setting-desc">TV show tracking (coming soon)</div>
          </div>
          <span style="color:var(--accent);font-size:12px;">Planned</span>
        </div>
      </div>
    `;
  },

  renderBrowser() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Browser Settings</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Homepage</div>
            <div class="setting-desc">Page opened on new tab</div>
          </div>
          <input type="text" class="form-input" style="width:300px;" value="https://www.google.com" onchange="Settings.saveSetting('browser_homepage', this.value)">
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Enable DevTools</div>
            <div class="setting-desc">Allow developer tools in browser tab (debugging)</div>
          </div>
          <label class="toggle">
            <input type="checkbox" onchange="Settings.saveSetting('browser_devtools', this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Block Ads</div>
            <div class="setting-desc">Basic ad blocking in embedded browser</div>
          </div>
          <label class="toggle">
            <input type="checkbox" checked onchange="Settings.saveSetting('browser_adblock', this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    `;
  },

  renderPlayer() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Player Settings</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Default Player</div>
            <div class="setting-desc">External player backend for video playback</div>
          </div>
          <select class="form-select" style="width:150px;" onchange="Settings.saveSetting('default_player', this.value)">
            <option value="mpv" ${this.allSettings.default_player === 'mpv' ? 'selected' : ''}>MPV</option>
            <option value="vlc" ${this.allSettings.default_player === 'vlc' ? 'selected' : ''}>VLC</option>
            <option value="auto" ${this.allSettings.default_player === 'auto' ? 'selected' : ''}>Auto</option>
          </select>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">MPV Path</div>
            <div class="setting-desc">Custom path to MPV executable</div>
          </div>
          <input type="text" class="form-input" style="width:300px;" value="${this.allSettings.mpv_path || '/usr/bin/mpv'}" placeholder="/usr/bin/mpv" onchange="Settings.saveSetting('mpv_path', this.value)">
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Resume Playback</div>
            <div class="setting-desc">Automatically resume from last position</div>
          </div>
          <label class="toggle">
            <input type="checkbox" checked onchange="Settings.saveSetting('resume_playback', this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Hardware Acceleration</div>
            <div class="setting-desc">Use GPU for video decoding</div>
          </div>
          <label class="toggle">
            <input type="checkbox" checked onchange="Settings.saveSetting('hw_acceleration', this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    `;
  },

  renderDatabase() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Database</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Database Path</div>
            <div class="setting-desc">${window.jmdb && window.jmdb.getBackendPort ? 'data/database/jmdb.db' : 'data/database/jmdb.db'}</div>
          </div>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Schema Version</div>
            <div class="setting-desc">Current schema version</div>
          </div>
          <span class="form-input" style="width:60px;text-align:center;">2</span>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Database Size</div>
            <div class="setting-desc">Approximate size of database file</div>
          </div>
          <span style="color:var(--text-muted);font-size:13px;">~24 KB</span>
        </div>
      </div>
    `;
  },

  renderBackup() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Backup & Restore</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Create Backup</div>
            <div class="setting-desc">Save a copy of the current database</div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="Settings.createBackup()">Create Backup</button>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Restore from Backup</div>
            <div class="setting-desc">Restore database from a previous backup</div>
          </div>
          <select class="form-select" id="backup-select" style="width:200px;" onchange="Settings.selectBackup(this.value)">
            <option value="">-- Select backup --</option>
          </select>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Backup History</div>
            <div class="setting-desc">Available backups</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="Settings.loadBackups()">Refresh</button>
        </div>
      </div>
    `;
  },

  renderAdvanced() {
    return `
      <div class="settings-section">
        <div class="settings-section-title">Advanced</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Log Level</div>
            <div class="setting-desc">Verbosity of application logs</div>
          </div>
          <select class="form-select" style="width:120px;" onchange="Settings.saveSetting('log_level', this.value)">
            <option value="info" ${this.allSettings.log_level === 'info' ? 'selected' : ''}>Info</option>
            <option value="debug" ${this.allSettings.log_level === 'debug' ? 'selected' : ''}>Debug</option>
            <option value="warning" ${this.allSettings.log_level === 'warning' ? 'selected' : ''}>Warning</option>
          </select>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Reset All Settings</div>
            <div class="setting-desc">Clear all custom settings (cannot be undone)</div>
          </div>
          <button class="btn btn-sm btn-danger" onclick="Settings.resetSettings()">Reset</button>
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Diagnostics</div>
            <div class="setting-desc">View system information</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="App.nav('diagnostics')">Open Diagnostics</button>
        </div>
      </div>
    `;
  },

  bindSectionEvents(sectionId) {
    // Section-specific event bindings go here
  },

  async loadSettings() {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/settings`);
      const data = await res.json();
      this.allSettings = data.settings || {};
      this.switchSection(this.currentSection);
    } catch (e) {
      console.error('Failed to load settings:', e);
      this.switchSection(this.currentSection);
    }
  },

  async saveSetting(key, value) {
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value })
      });
      this.allSettings[key] = String(value);
      App.toast('Setting saved', 'success');
    } catch (e) {
      console.error('Failed to save setting:', e);
      App.toast('Failed to save setting', 'error');
    }
  },

  async saveMetadataSettings() {
    const tmdb = document.getElementById('set-tmdb-key')?.value || '';
    const omdb = document.getElementById('set-omdb-key')?.value || '';
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/settings/metadata`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tmdb_api_key: tmdb, omdb_api_key: omdb })
      });
      this.allSettings.tmdb_api_key = tmdb;
      this.allSettings.omdb_api_key = omdb;
      App.toast('API keys saved', 'success');
    } catch (e) {
      console.error('Failed to save metadata settings:', e);
      App.toast('Failed to save API keys', 'error');
    }
  },

  toggleTheme(enabled) {
    document.body.classList.remove('theme-dark', 'theme-light');
    document.body.classList.add(enabled ? 'theme-dark' : 'theme-light');
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = enabled ? '🌙' : '☀️';
    this.saveSetting('theme', enabled ? 'dark' : 'light');
  },

  setAccent(color) {
    document.documentElement.style.setProperty('--accent', color);
    this.saveSetting('accent_color', color);
  },

  async createBackup() {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/system/backup`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        App.toast('Backup created successfully', 'success');
        this.loadBackups();
      } else {
        App.toast('Backup creation failed', 'error');
      }
    } catch (e) {
      App.toast('Backup failed', 'error');
    }
  },

  async loadBackups() {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/system/backups`);
      const data = await res.json();
      const select = document.getElementById('backup-select');
      if (select) {
        select.innerHTML = '<option value="">-- Select backup --</option>';
        (data.backups || []).forEach(b => {
          const opt = document.createElement('option');
          opt.value = b.filename;
          opt.textContent = `${b.filename} (${new Date(b.created_at).toLocaleString()})`;
          select.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('Failed to load backups:', e);
    }
  },

  async selectBackup(filename) {
    if (!filename) return;
    if (!confirm(`Restore from backup: ${filename}? This will replace your current database.`)) return;
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/system/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backup_path: filename })
      });
      App.toast('Database restored. Please restart the application.', 'success');
    } catch (e) {
      App.toast('Restore failed', 'error');
    }
  },

  async resetSettings() {
    if (!confirm('Reset all settings to defaults? This cannot be undone.')) return;
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/system/reset-settings`, { method: 'POST' });
      this.allSettings = {};
      App.toast('Settings reset. Please reload the page.', 'success');
    } catch (e) {
      App.toast('Reset failed', 'error');
    }
  }
};

window.Settings = Settings;
