/**
 * JMDB — Library Pages (Movies, TV, Music)
 */
async function renderLibraryKind(kind, title, icon) {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';

  try {
    const data = await API.get(`/api/library/${kind}`);
    const items = data.items || [];

    let html = `
      <div class="section-header">
        <span class="section-title">${title}</span>
        <span class="section-sub">${items.length} titles</span>
        <div style="margin-left:auto;display:flex;gap:8px;align-items:center;">
          <label style="font-size:12px;color:var(--text-muted);">Sort:</label>
          <select class="settings-select" id="libSort" onchange="renderLibraryKind('${kind}','${title}','${icon}')">
            <option value="rating">Top Rated</option>
            <option value="title">Title A-Z</option>
            <option value="newest">Newest</option>
            <option value="added">Recently Added</option>
          </select>
        </div>
      </div>`;
    body.innerHTML = html;

    const sortSel = document.getElementById('libSort');
    if (sortSel) {
      sortSel.addEventListener('change', async () => {
        const sorted = await API.get(`/api/library/${kind}?sort=${sortSel.value}`);
        const grid = body.querySelector('.cards-grid-holder') || (() => { const g = document.createElement('div'); body.appendChild(g); return g; })();
        renderCardsGrid(grid, sorted.items || []);
      });
    }

    const grid = document.createElement('div');
    grid.className = 'cards-grid-holder';
    body.appendChild(grid);
    renderCardsGrid(grid, items);

    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><div class="error-icon">⚠</div><h3>Failed to load ${title}</h3><p>${esc(e.message)}</p><button onclick="renderLibraryKind('${kind}','${title}','${icon}')">Retry</button></div>`;
  }
}

async function renderMovies() { await renderLibraryKind('movie', 'Movies', '🎬'); }
async function renderTV() { await renderLibraryKind('show', 'TV Shows', '📺'); }
async function renderMusic() { await renderLibraryKind('music', 'Music', '🎵'); }
