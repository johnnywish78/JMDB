/**
 * JMDB — Main Entry Point
 * Handles navigation, API connection, and page routing.
 */
(function() {
  const PAGE_RENDERERS = {
    home: renderHome,
    movies: renderMovies,
    tv: renderTV,
    music: renderMusic,
    search: renderSearch,
    people: renderPeople,
    services: renderServices,
    browser: renderBrowser,
    settings: renderSettings,
    favorites: renderFavorites,
    watchlist: renderWatchlist,
    history: renderHistory,
    recommendations: renderRecommendations,
    statistics: renderStatistics,
    library: renderLibrary,
  };

  // Navigation
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const page = el.dataset.page;
      AppState.navigate(page);
    });
  });

  // Theme toggle
  document.getElementById('themeToggle')?.addEventListener('click', () => {
    const newTheme = AppState.theme === 'dark' ? 'light' : 'dark';
    AppState.setTheme(newTheme);
  });

  // Settings button
  document.getElementById('settingsBtn')?.addEventListener('click', () => {
    AppState.navigate('settings');
  });

  // Search input (topbar)
  const searchInput = document.getElementById('searchInput');
  let _searchTimer = null;
  searchInput?.addEventListener('input', () => {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => {
      const q = searchInput.value.trim();
      if (q.length >= 2) AppState.navigate('search');
    }, 400);
  });
  searchInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      clearTimeout(_searchTimer);
      const q = searchInput.value.trim();
      if (q.length >= 2) {
        AppState.navigate('search');
        setTimeout(() => {
          const inp = document.getElementById('pageSearchInput');
          if (inp) {
            inp.value = q;
            if (typeof doSearch === 'function') doSearch(q);
          }
        }, 100);
      }
    }
  });

  // Global keyboard shortcut: / to focus search
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault();
      searchInput?.focus();
      searchInput?.select();
    }
  });

  // Playback payload from Python side
  window.addEventListener('message', (event) => {
    if (event.data?.type === 'play-payload') {
      renderPlayer({ payload: event.data.payload });
    }
  });

  // Play requests forwarded by the Electron main process
  if (window.jmdb && typeof jmdb.onPlay === 'function') {
    jmdb.onPlay((payload) => renderPlayer({ payload }));
  }

  // Navigation dispatcher
  AppState.navigate = function(page, params = {}) {
    AppState._prevPage = AppState.currentPage;
    AppState.currentPage = page;
    AppState.currentMediaId = params.media_id || null;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.page === page);
    });

    // Render page
    const body = document.getElementById('contentBody');
    const loading = document.getElementById('contentLoading');
    const error = document.getElementById('contentError');
    body.classList.add('hidden');
    loading.classList.remove('hidden');
    error.classList.add('hidden');

    // Special handling for detail
    if (page === 'detail' && params.media_id) {
      renderDetail(params).catch(() => {});
      return;
    }

    // Player is handled separately
    if (page === 'player') {
      if (params.payload) renderPlayer({ payload: params.payload });
      return;
    }

    const renderer = PAGE_RENDERERS[page];
    if (renderer) {
      renderer(params).catch(err => {
        console.error(`Failed to render ${page}:`, err);
        body.innerHTML = `<div class="content-error"><div class="error-icon">⚠</div><h3>Failed to load ${page}</h3><p>${err.message || 'Unknown error'}</p><button onclick="AppState.navigate('${page}')">Retry</button></div>`;
        body.classList.remove('hidden');
        loading.classList.add('hidden');
      });
    } else {
      loading.classList.add('hidden');
      body.innerHTML = `<div class="empty-state"><div class="empty-icon">🔧</div><div class="empty-title">Page not found</div><div class="empty-msg">The "${esc(page)}" page hasn't been built yet.</div></div>`;
      body.classList.remove('hidden');
    }
  };

  // ── Startup ──────────────────────────────────────────────────────────────
  async function startup() {
    // Apply saved theme
    try {
      const settings = await API.get('/api/settings');
      AppState.settings = settings;
      AppState.setTheme(settings.theme || 'dark');
    } catch (e) {
      console.warn('Failed to load settings:', e);
      document.documentElement.setAttribute('data-theme', 'dark');
    }

    // Check backend
    try {
      const health = await API.get('/api/health');
      console.log('Backend connected:', health);
      await AppState.init();
      document.getElementById('contentLoading').classList.add('hidden');
      document.getElementById('contentBody').classList.remove('hidden');
      AppState.navigate('home');
    } catch (e) {
      console.error('Backend not reachable:', e);
      document.getElementById('contentLoading').classList.add('hidden');
      document.getElementById('contentError').classList.remove('hidden');
    }
  }

  startup();
})();
