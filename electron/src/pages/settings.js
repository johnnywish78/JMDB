/**
 * JMDB — Settings Page
 */
async function renderSettings() {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';

  try {
    const settings = await API.get('/api/settings');
    AppState.settings = settings;

    let html = `
      <div class="section-header"><span class="section-title">Settings</span></div>
      <div class="settings-layout">
        <nav class="settings-nav">
          <div class="settings-section-title">General</div>
          <a class="settings-nav-item active" onclick="showSettingsPanel('general')">Appearance</a>
          <a class="settings-nav-item" onclick="showSettingsPanel('library')">Library</a>
          <div class="settings-section-title">Media</div>
          <a class="settings-nav-item" onclick="showSettingsPanel('playback')">Playback</a>
          <a class="settings-nav-item" onclick="showSettingsPanel('metadata')">Metadata</a>
          <div class="settings-section-title">Browser</div>
          <a class="settings-nav-item" onclick="showSettingsPanel('browser')">Browser</a>
          <div class="settings-section-title">Data</div>
          <a class="settings-nav-item" onclick="showSettingsPanel('data')">Database & Cache</a>
        </nav>
        <div class="settings-panel" id="settingsPanel"></div>
      </div>`;
    body.innerHTML = html;
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');

    showSettingsPanel('general');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><p>${esc(e.message)}</p></div>`;
  }
}

async function showSettingsPanel(section) {
  // Update nav active state
  document.querySelectorAll('.settings-nav-item').forEach(el => el.classList.remove('active'));
  event?.target?.classList.add('active');

  const panel = document.getElementById('settingsPanel');
  if (!panel) return;

  const s = AppState.settings;

  switch(section) {
    case 'general':
      panel.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">Appearance</div>
          <div class="settings-row">
            <div><div class="settings-label">Theme</div><div class="settings-desc">Dark, light, or follow system</div></div>
            <div class="settings-control">
              <select class="settings-select" onchange="updateSetting('theme',this.value)">
                <option value="dark" ${s.theme==='dark'?'selected':''}>Dark</option>
                <option value="light" ${s.theme==='light'?'selected':''}>Light</option>
              </select>
            </div>
          </div>
          <div class="settings-row">
            <div><div class="settings-label">Accent Color</div><div class="settings-desc">Highlight color for the UI</div></div>
            <div class="settings-control">
              <select class="settings-select" onchange="updateSetting('accent',this.value)">
                <option value="amber" ${s.accent==='amber'?'selected':''}>Amber</option>
                <option value="blue" ${s.accent==='blue'?'selected':''}>Blue</option>
                <option value="green" ${s.accent==='green'?'selected':''}>Green</option>
                <option value="rose" ${s.accent==='rose'?'selected':''}>Rose</option>
              </select>
            </div>
          </div>
        </div>`;
      break;

    case 'library':
      const folders = s.library_folders || [];
      panel.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">Library Folders</div>
          <div id="folderList" style="margin-bottom:12px;">
            ${folders.map(f => `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);">
              <span style="flex:1;font-size:13px;color:var(--text-secondary);">📁 ${esc(f)}</span>
              <button class="btn btn-sm" style="color:var(--danger);padding:2px 8px;" onclick="removeFolder(this)">✕</button>
            </div>`).join('')}
            ${folders.length === 0 ? '<div style="color:var(--text-muted);font-size:13px;padding:8px 0;">No folders added yet.</div>' : ''}
          </div>
          <div style="display:flex;gap:8px;">
            <button class="btn btn-sm" onclick="addFolder()">+ Add Folder</button>
            <button class="btn btn-sm btn-accent" onclick="runScan()">▶ Scan Library</button>
          </div>
          <div id="scanStatus" style="margin-top:12px;font-size:13px;color:var(--text-muted);"></div>
        </div>`;
      break;

    case 'playback':
      panel.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">Playback</div>
          <div class="settings-row">
            <div><div class="settings-label">Default Backend</div><div class="settings-desc">mpv (recommended), VLC, or auto-detect</div></div>
            <div class="settings-control">
              <select class="settings-select" id="backendSelect" onchange="updateSetting('backend',this.value)">
                <option value="auto" ${s.backend==='auto'?'selected':''}>Auto</option>
                <option value="mpv" ${s.backend==='mpv'?'selected':''}>MPV</option>
                <option value="vlc" ${s.backend==='vlc'?'selected':''}>VLC</option>
              </select>
            </div>
          </div>
          <div class="settings-row">
            <div><div class="settings-label">Default Volume</div><div class="settings-desc">0–100</div></div>
            <div class="settings-control">
              <input type="range" min="0" max="100" value="${s.volume || 70}" style="width:120px;" oninput="this.nextElementSibling.textContent=this.value+'%'">
              <span style="font-size:12px;color:var(--text-muted);min-width:36px;">${s.volume || 70}%</span>
            </div>
          </div>
          <div class="settings-row">
            <div><div class="settings-label">Autoplay Next Episode</div><div class="settings-desc">Auto-play next episode after current finishes</div></div>
            <div class="settings-control">
              <div class="toggle ${s.autoplay_next?'on':''}" onclick="toggleSetting('autoplay_next',this)"></div>
            </div>
          </div>
          <div class="settings-row">
            <div><div class="settings-label">Subtitles</div><div class="settings-desc">Enable subtitle support</div></div>
            <div class="settings-control">
              <div class="toggle ${s.subtitles_enabled?'on':''}" onclick="toggleSetting('subtitles_enabled',this)"></div>
            </div>
          </div>
        </div>`;
      break;

    case 'metadata':
      panel.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">Metadata Providers</div>
          <div class="settings-row">
            <div><div class="settings-label">TMDB API Key</div><div class="settings-desc">TheMovieDB key for movie/TV metadata</div></div>
            <div class="settings-control">
              <input type="password" class="settings-input" style="width:240px;" value="${esc(s.tmdb_api_key || '')}" placeholder="Enter TMDB key…"
                     onchange="updateSetting('tmdb_api_key',this.value)">
            </div>
          </div>
          <div class="settings-row">
            <div><div class="settings-label">OMDb API Key</div><div class="settings-desc">Optional fallback for IMDb ratings</div></div>
            <div class="settings-control">
              <input type="password" class="settings-input" style="width:240px;" value="${esc(s.omdb_api_key || '')}" placeholder="Enter OMDb key…"
                     onchange="updateSetting('omdb_api_key',this.value)">
            </div>
          </div>
          <div style="padding-top:12px;font-size:12px;color:var(--text-muted);">
            TVMaze works without a key for series. Get free keys at themoviedb.org and omdbapi.com.
          </div>
        </div>`;
      break;

    case 'browser':
      panel.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">Browser</div>
          <div class="settings-row">
            <div><div class="settings-label">Home Page</div><div class="settings-desc">URL opened on new tab</div></div>
            <div class="settings-control">
              <input type="text" class="settings-input" style="width:300px;" value="${esc(s.browser_home || 'https://duckduckgo.com')}"
                     onchange="updateSetting('browser_home',this.value)">
            </div>
          </div>
          <div class="settings-row">
            <div><div class="settings-label">Persistent Session</div><div class="settings-desc">Keep login cookies between sessions</div></div>
            <div class="settings-control">
              <div class="toggle on" onclick="this.classList.toggle('on')"></div>
            </div>
          </div>
        </div>`;
      break;

    case 'data':
      const cacheStats = await API.get('/api/cache/stats').catch(() => ({ total: 0, movies: 0, series: 0 }));
      panel.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">Cache Management</div>
          <div class="settings-row">
            <div><div class="settings-label">Metadata Cache</div><div class="settings-desc">${cacheStats.total || 0} entries (movies: ${cacheStats.movies||0}, series: ${cacheStats.series||0})</div></div>
            <div class="settings-control">
              <button class="btn btn-sm" onclick="clearCache()">Clear Cache</button>
            </div>
          </div>
        </div>
        <div class="settings-group">
          <div class="settings-group-title">Database</div>
          <div class="settings-row">
            <div><div class="settings-label">Database Path</div></div>
            <div class="settings-control"><code style="font-size:11px;color:var(--text-muted);">data/database/jmdb.db</code></div>
          </div>
          <div style="padding-top:12px;font-size:12px;color:var(--text-muted);">
            ⚠ Resetting the database will delete all library data, history, and preferences.
          </div>
        </div>`;
      break;
  }
}

async function updateSetting(key, value) {
  try {
    await API.patch('/api/settings', { [key]: value });
    AppState.settings[key] = value;
    if (key === 'theme') AppState.setTheme(value);
    AppState.toast('Setting saved', 'success');
  } catch (e) {
    AppState.toast('Failed to save setting', 'error');
  }
}

function toggleSetting(key, el) {
  const current = AppState.settings[key];
  const newVal = !current;
  el.classList.toggle('on', newVal);
  updateSetting(key, newVal);
}

async function addFolder() {
  const result = await jmdb.openDirectory({ title: 'Add library folder' });
  if (result.canceled || !result.filePaths?.length) return;
  const folder = result.filePaths[0];
  const folders = [...(AppState.settings.library_folders || []), folder];
  await updateSetting('library_folders', folders);
  showSettingsPanel('library');
}

function removeFolder(btn) {
  const row = btn.closest('[style*="border-bottom"]');
  if (!row) return;
  const text = row.querySelector('span')?.textContent?.replace('📁 ', '') || '';
  const folders = (AppState.settings.library_folders || []).filter(f => f !== text);
  updateSetting('library_folders', folders);
  showSettingsPanel('library');
}

async function runScan() {
  const statusEl = document.getElementById('scanStatus');
  if (!statusEl) return;
  statusEl.textContent = 'Starting scan…';
  try {
    await API.post('/api/scan', { enrich: true });
    statusEl.textContent = 'Scan started in background. Check Status…';
    // Poll for completion
    const poll = setInterval(async () => {
      try {
        const st = await API.get('/api/scan/status');
        if (!st.running) {
          clearInterval(poll);
          statusEl.textContent = `Scan complete: ${JSON.stringify(st.summary)}`;
          AppState.updateCounts();
        }
      } catch {}
    }, 2000);
    setTimeout(() => clearInterval(poll), 120000); // Max 2 min polling
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
}

async function clearCache() {
  try {
    const r = await API.post('/api/cache/clear', {});
    AppState.toast(`Cleared ${r.cleared} cache entries`, 'success');
    showSettingsPanel('data');
  } catch (e) {
    AppState.toast(e.message, 'error');
  }
}
