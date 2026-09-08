/**
 * JMDB — Detail Page
 */
async function renderDetail(params) {
  const mediaId = params.media_id;
  if (!mediaId) { AppState.navigate('home'); return; }

  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';

  try {
    let item;
    let episodes = [];

    // Fetch based on kind
    if (params.kind === 'show') {
      const data = await API.get(`/api/shows/${mediaId}`);
      item = data;
      episodes = data.episodes || [];
    } else {
      item = await API.get(`/api/media/${mediaId}`);
      if (item && item.kind === 'show') {
        const data = await API.get(`/api/shows/${mediaId}`);
        episodes = data.episodes || [];
      }
    }

    // Favorite / watchlist state
    let isFav = false, inWatchlist = false;
    try {
      const [fav, wl] = await Promise.all([API.get('/api/favorites'), API.get('/api/watchlist')]);
      isFav = (fav.ids || []).includes(item.id);
      inWatchlist = (wl.ids || []).includes(item.id);
    } catch {}

    if (!item) {
      body.innerHTML = '<div class="content-error"><h3>Not found</h3></div>';
      return;
    }

    const backdrop = await resolveBackdrop(item);
    const posterUrl = await resolvePoster(item);
    const isMovie = item.kind === 'movie';
    const isShow = item.kind === 'show';

    let html = `
      <div style="margin:-20px -24px 20px;">
        ${backdrop
          ? `<div class="detail-backdrop" style="background-image:url('${backdrop}')"></div>`
          : `<div class="detail-backdrop" style="background:linear-gradient(135deg,#1a1d2e,#2a2d3e);"></div>`}
        <div class="detail-content">
          <div class="detail-header">
            <div class="detail-poster">
              ${posterUrl
                ? `<img src="${posterUrl}" alt="${esc(item.title)}">`
                : `<div class="placeholder">${(item.title.charAt(0) || '?').toUpperCase()}</div>`}
            </div>
            <div class="detail-info">
              <div class="detail-title">${esc(item.title)}</div>
              ${item.original_title && item.original_title !== item.title
                ? `<div class="detail-original">${esc(item.original_title)}</div>` : ''}
              <div class="detail-meta">
                <span>${item.year || '?'}</span>
                <span>·</span>
                <span>${item.runtime_min ? `${Math.floor(item.runtime_min/60)}h ${item.runtime_min%60}m` : ''}</span>
                <span>·</span>
                <span style="color:var(--accent);font-weight:700;">★ ${Number(item.rating || 0).toFixed(1)}</span>
                ${item.tmdb_id ? `<span>· TMDB ${item.tmdb_id}</span>` : ''}
                ${item.imdb_id ? `<span>· IMDb ${item.imdb_id}</span>` : ''}
              </div>
              <div class="detail-genres">
                ${(item.genres || []).map(g => `<span class="genre-tag">${esc(g)}</span>`).join('')}
              </div>
              <div class="detail-overview">${esc(item.overview || 'No synopsis available. Enrich metadata via Settings → Scan.')}</div>
              <div class="detail-actions">
                ${item.file_path
                  ? `<button class="btn btn-accent" onclick="playFromDetail(${item.id})">▶ Play</button>`
                  : (isShow ? `<button class="btn" style="opacity:0.6" disabled>Select an episode below</button>` : `<button class="btn" disabled>No media file linked</button>`)}
                <button class="btn" id="favBtn" onclick="toggleFavorite(${item.id})">${isFav ? '♥ Favorited' : '♡ Favorite'}</button>
                <button class="btn" id="wlBtn" onclick="toggleWatchlist(${item.id})">${inWatchlist ? '✓ In Watchlist' : '+ Watchlist'}</button>
                <button class="btn" onclick="reEnrich(${item.id})">↻ Re-enrich</button>
              </div>
              <div class="detail-stats">
                <div class="stat-item"><div class="stat-value">${item.year || '—'}</div><div class="stat-label">Year</div></div>
                <div class="stat-item"><div class="stat-value">${item.runtime_min ? Math.floor(item.runtime_min/60) + 'h' : '—'}</div><div class="stat-label">Runtime</div></div>
                <div class="stat-item"><div class="stat-value">${item.tmdb_id || '—'}</div><div class="stat-label">TMDB ID</div></div>
                <div class="stat-item"><div class="stat-value">${item.imdb_id || '—'}</div><div class="stat-label">IMDb ID</div></div>
              </div>
            </div>
          </div>
        </div>
      </div>`;

    // Episodes section for shows
    if (isShow && episodes.length > 0) {
      html += `<div class="section-header"><span class="section-title">Episodes</span><span class="section-sub">${episodes.length} episodes</span></div>`;
      html += `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;">`;
      for (const ep of episodes.slice(0, 20)) {
        html += `
          <div style="display:flex;align-items:center;gap:14px;padding:10px 14px;border-bottom:1px solid var(--border);cursor:pointer;transition:background 0.1s;"
               onmouseover="this.style.background='var(--bg-hover)'" onmouseout="this.style.background=''"
               onclick="playEpisode(${item.id},${ep.id})">
            <span style="font-weight:700;color:var(--text-muted);min-width:50px;">S${ep.season}E${ep.number}</span>
            <span style="flex:1;font-size:13px;">${esc(ep.title || `Episode ${ep.number}`)}</span>
            <span style="font-size:12px;color:var(--text-muted);">${ep.runtime_min ? Math.floor(ep.runtime_min/60) + 'm' : ''}</span>
            ${ep.file_path ? '<span style="color:var(--accent);font-size:16px;">▶</span>' : '<span style="color:var(--text-muted);font-size:12px;">No file</span>'}
          </div>`;
      }
      html += `</div>`;
    }

    body.innerHTML = html;
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');

  } catch (e) {
    body.innerHTML = `<div class="content-error"><div class="error-icon">⚠</div><h3>Failed to load detail</h3><p>${esc(e.message)}</p><button onclick="AppState.navigate('movies')">Back</button></div>`;
  }
}

function playFromDetail(mediaId) {
  API.get(`/api/media/${mediaId}`).then(item => {
    if (item && item.file_path) {
      const payload = {
        media_key: `m:${item.id}`,
        title: item.title,
        subtitle: `${item.year || ''} · ${item.runtime_min || 0} min`,
        file_path: item.file_path,
        duration_s: (item.runtime_min || 0) * 60,
        media_id: item.id,
      };
      jmdb.playMedia(payload);
    }
  });
}

function playEpisode(showId, episodeId) {
  Promise.all([API.get(`/api/shows/${showId}`), API.get(`/api/episodes/${episodeId}`)])
    .then(([show, ep]) => {
      if (ep && ep.file_path) {
        const payload = {
          media_key: `e:${ep.id}`,
          title: show.title,
          subtitle: `S${ep.season} E${ep.number} · ${ep.title || ''}`,
          file_path: ep.file_path,
          duration_s: (ep.runtime_min || show.runtime_min || 0) * 60,
          episode_id: ep.id,
          show_id: show.id,
          season: ep.season,
          number: ep.number,
        };
        jmdb.playMedia(payload);
      }
    });
}

async function toggleFavorite(mediaId) {
  try {
    const r = await API.post(`/api/favorites/${mediaId}`, {});
    const btn = document.getElementById('favBtn');
    if (btn) btn.textContent = r.favorited ? '♥ Favorited' : '♡ Favorite';
    AppState.toast(r.favorited ? 'Added to favorites' : 'Removed from favorites', 'success');
  } catch (e) { AppState.toast(e.message, 'error'); }
}

async function toggleWatchlist(mediaId) {
  try {
    const r = await API.post(`/api/watchlist/${mediaId}`, {});
    const btn = document.getElementById('wlBtn');
    if (btn) btn.textContent = r.in_watchlist ? '✓ In Watchlist' : '+ Watchlist';
    AppState.toast(r.in_watchlist ? 'Added to watchlist' : 'Removed from watchlist', 'success');
  } catch (e) { AppState.toast(e.message, 'error'); }
}

async function reEnrich(mediaId) {
  AppState.toast('Re-enriching metadata…', 'info');
  try {
    await API.post(`/api/re-enrich/${mediaId}`, { clear_cache: true });
    AppState.toast('Metadata updated!', 'success');
    renderDetail({ media_id: mediaId });
  } catch (e) {
    AppState.toast(e.message, 'error');
  }
}
