// JMDB Application Controller
const App = {
  port: 8765,
  currentPage: 'home',
  searchDebounce: null,

  init() {
    console.log('JMDB v1.0.0 initialized');
    this.setupEventListeners();
    this.setupDropdowns();
    this.setupKeyboard();
    this.setupErrorHandling();

    if (window.jmdb && window.jmdb.getBackendPort) {
      window.jmdb.getBackendPort().then(port => {
        this.port = parseInt(port) || 8765;
      }).catch(() => {});
    }

    this.nav('home');
  },

  setupErrorHandling() {
    window.onerror = (msg, url, line, col, err) => {
      console.error(`[JMDB Error] ${msg} at ${line}:${col}`);
      return false;
    };
    window.addEventListener('unhandledrejection', (e) => {
      console.error('[JMDB Unhandled Rejection]', e.reason);
    });
  },

  setupEventListeners() {
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const page = item.dataset.page;
        const type = item.dataset.type;
        this.nav(page, { type });
        this.closeAllDropdowns();
      });
    });

    document.querySelectorAll('.nav-item[data-action]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const action = item.dataset.action;
        this.handleAction(action);
        this.closeAllDropdowns();
      });
    });

    const searchInput = document.getElementById('global-search');
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const q = searchInput.value.trim();
          if (q.length >= 2) {
            this.nav('search', { q });
            searchInput.blur();
          }
        } else if (e.key === 'Escape') {
          searchInput.value = '';
          this.hideSearchResults();
        }
      });
      searchInput.addEventListener('input', () => {
        clearTimeout(this.searchDebounce);
        const q = searchInput.value.trim();
        if (q.length >= 2) {
          this.searchDebounce = setTimeout(() => this.liveSearch(q), 300);
        } else {
          this.hideSearchResults();
        }
      });
    }

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.search-box')) {
        this.hideSearchResults();
      }
    });

    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => this.toggleTheme());
    }
  },

  setupDropdowns() {
    // Reliable action handling for dropdown items.
    // Capture phase guarantees the action is received even if another
    // renderer handler stops normal bubbling.
    document.addEventListener('click', (e) => {
      const item = e.target.closest('.dropdown-item[data-action]');
      if (!item) return;

      const action = item.dataset.action;
      if (action !== 'add-location') return;

      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      console.log('[JMDB] captured dropdown action:', action);
      this.handleAction(action);
      this.closeAllDropdowns();
    }, true);

    document.querySelectorAll('.dropdown-trigger').forEach(trigger => {
      trigger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggleDropdown(trigger);
      });
      trigger.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.toggleDropdown(trigger);
        }
        if (e.key === 'Escape') {
          this.closeAllDropdowns();
        }
      });
    });

    document.querySelectorAll('.dropdown-item[data-page], .dropdown-item[data-action]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const page = item.dataset.page;
        const type = item.dataset.type;
        const action = item.dataset.action;

        console.log('[JMDB] dropdown item clicked:', { page, type, action });

        if (page) {
          this.nav(page, { type });
        } else if (action) {
          console.log('[JMDB] handling action:', action);
          this.handleAction(action);
        }

        this.closeAllDropdowns();
      });

      item.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          item.click();
        }
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          const next = item.parentElement.querySelector('.dropdown-item:focus, [tabindex="-1"]:not(:focus)') 
            || item.nextElementSibling;
          if (next) next.focus();
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          const prev = item.previousElementSibling;
          if (prev) prev.focus();
        }
      });
    });
  },

  toggleDropdown(trigger) {
    const parent = trigger.closest('.nav-dropdown');
    const menu = parent?.querySelector('.dropdown-menu');
    if (!menu) return;

    const isOpen = trigger.getAttribute('aria-expanded') === 'true';
    this.closeAllDropdowns();

    if (!isOpen) {
      trigger.setAttribute('aria-expanded', 'true');
      menu.style.display = 'block';
    }
  },

  closeAllDropdowns() {
    document.querySelectorAll('.dropdown-trigger').forEach(t => t.setAttribute('aria-expanded', 'false'));
    document.querySelectorAll('.dropdown-menu').forEach(m => m.style.display = 'none');
  },

  setupKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && !e.target.matches('input, textarea, select')) {
        e.preventDefault();
        document.getElementById('global-search')?.focus();
      }
      if (e.key === 'Escape') {
        this.closeAllDropdowns();
        this.hideSearchResults();
        const modal = document.getElementById('modal-container');
        if (modal && modal.innerHTML.trim()) {
          modal.innerHTML = '';
        }
      }
    });
  },

  handleAction(action) {
    if (action === 'add-location') {
      this.showAddLocationModal();
    } else if (action === 'scan-all') {
      this.scanAllLocations();
    } else if (action === 'scan') {
      this.nav('scan-history');
    }
  },

  setActiveNav(page) {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    const targets = ['.nav-item[data-page="' + page + '"]', '.nav-item[data-action="' + page + '"]'];
    for (const sel of targets) {
      const el = document.querySelector(sel);
      if (el) { el.classList.add('active'); break; }
    }
  },

  nav(page, params = {}) {
    this.currentPage = page;
    this.setActiveNav(page);
    this.closeAllDropdowns();
    this.hideSearchResults();

    const container = document.getElementById('page-container');
    if (!container) { console.error('page-container not found'); return; }

    container.innerHTML = '';

    const pageRenderers = {
      home: () => this.renderHome(container),
      library: () => this.renderLibrary(container, params.type || 'all'),
      locations: () => this.renderLocations(container),
      search: () => this.renderSearch(container, params),
      browser: () => this.renderBrowser(container),
      player: () => this.renderPlayer(container),
      services: () => this.renderServices(container),
      settings: () => { if (typeof Settings !== 'undefined') Settings.init(container); else this.renderGenericSettings(container); },
      scan_history: () => this.renderScanHistory(container),
      scan_problems: () => this.renderScanProblems(container),
      favorites: () => this.renderLibrary(container, 'favorite'),
      statistics: () => this.renderStatistics(container),
      activity: () => this.renderActivity(container),
      help: () => this.renderHelp(container),
      about: () => this.renderAbout(container),
      diagnostics: () => this.renderDiagnostics(container)
    };

    (pageRenderers[page] || (() => {
      container.innerHTML = `<div class="empty-state"><h2>${this.escapeHtml(page)}</h2><p>Page coming soon</p></div>`;
    }))();
  },

  renderHome(container) {
    container.innerHTML = `
      <section class="hero-section">
        <div class="hero-backdrop"></div>
        <div class="hero-overlay"></div>

        <div class="hero-content">
          <div class="hero-poster" aria-hidden="true">
            <div class="hero-poster-mark">J</div>
          </div>

          <div class="hero-info">
            <div class="hero-kicker">YOUR PERSONAL MEDIA UNIVERSE</div>
            <h1 class="hero-title">Welcome to JMDB</h1>
            <div class="hero-meta">Johnny's Media Database <span>•</span> v1.0.0</div>
            <p class="hero-overview">
              Your personal media library, beautifully organized.
              Discover, manage and play your collection from one cinematic home.
            </p>

            <div class="hero-actions">
              <button class="btn btn-primary" id="home-add-location">
                <span class="btn-icon">+</span>
                Add Location
              </button>
              <button class="btn btn-secondary" id="home-explore">
                Explore Library
              </button>
            </div>
          </div>
        </div>
      </section>

      ${this.renderSection('Continue Watching', 'continue-row', 'library', { type: 'continue_watching' }, true)}
      ${this.renderSection('Recently Added', 'recent-row', 'library', { type: 'all' }, true)}
      ${this.renderSection('Favorites', 'fav-row', 'library', { type: 'favorite' }, true)}
    `;

    document.getElementById('home-add-location')?.addEventListener('click', () => {
      this.nav('locations');
    });

    document.getElementById('home-explore')?.addEventListener('click', () => {
      this.nav('library', { type: 'all' });
    });

    this.loadMediaRow(
      'continue-row',
      `http://127.0.0.1:${this.port}/api/media/continue-watching?limit=10`
    );

    this.loadMediaRow(
      'recent-row',
      `http://127.0.0.1:${this.port}/api/media/recent?limit=10`
    );

    this.loadMediaRow(
      'fav-row',
      `http://127.0.0.1:${this.port}/api/media/favorites?limit=10`
    );
  },

  renderSection(title, rowId, navPage, navParams, scrollable = true) {
    return `
      <section class="section media-section">
        <div class="section-header">
          <div class="section-heading">
            <h2 class="section-title">${this.escapeHtml(title)}</h2>
            <span class="section-accent"></span>
          </div>

          <button
            class="view-all"
            data-page="${navPage}"
            data-type="${navParams.type || ''}"
            type="button"
          >
            View All
            <span aria-hidden="true">→</span>
          </button>
        </div>

        <div class="media-row ${scrollable ? 'media-row-scroll' : ''}" id="${rowId}">
          <div class="media-row-loading">
            <span class="loading-pulse"></span>
            <span>Loading your collection…</span>
          </div>
        </div>
      </section>
    `;
  },

  async loadMediaRow(rowId, url) {
    const row = document.getElementById(rowId);
    if (!row) return;

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const items = data.items || [];

      if (items.length > 0) {
        row.innerHTML = items.map(item => this.mediaCard(item)).join('');
      } else {
        row.innerHTML = `
          <div class="media-row-empty">
            <div class="media-row-empty-icon"></div>
            <span>No titles here yet</span>
          </div>
        `;
      }
    } catch (e) {
      console.error(`Failed to load ${rowId}:`, e);

      row.innerHTML = `
        <div class="media-row-empty media-row-error">
          <span>Unable to load this section</span>
        </div>
      `;
    }
  },

  mediaCard(item, clickable = true) {
    const poster = item.artwork?.find(a => a.is_primary)?.url
      || item.artwork?.[0]?.url
      || '';

    const title = this.escapeHtml(item.title || 'Untitled');
    const mediaType = this.escapeHtml(item.media_type || 'media');
    const year = item.year || '';

    const posterHTML = poster
      ? `
        <img
          src="${this.escapeHtml(poster)}"
          alt="${title}"
          class="card-poster-image"
          loading="lazy"
        >
      `
      : `
        <div class="card-poster-fallback" aria-hidden="true">
          <span class="card-poster-fallback-mark">J</span>
        </div>
      `;

    const clickHandler = clickable
      ? `onclick="App.showMediaDetail(${Number(item.id)})"`
      : '';

    const ctxClickHandler = clickable
      ? `oncontextmenu="App.showMediaContext(event, ${Number(item.id)})"`
      : '';

    return `
      <article
        class="media-card"
        ${clickHandler}
        ${ctxClickHandler}
        data-media-id="${Number(item.id)}"
        tabindex="${clickable ? '0' : '-1'}"
        role="${clickable ? 'button' : 'article'}"
        aria-label="${title}"
      >
        <div class="card-poster">
          ${posterHTML}

          <div class="card-poster-shade"></div>

          ${item.favorite ? `
            <div class="card-favorite" title="Favorite" aria-label="Favorite">
              <span>★</span>
            </div>
          ` : ''}

          ${item.progress != null && Number(item.progress) > 0 ? `
            <div class="card-progress">
              <span style="--progress:${Math.min(100, Math.max(0, Number(item.progress)))}%"></span>
            </div>
          ` : ''}
        </div>

        <div class="card-info">
          <div class="card-title" title="${title}">${title}</div>
          <div class="card-meta">
            ${year ? `<span>${year}</span><span class="card-meta-dot">•</span>` : ''}
            <span>${mediaType.replace('_', ' ')}</span>
          </div>
        </div>
      </article>
    `;
  },

  renderLibrary(container, type) {
    const titles = {
      all: 'All Media',
      movie: 'Movies',
      tv_show: 'TV Shows',
      episode: 'Episodes',
      collection: 'Collections',
      favorite: 'Favorites',
      recently_added: 'Recently Added',
      recently_played: 'Recently Played',
      continue_watching: 'Continue Watching',
      watched: 'Watched',
      unwatched: 'Unwatched'
    };

    const title = titles[type] || 'Library';

    container.innerHTML = `
      <section class="library-page">
        <header class="library-header">
          <div class="library-heading">
            <span class="library-kicker">YOUR COLLECTION</span>
            <h1 class="library-title">${title}</h1>
            <p class="library-subtitle">
              Your personal media collection, organized for discovery.
            </p>
          </div>

          <div class="library-toolbar">
            <label class="library-sort">
              <span>Sort</span>
              <select id="lib-sort" class="form-select" onchange="App.sortLibrary(this.value)">
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="title">Title A-Z</option>
                <option value="rating">Rating</option>
              </select>
            </label>

            <button
              class="library-view-toggle active"
              type="button"
              aria-label="Grid view"
              title="Grid view"
            >▦</button>
          </div>
        </header>

        <nav class="library-tabs" aria-label="Library sections">
          <button class="library-tab ${type === 'all' ? 'active' : ''}"
                  onclick="App.nav('library', {type:'all'})">All Media</button>
          <button class="library-tab ${type === 'movie' ? 'active' : ''}"
                  onclick="App.nav('library', {type:'movie'})">Movies</button>
          <button class="library-tab ${type === 'tv_show' ? 'active' : ''}"
                  onclick="App.nav('library', {type:'tv_show'})">TV Shows</button>
          <button class="library-tab ${type === 'episode' ? 'active' : ''}"
                  onclick="App.nav('library', {type:'episode'})">Episodes</button>
          <button class="library-tab ${type === 'favorite' ? 'active' : ''}"
                  onclick="App.nav('library', {type:'favorite'})">Favorites</button>
        </nav>

        <div class="library-summary">
          <span class="library-summary-label">COLLECTION</span>
          <span id="library-count" class="library-summary-count">Loading…</span>
        </div>

        <div id="lib-grid" class="library-grid">
          ${Array.from({ length: 10 }, () => `
            <div class="library-skeleton" aria-hidden="true">
              <div class="library-skeleton-poster"></div>
              <div class="library-skeleton-title"></div>
              <div class="library-skeleton-meta"></div>
            </div>
          `).join('')}
        </div>

        <div id="lib-load-more" class="library-load-more">
          <button class="btn btn-secondary" onclick="App.loadMoreLibrary()">
            Load More
          </button>
        </div>
      </section>
    `;

    this.currentLibType = type;
    this.currentLibSort = 'newest';
    this.currentLibOffset = 0;
    this.loadLibraryGrid(type, 0);
  },

  async loadLibraryGrid(type, offset = 0) {
    const sort = this.currentLibSort || 'newest';

    let url = `http://127.0.0.1:${this.port}/api/media?limit=20&offset=${offset}`;
    url += `&sort=${encodeURIComponent(sort)}`;

    if (type === 'favorite') {
      url += '&favorite=true';
    } else if (type !== 'all' && ['movie', 'tv_show', 'episode'].includes(type)) {
      url += `&media_type=${encodeURIComponent(type)}`;
    }

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const grid = document.getElementById('lib-grid');
      const count = document.getElementById('library-count');
      const loadMore = document.getElementById('lib-load-more');

      if (!grid) return;

      const items = data.items || [];
      const total = Number(data.total || 0);

      if (count) {
        count.textContent = `${total.toLocaleString()} ${total === 1 ? 'title' : 'titles'}`;
      }

      if (offset === 0) {
        grid.innerHTML = '';
      }

      if (items.length > 0) {
        grid.insertAdjacentHTML(
          'beforeend',
          items.map(item => this.mediaCard(item)).join('')
        );
      } else if (offset === 0) {
        grid.innerHTML = `
          <div class="library-empty">
            <div class="library-empty-icon">◈</div>
            <h2>No media found</h2>
            <p>Add a media location and scan your library to start building your collection.</p>
            <button class="btn btn-primary" onclick="App.nav('locations')">
              Manage Locations
            </button>
          </div>
        `;
      }

      if (loadMore) {
        loadMore.classList.toggle(
          'visible',
          total > offset + items.length
        );
      }
    } catch (e) {
      console.error('Failed to load library:', e);

      const grid = document.getElementById('lib-grid');
      const count = document.getElementById('library-count');
      const loadMore = document.getElementById('lib-load-more');

      if (count) count.textContent = 'Unavailable';
      if (loadMore) loadMore.classList.remove('visible');

      if (grid) {
        grid.innerHTML = `
          <div class="library-empty library-empty-error">
            <div class="library-empty-icon">!</div>
            <h2>Library unavailable</h2>
            <p>JMDB could not load your media collection right now.</p>
          </div>
        `;
      }
    }
  },

  sortLibrary(by) {
    const allowed = ['newest', 'oldest', 'title', 'rating'];

    this.currentLibSort = allowed.includes(by) ? by : 'newest';
    this.currentLibOffset = 0;

    this.loadLibraryGrid(
      this.currentLibType || 'all',
      0
    );
  },

  loadMoreLibrary() {
    this.currentLibOffset = (this.currentLibOffset || 0) + 20;
    this.loadLibraryGrid(this.currentLibType || 'all', this.currentLibOffset);
  },

  renderLocations(container) {
    container.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;">
        <h2>Manage Locations</h2>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-sm btn-secondary" onclick="App.scanAllLocations()">Scan All</button>
          <button class="btn btn-primary" onclick="App.showAddLocationModal()">+ Add Location</button>
        </div>
      </div>
      <div id="locations-list" style="display:flex;flex-direction:column;gap:12px;"></div>
    `;
    this.loadLocations();
  },

  async loadLocations() {
    const list = document.getElementById('locations-list');
    if (!list) return;
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library`);
      const data = await res.json();
      const libs = data.libraries || [];
      if (libs.length > 0) {
        list.innerHTML = libs.map(lib => `
          <div class="location-item">
            <div class="loc-info">
              <h3>${this.escapeHtml(lib.name)}</h3>
              <p>${this.escapeHtml(lib.path)} • ${lib.media_type} • Status: ${lib.scan_status}</p>
              ${lib.last_scan_at ? `<p style="font-size:11px;color:var(--text-muted);">Last scan: ${new Date(lib.last_scan_at).toLocaleString()}</p>` : ''}
            </div>
            <div style="display:flex;gap:8px;flex-shrink:0;">
              <button class="btn btn-sm btn-primary" onclick="App.scanLocation(${lib.id})">Scan</button>
              <button class="btn btn-sm btn-danger" onclick="App.deleteLocation(${lib.id})">Remove</button>
            </div>
          </div>
        `).join('');
      } else {
        list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📁</div><div class="empty-state-title">No locations yet</div><p>Add a media folder to start scanning your collection.</p></div>';
      }
    } catch (e) {
      console.error('Failed to load locations:', e);
      list.innerHTML = '<div class="empty-state"><p>Failed to load locations</p></div>';
    }
  },

  showAddLocationModal() {
    const modal = document.getElementById('modal-container');
    if (!modal) return;
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3>Add Location</h3>
          <button class="modal-close" onclick="App.closeModal()" aria-label="Close">✕</button>
        </div>
        <div class="modal-body">
          <div style="margin-bottom:16px;">
            <label style="display:block;margin-bottom:8px;font-size:14px;font-weight:500;">Name</label>
            <input type="text" id="loc-name" class="form-input" placeholder="My Movies" autofocus>
          </div>
          <div style="margin-bottom:16px;">
            <label style="display:block;margin-bottom:8px;font-size:14px;font-weight:500;">Type</label>
            <select id="loc-type" class="form-select">
              <option value="movie">Movies</option>
              <option value="tv_show">TV Shows</option>
              <option value="music">Music</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div style="margin-bottom:16px;">
            <label style="display:block;margin-bottom:8px;font-size:14px;font-weight:500;">Path</label>
            <div style="display:flex;gap:8px;">
              <input type="text" id="loc-path" class="form-input" placeholder="/path/to/media">
              <button class="btn btn-sm btn-secondary" onclick="App.browseFolder()">Browse</button>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="App.createLocation()">Add Location</button>
        </div>
      </div>
    `;
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    document.getElementById('loc-name')?.focus();
  },

  closeModal() {
    const modal = document.getElementById('modal-container');
    if (modal) {
      modal.innerHTML = '';
      modal.style.display = 'none';
      modal.setAttribute('aria-hidden', 'true');
    }
  },

  async browseFolder() {
    if (window.jmdb && window.jmdb.openDirectory) {
      try {
        const path = await window.jmdb.openDirectory();
        if (path) {
          const pathInput = document.getElementById('loc-path');
          if (pathInput) pathInput.value = path;
        }
      } catch (e) {
        this.toast('Failed to open folder dialog', 'error');
      }
    } else {
      this.toast('File dialog not available - run in Electron', 'error');
    }
  },

  async createLocation() {
    const name = document.getElementById('loc-name')?.value.trim();
    const type = document.getElementById('loc-type')?.value || 'movie';
    const path = document.getElementById('loc-path')?.value.trim();

    if (!path) {
      this.toast('Please select a media folder', 'error');
      return;
    }

    // Name is optional. If empty, derive it from the selected path.
    const finalName = name || path.replace(/\\/g, '/').split('/').filter(Boolean).pop() || 'Media';

    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: finalName, media_type: type, path })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      this.toast('Location added successfully', 'success');
      this.closeModal();
      this.nav('locations');
    } catch (e) {
      console.error('Failed to add location:', e);
      this.toast(`Failed to add location: ${e.message}`, 'error');
    }
  },

  async scanLocation(id) {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = 'Scanning...'; }
    this.toast('Scan started...', 'info');
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library/${id}/scan`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const interval = setInterval(async () => {
        try {
          const status = await fetch(`http://127.0.0.1:${this.port}/api/library/scan-status`).then(r => r.json());
          if (!status.active) {
            clearInterval(interval);
            if (btn) { btn.disabled = false; btn.textContent = 'Scan'; }
            this.toast('Scan completed', 'success');
            this.loadLocations();
          }
        } catch (_) { clearInterval(interval); }
      }, 2000);
    } catch (e) {
      console.error('Scan failed:', e);
      this.toast('Scan failed', 'error');
      if (btn) { btn.disabled = false; btn.textContent = 'Scan'; }
    }
  },

  async scanAllLocations() {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library`);
      const data = await res.json();
      const libs = data.libraries || [];
      if (libs.length === 0) {
        this.toast('No locations to scan', 'error');
        return;
      }
      for (const lib of libs) {
        await fetch(`http://127.0.0.1:${this.port}/api/library/${lib.id}/scan`, { method: 'POST' });
      }
      this.toast('Scanning all locations...', 'info');
      const interval = setInterval(async () => {
        try {
          const status = await fetch(`http://127.0.0.1:${this.port}/api/library/scan-status`).then(r => r.json());
          if (!status.active) {
            clearInterval(interval);
            this.toast('All scans completed', 'success');
            this.loadLocations();
          }
        } catch (_) { clearInterval(interval); }
      }, 2000);
    } catch (e) {
      this.toast('Failed to start scan', 'error');
    }
  },

  async deleteLocation(id) {
    if (!confirm('Remove this location? Media items will remain in the database.')) return;
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/library/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.toast('Location removed', 'success');
      this.loadLocations();
    } catch (e) {
      console.error('Delete failed:', e);
      this.toast('Failed to remove location', 'error');
    }
  },

  renderSearch(container, params) {
    const initialQuery = params.q || '';
    container.innerHTML = `
      <div style="margin-bottom:24px;">
        <h2>Search</h2>
        <div class="search-box" style="margin-top:12px;max-width:600px;">
          <span class="search-icon">🔍</span>
          <input type="text" id="page-search-input" class="form-input" placeholder="Search media and people..." value="${this.escapeHtml(initialQuery)}" style="flex:1;background:var(--bg-tertiary);border:1px solid var(--border-color);color:var(--text-primary);padding:10px 16px;border-radius:20px;outline:none;">
        </div>
      </div>
      <div id="search-results-area"></div>
    `;

    const input = document.getElementById('page-search-input');
    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const q = input.value.trim();
          if (q.length >= 2) this.performSearch(q);
        }
        if (e.key === 'Escape') {
          input.value = '';
          document.getElementById('search-results-area').innerHTML = '';
        }
      });
      input.addEventListener('input', () => {
        clearTimeout(this.searchDebounce);
        const q = input.value.trim();
        this.searchDebounce = setTimeout(() => {
          if (q.length >= 2) this.performSearch(q);
        }, 400);
      });
      if (initialQuery) {
        setTimeout(() => this.performSearch(initialQuery), 100);
      }
    }
  },

  async performSearch(query) {
    const area = document.getElementById('search-results-area');
    if (!area) return;
    area.innerHTML = '<div class="empty-state"><p>Searching...</p></div>';

    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/search?q=${encodeURIComponent(query)}&limit=50`);
      const data = await res.json();

      const mediaItems = data.media || [];
      const peopleItems = data.people || [];

      if (mediaItems.length === 0 && peopleItems.length === 0) {
        area.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-title">No results for "${this.escapeHtml(query)}"</div><p>Try a different search term.</p></div>`;
        return;
      }

      let html = '';
      if (mediaItems.length > 0) {
        html += `<h3 style="margin-bottom:12px;">Media (${mediaItems.length})</h3>`;
        html += `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px;margin-bottom:24px;">`;
        html += mediaItems.map(item => this.mediaCard({
          id: item.id, title: item.title, year: item.year, media_type: item.media_type,
          favorite: false, artwork: []
        })).join('');
        html += '</div>';
      }

      if (peopleItems.length > 0) {
        html += `<h3 style="margin-bottom:12px;">People (${peopleItems.length})</h3>`;
        html += `<div style="display:flex;flex-direction:column;gap:8px;">`;
        html += peopleItems.map(p => `
          <div class="service-card" style="cursor:pointer;" onclick="App.toast('Person page coming soon', 'info')">
            <div class="service-info">
              <h3>${this.escapeHtml(p.name)}</h3>
            </div>
          </div>
        `).join('');
        html += '</div>';
      }

      area.innerHTML = html;
    } catch (e) {
      console.error('Search failed:', e);
      area.innerHTML = '<div class="empty-state"><p>Search failed. Is the backend running?</p></div>';
    }
  },

  hideSearchResults() {
    const results = document.getElementById('search-results');
    if (results) results.style.display = 'none';
  },

  async renderBrowser(container) {
    try {
      if (
        window.Views &&
        window.Views.browser &&
        typeof window.Views.browser.render === 'function'
      ) {
        await window.Views.browser.render(container, {});
        return;
      }

      if (
        window.BrowserHub &&
        typeof window.BrowserHub.render === 'function'
      ) {
        await window.BrowserHub.render(container, {});
        return;
      }

      console.error('[JMDB] BrowserHub is not available');
      container.innerHTML =
        '<div class="empty-state"><p>Browser module not loaded</p></div>';
    } catch (error) {
      console.error('[JMDB] Browser initialization failed:', error);
      container.innerHTML =
        '<div class="empty-state"><p>Browser failed to initialize</p></div>';
    }
  },

  renderPlayer(container) {
    container.innerHTML = `
      <div class="player-layout" style="display:flex;height:100%;gap:0;">
        <div style="flex:1;display:flex;flex-direction:column;background:#000;min-width:0;">
          <div id="player-video-area" style="flex:1;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;">
            <video id="player-video" style="width:100%;height:100%;object-fit:contain;display:none;" controlslist="nodownload noremoteplayback"></video>
            <div id="player-placeholder" style="text-align:center;color:var(--text-muted);">
              <div style="font-size:72px;margin-bottom:16px;">▶</div>
              <h2>Select a media item to play</h2>
              <p style="margin-top:8px;font-size:14px;">Click on any movie or TV show from the library</p>
            </div>
          </div>
          <div class="player-controls" id="player-controls">
            <div class="player-progress" id="player-progress-bar" style="cursor:pointer;padding:8px 16px 4px;">
              <div class="progress-track" style="width:100%;height:4px;background:rgba(255,255,255,0.2);border-radius:2px;position:relative;">
                <div id="progress-fill" style="height:100%;background:var(--accent);border-radius:2px;width:0%;position:absolute;top:0;left:0;"></div>
              </div>
            </div>
            <div class="player-buttons" style="display:flex;align-items:center;gap:12px;padding:8px 16px;">
              <button class="btn btn-secondary btn-sm" id="btn-play" onclick="Player.togglePlay()" title="Play/Pause">▶</button>
              <button class="btn btn-secondary btn-sm" id="btn-stop" onclick="Player.stop()" title="Stop">⏹</button>
              <div class="player-time" id="player-time" style="color:white;font-size:12px;min-width:120px;text-align:center;">--:-- / --:--</div>
              <div style="flex:1;"></div>
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="color:white;font-size:14px;">🔊</span>
                <input type="range" id="volume-slider" min="0" max="100" value="80" onchange="Player.setVolume(this.value)" style="width:80px;">
              </div>
              <button class="btn btn-secondary btn-sm" id="btn-fullscreen" onclick="Player.toggleFullscreen()" title="Fullscreen">⛶</button>
            </div>
            <div class="player-title-bar" style="padding:4px 16px;background:rgba(0,0,0,0.5);display:flex;justify-content:space-between;align-items:center;">
              <span id="player-title" style="color:white;font-size:14px;font-weight:500;">No media selected</span>
              <select id="player-backend-select" onchange="Player.setBackend(this.value)" style="background:var(--bg-tertiary);color:var(--text-primary);border:1px solid var(--border-color);border-radius:4px;padding:4px 8px;font-size:12px;">
                <option value="mpv">MPV</option>
                <option value="vlc">VLC</option>
                <option value="auto">Auto</option>
              </select>
            </div>
          </div>
        </div>
        <div class="player-sidebar" style="width:300px;background:var(--bg-secondary);border-left:1px solid var(--border-color);overflow-y:auto;padding:16px;">
          <h3 style="margin-bottom:16px;">Recently Played</h3>
          <div id="player-recent-list">
            <div class="empty-state" style="padding:20px;"><p style="font-size:12px;">No recent playback</p></div>
          </div>
        </div>
      </div>
    `;
    if (typeof Player !== 'undefined') {
      Player.init(container);
    }
  },

  async showMediaDetail(mediaId) {
    const container = document.getElementById('page-container');
    if (!container) return;

    const id = Number(mediaId);
    if (!Number.isFinite(id) || id <= 0) return;

    container.innerHTML = `
      <section class="media-detail-page">
        <div class="media-detail-loading">
          <div class="media-detail-loading-mark">J</div>
          <span>Loading title…</span>
        </div>
      </section>
    `;

    this.currentPage = 'detail';
    this.currentMediaId = id;

    try {
      const res = await fetch(
        `http://127.0.0.1:${this.port}/api/media/${id}`
      );

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const item = await res.json();
      this.renderMediaDetail(container, item);
    } catch (e) {
      console.error('Failed to load media detail:', e);

      container.innerHTML = `
        <section class="media-detail-page">
          <div class="media-detail-empty">
            <div class="media-detail-empty-icon">!</div>
            <h2>Unable to load title</h2>
            <p>JMDB could not retrieve this media item.</p>
            <button class="btn btn-secondary" onclick="App.nav('library', {type:'all'})">
              Back to Library
            </button>
          </div>
        </section>
      `;
    }
  },

  renderMediaDetail(container, item) {
    const escape = value => this.escapeHtml(value == null ? '' : String(value));

    const title = escape(item.title || 'Untitled');
    const originalTitle = escape(item.original_title || '');
    const description = escape(
      item.description || 'No description is available for this title.'
    );

    const poster =
      item.artwork?.find(a => a.is_primary && a.type === 'poster')?.url ||
      item.artwork?.find(a => a.is_primary)?.url ||
      item.artwork?.find(a => a.type === 'poster')?.url ||
      item.artwork?.[0]?.url ||
      '';

    const backdrop =
      item.artwork?.find(a => a.type === 'backdrop')?.url ||
      item.artwork?.find(a => a.type === 'fanart')?.url ||
      '';

    const typeLabel = escape(
      (item.media_type || 'media').replace('_', ' ')
    );

    const genres = Array.isArray(item.genres) ? item.genres : [];
    const people = Array.isArray(item.people) ? item.people : [];
    const externalIds = Array.isArray(item.external_ids)
      ? item.external_ids
      : [];

    const rating = item.rating != null
      ? Number(item.rating).toFixed(1)
      : '';

    const runtime = item.runtime
      ? `${Math.floor(Number(item.runtime) / 60)}h ${Number(item.runtime) % 60}m`
      : '';

    const progress = item.watch_progress;
    const progressPercent =
      progress && Number(progress.duration) > 0
        ? Math.min(
            100,
            Math.max(
              0,
              (Number(progress.position) / Number(progress.duration)) * 100
            )
          )
        : 0;

    const heroStyle = backdrop
      ? `style="--detail-backdrop:url('${this.escapeHtml(backdrop)}')"`
      : '';

    const posterHtml = poster
      ? `<img src="${this.escapeHtml(poster)}" alt="${title}" class="media-detail-poster">`
      : `<div class="media-detail-poster-fallback"><span>J</span></div>`;

    const meta = [
      item.year ? `<span>${escape(item.year)}</span>` : '',
      runtime ? `<span>${escape(runtime)}</span>` : '',
      `<span>${typeLabel}</span>`
    ].filter(Boolean).join('<span class="media-detail-dot">•</span>');

    const genreHtml = genres.length
      ? genres.map(g => `<span class="media-detail-chip">${escape(g)}</span>`).join('')
      : '<span class="media-detail-muted">No genres listed</span>';

    const peopleHtml = people.length
      ? people.slice(0, 8).map(p => `
          <span class="media-detail-person">
            ${escape(p.name)}
            ${p.role ? `<small>${escape(p.role)}</small>` : ''}
          </span>
        `).join('')
      : '<span class="media-detail-muted">No cast information</span>';

    const externalHtml = externalIds.length
      ? externalIds.map(e => `
          <span class="media-detail-external">
            ${escape(e.provider)} · ${escape(e.external_id)}
          </span>
        `).join('')
      : '';

    const progressHtml = progressPercent > 0
      ? `
        <div class="media-detail-progress">
          <div class="media-detail-progress-track">
            <span style="width:${progressPercent}%"></span>
          </div>
          <small>${Math.round(progressPercent)}% watched</small>
        </div>
      `
      : '';

    container.innerHTML = `
      <section class="media-detail-page" ${heroStyle}>
        <div class="media-detail-backdrop"></div>
        <div class="media-detail-vignette"></div>

        <div class="media-detail-content">
          <button
            class="media-detail-back"
            type="button"
            onclick="App.nav('library', {type:'all'})"
          >
            <span>←</span> Back to Library
          </button>

          <div class="media-detail-main">
            <div class="media-detail-poster-wrap">
              ${posterHtml}
              ${item.favorite ? `
                <div class="media-detail-favorite-badge">★ Favorite</div>
              ` : ''}
            </div>

            <div class="media-detail-info">
              <span class="media-detail-kicker">${typeLabel.toUpperCase()}</span>

              <h1 class="media-detail-title">${title}</h1>

              ${originalTitle && originalTitle !== title ? `
                <div class="media-detail-original">${originalTitle}</div>
              ` : ''}

              <div class="media-detail-meta">
                ${meta}
                ${rating ? `
                  <span class="media-detail-rating">
                    ★ ${escape(rating)}
                    ${item.votes ? `<small>${Number(item.votes).toLocaleString()} votes</small>` : ''}
                  </span>
                ` : ''}
              </div>

              <p class="media-detail-description">${description}</p>

              <div class="media-detail-actions">
                <button
                  class="btn btn-primary media-detail-play"
                  type="button"
                  onclick="App.loadPlayer(${Number(item.id)})"
                >
                  ▶ Play
                </button>

                <button
                  class="btn btn-secondary"
                  type="button"
                  onclick="App.toggleMediaFavorite(${Number(item.id)}, this)"
                >
                  ${item.favorite ? '★ Favorite' : '☆ Add Favorite'}
                </button>
              </div>

              ${progressHtml}

              <div class="media-detail-section">
                <div class="media-detail-section-label">GENRES</div>
                <div class="media-detail-chips">${genreHtml}</div>
              </div>

              <div class="media-detail-section">
                <div class="media-detail-section-label">CAST & PEOPLE</div>
                <div class="media-detail-people">${peopleHtml}</div>
              </div>

              ${externalHtml ? `
                <div class="media-detail-section">
                  <div class="media-detail-section-label">EXTERNAL IDs</div>
                  <div class="media-detail-external-list">${externalHtml}</div>
                </div>
              ` : ''}
            </div>
          </div>
        </div>
      </section>
    `;
  },

  async toggleMediaFavorite(mediaId, button) {
    try {
      const res = await fetch(
        `http://127.0.0.1:${this.port}/api/media/${Number(mediaId)}/favorite`,
        { method: 'POST' }
      );

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      button.textContent = data.favorite ? '★ Favorite' : '☆ Add Favorite';

      if (this.currentMediaId === Number(mediaId)) {
        this.toast(
          data.favorite ? 'Added to Favorites' : 'Removed from Favorites',
          'success'
        );
      }
    } catch (e) {
      console.error('Failed to toggle favorite:', e);
      this.toast('Could not update favorite', 'error');
    }
  },

  loadPlayer(mediaId) {
    this.nav('player');
    setTimeout(() => {
      if (typeof Player !== 'undefined' && Player.loadMedia) {
        Player.loadMedia(mediaId);
      }
    }, 200);
  },

  showMediaContext(e, mediaId) {
    e.preventDefault();
    const menu = document.getElementById('context-menu');
    if (!menu) return;

    menu.innerHTML = `
      <div class="context-menu-item" onclick="App.loadPlayer(${mediaId});App.hideContextMenu();">▶ Play</div>
      <div class="context-menu-item" onclick="App.showMediaDetail(${mediaId});App.hideContextMenu();">ℹ Details</div>
      <div class="context-sep"></div>
      <div class="context-menu-item" onclick="App.toast('Edit coming soon', 'info');App.hideContextMenu();">✏ Edit</div>
      <div class="context-menu-item" onclick="App.fetchMediaMetadata(${Number(mediaId)});App.hideContextMenu();">🏷 Fetch Metadata</div>
    `;

    menu.style.display = 'block';
    menu.style.left = e.clientX + 'px';
    menu.style.top = e.clientY + 'px';
    menu.style.visibility = 'visible';
    menu.setAttribute('aria-hidden', 'false');
  },

  async fetchMediaMetadata(mediaId) {
    const id = Number(mediaId);

    if (!Number.isFinite(id) || id <= 0) {
      this.toast("Invalid media ID", "error");
      return;
    }

    this.toast("Fetching metadata...", "info");

    try {
      const response = await fetch(
        `http://127.0.0.1:${this.port}/api/media/${id}/metadata`,
        { method: "POST" }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || `HTTP ${response.status}`
        );
      }

      this.toast(
        "Metadata updated successfully",
        "success"
      );

      if (this.currentMediaId === id) {
        await this.showMediaDetail(id);
      }

    } catch (error) {
      console.error(
        "Metadata fetch failed:",
        error
      );

      this.toast(
        error.message || "Could not fetch metadata",
        "error"
      );
    }
  },

  hideContextMenu() {
    const menu = document.getElementById('context-menu');
    if (menu) {
      menu.style.display = 'none';
      menu.style.visibility = 'hidden';
      menu.setAttribute('aria-hidden', 'true');
    }
  },

  renderServices(container) {
    container.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;">
        <h2>Services</h2>
        <button class="btn btn-sm btn-secondary" onclick="App.loadServices()">Refresh</button>
      </div>
      <div class="services-grid" id="services-grid">
        <div class="empty-state"><p>Loading services...</p></div>
      </div>
    `;
    this.loadServices();
  },

  async loadServices() {
    const grid = document.getElementById('services-grid');
    if (!grid) return;
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/services`);
      const data = await res.json();
      const services = data.services || [];

      if (services.length === 0) {
        grid.innerHTML = '<div class="empty-state"><p>No services configured</p></div>';
        return;
      }

      grid.innerHTML = services.map(s => {
        const statusColor = s.health_status === 'healthy' ? 'var(--success)' : s.health_status === 'unhealthy' ? 'var(--danger)' : 'var(--text-muted)';
        return `
          <div class="service-card">
            <div class="service-info">
              <h3>${this.escapeHtml(s.name)}</h3>
              <p style="color:${statusColor};font-size:12px;">● ${s.health_status || 'unknown'} ${s.enabled ? '• Enabled' : '• Disabled'}</p>
              ${s.category ? `<p style="font-size:11px;color:var(--text-muted);margin-top:4px;">${this.escapeHtml(s.category)}</p>` : ''}
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end;">
              <label class="toggle">
                <input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="App.toggleService(${s.id}, this.checked)">
                <span class="toggle-slider"></span>
              </label>
              <button class="btn btn-sm btn-secondary" onclick="App.testService(${s.id})">Test</button>
            </div>
          </div>
        `;
      }).join('');
    } catch (e) {
      console.error('Failed to load services:', e);
      grid.innerHTML = '<div class="empty-state"><p>Failed to load services</p></div>';
    }
  },

  async testService(id) {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/services/${id}/test`, { method: 'POST' });
      const data = await res.json();
      if (data.healthy) {
        this.toast('Service is healthy', 'success');
      } else {
        this.toast('Service test failed', 'error');
      }
      this.loadServices();
    } catch (e) {
      this.toast('Test failed', 'error');
    }
  },

  async toggleService(id, enabled) {
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/services/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      this.toast(`Service ${enabled ? 'enabled' : 'disabled'}`, 'success');
    } catch (e) {
      console.error(e);
      this.toast('Failed to update service', 'error');
    }
  },

  renderGenericSettings(container) {
    container.innerHTML = `
      <h2 style="margin-bottom:24px;">Settings</h2>
      <div class="settings-section">
        <div class="settings-section-title">General</div>
        <div class="setting-row">
          <div>
            <div class="setting-label">Theme</div>
            <div class="setting-desc">Switch between dark and light mode</div>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="App.toggleTheme()">Toggle Theme</button>
        </div>
      </div>
    `;
  },

  renderStatistics(container) {
    container.innerHTML = `
      <h2 style="margin-bottom:24px;">Statistics</h2>
      <div class="stats-grid" id="stats-grid">
        <div class="stat-card"><div class="stat-value" id="stat-total">-</div><div class="stat-label">Total Media</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-movies">-</div><div class="stat-label">Movies</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-tv">-</div><div class="stat-label">TV Shows</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-favs">-</div><div class="stat-label">Favorites</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-locations">-</div><div class="stat-label">Locations</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-played">-</div><div class="stat-label">Played</div></div>
      </div>
    `;
    this.loadStatistics();
  },

  async loadStatistics() {
    try {
      const [mediaRes, libRes] = await Promise.all([
        fetch(`http://127.0.0.1:${this.port}/api/media?limit=1`),
        fetch(`http://127.0.0.1:${this.port}/api/library`)
      ]);
      const media = await mediaRes.json();
      const libs = await libRes.json();

      const total = media.total || 0;
      const movies = media.items?.filter(i => i.media_type === 'movie').length || 0;
      const tvShows = media.items?.filter(i => i.media_type === 'tv_show').length || 0;
      const favs = media.items?.filter(i => i.favorite).length || 0;

      const el = (id) => document.getElementById(id);
      if (el('stat-total')) el('stat-total').textContent = total;
      if (el('stat-movies')) el('stat-movies').textContent = movies;
      if (el('stat-tv')) el('stat-tv').textContent = tvShows;
      if (el('stat-favs')) el('stat-favs').textContent = favs;
      if (el('stat-locations')) el('stat-locations').textContent = libs.libraries?.length || 0;
      if (el('stat-played')) el('stat-played').textContent = '0';
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  },

  renderActivity(container) {
    container.innerHTML = `
      <h2 style="margin-bottom:24px;">Activity</h2>
      <div class="empty-state">
        <div class="empty-state-icon">📋</div>
        <div class="empty-state-title">No activity yet</div>
        <p>Activity will appear here as you use JMDB.</p>
      </div>
    `;
  },

  renderHelp(container) {
    container.innerHTML = `
      <h2 style="margin-bottom:24px;">Help</h2>
      <div class="settings-section">
        <h3 style="margin-bottom:12px;">Getting Started</h3>
        <ol style="padding-left:20px;line-height:2;">
          <li>Go to <strong>Locations</strong> and add your media folders</li>
          <li>Click <strong>Scan</strong> to index your media files</li>
          <li>Browse your library under <strong>Library → All Media</strong></li>
          <li>Use <strong>Search</strong> to find specific titles</li>
          <li>Click any media card to <strong>play</strong> it</li>
        </ol>
      </div>
      <div class="settings-section" style="margin-top:16px;">
        <h3 style="margin-bottom:12px;">Keyboard Shortcuts</h3>
        <div class="setting-row"><div><div class="setting-label">/</div><div class="setting-desc">Focus search bar</div></div></div>
        <div class="setting-row"><div><div class="setting-label">Enter</div><div class="setting-desc">Submit search</div></div></div>
        <div class="setting-row"><div><div class="setting-label">Escape</div><div class="setting-desc">Close modals/dropdowns</div></div></div>
      </div>
    `;
  },

  renderAbout(container) {
    container.innerHTML = `
      <div style="text-align:center;padding:60px 20px;">
        <div style="width:80px;height:80px;background:linear-gradient(135deg,var(--accent),var(--accent-hover));border-radius:var(--radius-lg);display:flex;align-items:center;justify-content:center;font-size:40px;font-weight:bold;color:#000;margin:0 auto 24px;">J</div>
        <h1 style="margin-bottom:8px;">JMDB</h1>
        <p style="color:var(--text-muted);margin-bottom:4px;">Johnny's Media Database</p>
        <p style="color:var(--text-muted);margin-bottom:32px;">Version 1.0.0</p>
        <p style="max-width:500px;margin:0 auto;line-height:1.6;">A personal media library manager built with FastAPI, SQLAlchemy, and Electron. Scan your media folders, fetch metadata, and enjoy your collection.</p>
      </div>
    `;
  },

  renderDiagnostics(container) {
    container.innerHTML = `
      <h2 style="margin-bottom:24px;">Diagnostics</h2>
      <div id="diag-content">
        <div class="settings-section">
          <div class="settings-section-title">System Information</div>
          <div id="diag-loading"><p>Checking...</p></div>
        </div>
      </div>
    `;
    this.loadDiagnostics();
  },

  async loadDiagnostics() {
    const area = document.getElementById('diag-loading');
    if (!area) return;
    try {
      const [sysRes, dbRes, srvRes] = await Promise.all([
        fetch(`http://127.0.0.1:${this.port}/api/system/info`),
        fetch(`http://127.0.0.1:${this.port}/api/system/diagnostics`),
        fetch(`http://127.0.0.1:${this.port}/api/health`)
      ]);
      const sys = await sysRes.json();
      const diag = await dbRes.json();
      const health = await srvRes.json();

      area.innerHTML = `
        <div class="setting-row"><div><div class="setting-label">Application</div></div><span>${sys.application || 'JMDB'} v${sys.version || '1.0.0'}</span></div>
        <div class="setting-row"><div><div class="setting-label">Backend Status</div></div><span style="color:var(--success);">● ${health.status || 'healthy'}</span></div>
        <div class="setting-row"><div><div class="setting-label">Python</div></div><span>${sys.python || '-'}</span></div>
        <div class="setting-row"><div><div class="setting-label">Platform</div></div><span>${sys.platform || '-'}</span></div>
        <div class="setting-row"><div><div class="setting-label">Database Path</div></div><span style="font-size:12px;word-break:break-all;">${diag.db_path || '-'}</span></div>
        <div class="setting-row"><div><div class="setting-label">Database Exists</div></div><span>${diag.db_exists ? 'Yes' : 'No'}</span></div>
        <div class="setting-row"><div><div class="setting-label">Database Size</div></div><span>${diag.db_size ? (diag.db_size / 1024).toFixed(1) + ' KB' : '-'}</span></div>
      `;
    } catch (e) {
      area.innerHTML = `<p style="color:var(--danger);">Failed to load diagnostics: ${e.message}</p>`;
    }
  },

  renderScanHistory(container) {
    container.innerHTML = `
      <h2 style="margin-bottom:24px;">Scan History</h2>
      <div class="empty-state">
        <div class="empty-state-icon">📜</div>
        <div class="empty-state-title">No scan history</div>
        <p>Scan results will appear here after you scan a location.</p>
      </div>
    `;
  },

  renderScanProblems(container) {
    container.innerHTML = `
      <h2 style="margin-bottom:24px;">Scan Problems</h2>
      <div class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-title">No problems detected</div>
        <p>All scans have completed without errors.</p>
      </div>
    `;
  },

  toggleTheme() {
    const isDark = document.body.classList.contains('theme-dark');
    document.body.classList.remove('theme-dark', 'theme-light');
    document.body.classList.add(isDark ? 'theme-light' : 'theme-dark');
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = isDark ? '☀️' : '🌙';
  },

  toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'i';
    toast.innerHTML = `<span>${icon}</span><span>${this.escapeHtml(msg)}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  },

  escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};

window.App = App;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => App.init());
} else {
  App.init();
}
