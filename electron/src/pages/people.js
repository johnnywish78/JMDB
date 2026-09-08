/**
 * JMDB — People Page
 */
async function renderPeople() {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';

  try {
    const data = await API.get('/api/people');
    const people = data.people || [];

    if (people.length === 0) {
      body.innerHTML = '<div class="empty-state"><div class="empty-icon">👤</div><div class="empty-title">No people indexed</div><div class="empty-msg">Enrich titles with metadata to build the cast index.</div></div>';
    } else {
      let html = `<div class="section-header"><span class="section-title">People</span><span class="section-sub">${people.length} indexed</span></div>`;
      html += `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;">`;
      for (const p of people) {
        html += `
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;cursor:pointer;text-align:center;transition:all 0.15s;"
               onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'"
               onclick="renderPerson('${esc(p.name)}')">
            <div style="font-size:24px;margin-bottom:6px;">👤</div>
            <div style="font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(p.name)}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${p.n} titles</div>
          </div>`;
      }
      html += '</div>';
      body.innerHTML = html;
    }
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><p>${esc(e.message)}</p></div>`;
  }
}

async function renderPerson(name) {
  const body = document.getElementById('contentBody');
  try {
    const data = await API.get(`/api/people/${encodeURIComponent(name)}`);
    const items = data.items || [];
    let html = `
      <div class="section-header">
        <button class="btn btn-sm" onclick="AppState.navigate('people')">← Back</button>
        <span class="section-title">${esc(name)}</span>
        <span class="section-sub">${items.length} titles</span>
      </div>`;
    if (items.length > 0) {
      const grid = document.createElement('div');
      grid.className = 'cards-grid';
      for (const item of items) {
        grid.appendChild(createMediaCard(item));
      }
      body.innerHTML = html;
      body.classList.remove('hidden');
      document.getElementById('contentLoading').classList.add('hidden');
      document.getElementById('contentBody').appendChild(grid);
    } else {
      body.innerHTML = html + '<div class="empty-state"><div class="empty-msg">No titles found for this person.</div></div>';
    }
  } catch (e) {
    AppState.toast(e.message, 'error');
    AppState.navigate('people');
  }
}
