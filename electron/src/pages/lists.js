/**
 * JMDB — Personal lists & stats pages.
 * Favorites / Watchlist / History / Recommendations / Statistics / Library.
 */

async function _renderGridPage(endpoint, title, emptyMsg, opts = {}) {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';
  try {
    const data = await API.get(endpoint);
    const items = data.items || [];
    body.innerHTML = `<div class="section-header"><span class="section-title">${title}</span><span class="section-sub">${items.length} titles</span></div>`;
    const grid = document.createElement('div');
    body.appendChild(grid);
    if (items.length === 0) {
      grid.innerHTML = `<div class="empty-state"><div class="empty-icon">🎬</div><div class="empty-title">Nothing here yet</div><div class="empty-msg">${emptyMsg}</div></div>`;
    } else {
      renderCardsGrid(grid, items, opts);
    }
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><div class="error-icon">⚠</div><h3>Failed to load ${title}</h3><p>${esc(e.message)}</p><button onclick="AppState.navigate('${opts.retry || 'home'}')">Retry</button></div>`;
  }
}

async function renderFavorites() {
  await _renderGridPage('/api/favorites', 'Favorites', 'Mark titles as favorites from their detail page.', { retry: 'favorites' });
}

async function renderWatchlist() {
  await _renderGridPage('/api/watchlist', 'Watchlist', 'Add titles to your watchlist to keep track of what to watch next.', { retry: 'watchlist' });
}

async function renderRecommendations() {
  await _renderGridPage('/api/recommendations', 'Recommended For You', 'Recommendations improve as you favorite, rate, and watch titles.', { retry: 'recommendations' });
}

async function renderHistory() {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';
  try {
    const data = await API.get('/api/history');
    const entries = data.entries || [];
    let html = `<div class="section-header"><span class="section-title">History</span><span class="section-sub">${entries.length} sessions</span></div>`;
    if (entries.length === 0) {
      html += `<div class="empty-state"><div class="empty-icon">🕘</div><div class="empty-title">No watch history</div><div class="empty-msg">Played media will appear here.</div></div>`;
    } else {
      html += `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;">`;
      for (const h of entries.slice(0, 100)) {
        html += `<div style="display:flex;align-items:center;gap:14px;padding:10px 14px;border-bottom:1px solid var(--border);">
          <span style="font-size:16px;">▶</span>
          <div style="flex:1;">
            <div style="font-size:13px;font-weight:600;">${esc(h.media_title)}</div>
            <div style="font-size:11px;color:var(--text-muted);">${esc(h.subtitle || '')}</div>
          </div>
          <span style="font-size:11px;color:var(--text-muted);">${new Date(h.finished_at).toLocaleString()}</span>
        </div>`;
      }
      html += `</div>`;
    }
    body.innerHTML = html;
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><p>${esc(e.message)}</p></div>`;
  }
}

async function renderStatistics() {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';
  try {
    const s = await API.get('/api/statistics');
    const lib = s.library || {};
    const cards = [
      ['Movies', lib.movie || 0], ['TV Shows', lib.show || 0], ['Music', lib.music || 0],
      ['Watched', (s.movies_watched || 0) + (s.episodes_watched || 0)],
      ['Hours Watched', s.hours || 0], ['Favorites', s.favorites || 0],
      ['Watchlist', s.watchlist || 0], ['Day Streak', s.streak || 0],
    ];
    let html = `<div class="section-header"><span class="section-title">Statistics</span></div>`;
    html += `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-bottom:20px;">`;
    for (const [label, val] of cards) {
      html += `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:14px;text-align:center;">
        <div style="font-size:22px;font-weight:800;color:var(--accent);">${val}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${label}</div>
      </div>`;
    }
    html += `</div>`;

    if (s.top_genres && s.top_genres.length) {
      const max = Math.max(...s.top_genres.map(g => g[1]));
      html += `<div class="section-header"><span class="section-title">Top Genres</span></div><div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:20px;">`;
      for (const [g, w] of s.top_genres) {
        const pct = Math.round((w / max) * 100);
        html += `<div style="margin-bottom:10px;"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;"><span>${esc(g)}</span><span style="color:var(--text-muted);">${w.toFixed(1)}</span></div>
          <div style="height:6px;background:var(--bg-hover);border-radius:3px;"><div style="height:100%;width:${pct}%;background:var(--accent);border-radius:3px;"></div></div></div>`;
      }
      html += `</div>`;
    }

    if (s.activity && s.activity.length) {
      html += `<div class="section-header"><span class="section-title">Activity (14 days)</span></div><div style="display:flex;gap:4px;align-items:flex-end;height:80px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:12px;">`;
      const maxC = Math.max(1, ...s.activity.map(a => a.count));
      for (const a of s.activity) {
        const h = Math.max(4, Math.round((a.count / maxC) * 56));
        html += `<div title="${a.date}: ${a.count}" style="flex:1;height:${h}px;background:${a.count ? 'var(--accent)' : 'var(--bg-hover)'};border-radius:2px;"></div>`;
      }
      html += `</div>`;
    }

    body.innerHTML = html;
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><p>${esc(e.message)}</p></div>`;
  }
}

// ── Library management (Add Location / Scan / Scan All) ──────────────────────
let _scanPoll = null;

async function renderLibrary() {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';
  try {
    const settings = await API.get('/api/settings');
    const folders = settings.library_folders || [];
    let html = `<div class="section-header"><span class="section-title">Library</span><span class="section-sub">Locations & scanning</span></div>`;
    html += `<div class="settings-group">
      <div class="settings-group-title">Locations</div>
      <div id="libFolderList" style="margin-bottom:12px;">${folders.map(f => `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);"><span style="flex:1;font-size:13px;color:var(--text-secondary);">📁 ${esc(f)}</span><button class="btn btn-sm" style="color:var(--danger);" onclick="removeLibraryFolder('${esc(f)}')">✕</button></div>`).join('') || '<div style="color:var(--text-muted);font-size:13px;">No locations added yet.</div>'}</div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-sm" onclick="addLibraryFolder()">+ Add Location</button>
        <button class="btn btn-sm btn-accent" onclick="startScan()">▶ Scan All</button>
      </div>
      <div id="scanStatusBox" style="margin-top:12px;font-size:13px;color:var(--text-muted);"></div>
    </div>`;
    html += `<div id="libGrids"></div>`;
    body.innerHTML = html;
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
    pollScanStatus();
    _loadLibraryGrids();
  } catch (e) {
    body.innerHTML = `<div class="content-error"><p>${esc(e.message)}</p></div>`;
  }
}

async function _loadLibraryGrids() {
  const holder = document.getElementById('libGrids');
  if (!holder) return;
  holder.innerHTML = '';
  for (const [kind, title] of [['movie', 'Movies'], ['show', 'TV Shows'], ['music', 'Music']]) {
    try {
      const data = await API.get(`/api/library/${kind}`);
      const items = data.items || [];
      const sec = document.createElement('div');
      sec.innerHTML = `<div class="section-header"><span class="section-title">${title}</span><span class="section-sub">${items.length}</span></div>`;
      const grid = document.createElement('div');
      sec.appendChild(grid);
      renderCardsGrid(grid, items.slice(0, 12));
      holder.appendChild(sec);
    } catch {}
  }
}

async function addLibraryFolder() {
  const result = await jmdb.openDirectory({ title: 'Add library location' });
  if (result.canceled || !result.filePaths?.length) return;
  const folder = result.filePaths[0];
  const settings = await API.get('/api/settings');
  const folders = [...(settings.library_folders || []), folder];
  await API.patch('/api/settings', { library_folders: folders });
  AppState.toast('Location added', 'success');
  renderLibrary();
}

async function removeLibraryFolder(folder) {
  const settings = await API.get('/api/settings');
  const folders = (settings.library_folders || []).filter(f => f !== folder);
  await API.patch('/api/settings', { library_folders: folders });
  AppState.toast('Location removed', 'info');
  renderLibrary();
}

async function startScan() {
  const box = document.getElementById('scanStatusBox');
  if (box) box.textContent = 'Starting scan…';
  try {
    await API.post('/api/scan', { enrich: true });
    pollScanStatus();
  } catch (e) {
    if (box) box.textContent = `Error: ${e.message}`;
  }
}

async function pollScanStatus() {
  if (_scanPoll) clearInterval(_scanPoll);
  const tick = async () => {
    const box = document.getElementById('scanStatusBox');
    if (!box) { clearInterval(_scanPoll); _scanPoll = null; return; }
    try {
      const st = await API.get('/api/scan/status');
      if (st.running) {
        const d = st.discovered || {};
        box.textContent = `Scanning ${st.scanned || 0}/${st.total || 0} — ${st.current_file || ''} (movies ${d.movies || 0}, episodes ${d.episodes || 0}, music ${d.music || 0})`;
      } else if (st.summary) {
        const s = st.summary;
        if (s.error) box.textContent = `Scan error: ${s.error}`;
        else box.textContent = `Scan complete — movies ${s.movies || 0}, episodes ${s.episodes || 0}, music ${s.music || 0}, enriched ${s.enriched || 0}, errors ${s.errors || 0}`;
        clearInterval(_scanPoll); _scanPoll = null;
        AppState.updateCounts();
        _loadLibraryGrids();
      } else {
        box.textContent = 'Idle.';
      }
    } catch {}
  };
  tick();
  _scanPoll = setInterval(tick, 1000);
}
