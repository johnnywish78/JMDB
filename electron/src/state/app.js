/**
 * JMDB — Application State
 */
const AppState = {
  currentPage: 'home',
  theme: 'dark',
  settings: {},
  libraryCounts: { movies: 0, shows: 0, music: 0 },
  currentMediaId: null,
  currentEpisodeId: null,

  async init() {
    try {
      this.settings = await API.get('/api/settings');
      this.theme = this.settings.theme || 'dark';
      await this.updateCounts();
    } catch (e) {
      console.error('Failed to init state:', e);
      document.getElementById('contentLoading').classList.add('hidden');
      document.getElementById('contentError').classList.remove('hidden');
    }
  },

  async updateCounts() {
    try {
      const info = await API.get('/api/app/info');
      this.libraryCounts = {
        movies: info.movies || 0,
        shows: info.shows || 0,
        music: info.music || 0,
      };
      this._updateFooter();
    } catch {}
  },

  _updateFooter() {
    const el = document.getElementById('footerStats');
    if (el) {
      el.textContent = `${this.libraryCounts.movies} films · ${this.libraryCounts.shows} series`;
    }
  },

  setTheme(theme) {
    this.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    API.patch('/api/settings', { theme }).catch(() => {});
  },

  navigate(page, params = {}) {
    this.currentPage = page;
    this.currentMediaId = params.media_id || null;
    this.currentEpisodeId = params.episode_id || null;
    this._updateNav();
    renderPage(page, params);
  },

  _updateNav() {
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.page === this.currentPage);
    });
  },

  playMedia(item) {
    const payload = {
      media_key: `m:${item.id}`,
      title: item.title,
      subtitle: `${item.year || ''} · ${item.runtime_min || 0} min`,
      file_path: item.file_path,
      duration_s: (item.runtime_min || 0) * 60,
      media_id: item.id,
    };
    jmdb.playMedia(payload);
  },

  toast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  },
};
