/**
 * JMDB — Search Page
 */
let _searchTimeout = null;

async function renderSearch() {
  const body = document.getElementById('contentBody');
  body.innerHTML = `
    <div class="section-header"><span class="section-title">Search</span></div>
    <div style="margin-bottom:16px;">
      <input type="text" class="form-input" id="searchInput" placeholder="Search movies, TV shows, music…" style="max-width:500px;" autocomplete="off">
    </div>
    <div id="searchResults"></div>`;
  body.classList.remove('hidden');
  document.getElementById('contentLoading').classList.add('hidden');

  const input = document.getElementById('searchInput');
  input.focus();

  input.addEventListener('input', () => {
    clearTimeout(_searchTimeout);
    _searchTimeout = setTimeout(() => doSearch(input.value), 300);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { clearTimeout(_searchTimeout); doSearch(input.value); }
  });
}

async function doSearch(q) {
  const resultsEl = document.getElementById('searchResults');
  if (!q || q.trim().length < 2) {
    resultsEl.innerHTML = '<div class="empty-state"><div class="empty-msg">Type at least 2 characters to search.</div></div>';
    return;
  }
  resultsEl.innerHTML = '<div class="content-loading" style="padding:20px;"><div class="spinner"></div></div>';
  try {
    const data = await API.get(`/api/search?q=${encodeURIComponent(q)}&limit=50`);
    const results = data.results || [];
    if (results.length === 0) {
      resultsEl.innerHTML = `<div class="empty-state"><div class="empty-icon">🔍</div><div class="empty-title">No results for "${esc(q)}"</div></div>`;
      return;
    }
    const grid = document.createElement('div');
    grid.className = 'cards-grid';
    for (const item of results) {
      grid.appendChild(createMediaCard(item, {
        onPlay: (it) => {
          if (it.file_path) AppState.playMedia(it);
          else AppState.navigate('detail', { media_id: it.id });
        }
      }));
    }
    resultsEl.innerHTML = '';
    resultsEl.appendChild(grid);
  } catch (e) {
    resultsEl.innerHTML = `<div class="content-error"><p>${esc(e.message)}</p></div>`;
  }
}
