/**
 * JMDB — Library Pages (Movies, TV, Music)
 */
async function renderLibrary(kind, title, icon) {
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
          <select class="settings-select" id="libSort" onchange="renderLibrary('${kind}','${title}',${icon})">
            <option value="rating" ${data.sort==='rating'?'selected':''}>Top Rated</option>
            <option value="title" ${data.sort==='title'?'selected':''}>Title A-Z</option>
            <option value="newest" ${data.sort==='newest'?'selected':''}>Newest</option>
            <option value="added" ${data.sort==='added'?'selected':''}>Recently Added</option>
          </select>
        </div>
      </div>`;
    body.innerHTML = html;

    const grid = document.createElement('div');
    body.appendChild(grid);
    renderCardsGrid(grid, items);

    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><div class="error-icon">⚠</div><h3>Failed to load ${title}</h3><p>${esc(e.message)}</p><button onclick="renderLibrary('${kind}','${title}',${icon})">Retry</button></div>`;
  }
}

async function renderMovies() { await renderLibrary('movie', 'Movies', '🎬'); }
async function renderTV() { await renderLibrary('show', 'TV Shows', '📺'); }
async function renderMusic() { await renderLibrary('music', 'Music', '🎵'); }
