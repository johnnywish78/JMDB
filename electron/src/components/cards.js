/**
 * JMDB — Card Components
 */

function createMediaCard(item, opts = {}) {
  const card = document.createElement('div');
  card.className = 'media-card';
  card.dataset.id = item.id;
  card.dataset.kind = item.kind;

  const posterUrl = item.poster_path || item.poster_url;
  let posterHtml;
  if (posterUrl) {
    if (posterUrl.startsWith('http')) {
      const url = posterUrl.replace('/w500/', '/w342/').replace('/w780/', '/w342/');
      posterHtml = `<img src="${url}" alt="${esc(item.title)}" loading="lazy" onerror="this.parentElement.innerHTML=getPlaceholder('${esc(item.title)}','${item.year || ''}')">`;
    } else if (posterUrl.startsWith('file://')) {
      posterHtml = `<img src="${posterUrl}" alt="${esc(item.title)}" loading="lazy">`;
    } else {
      posterHtml = getPlaceholder(item.title, item.year);
    }
  } else {
    posterHtml = getPlaceholder(item.title, item.year);
  }

  const progress = opts.progress || 0;
  const progressHtml = progress > 0 ? `<div class="card-progress"><div class="card-progress-bar" style="width:${progress}%"></div></div>` : '';

  const ratingHtml = (item.rating && item.rating > 0)
    ? `<span class="card-rating">★ ${Number(item.rating).toFixed(1)}</span>`
    : '<span class="card-rating" style="opacity:0.3">—</span>';

  card.innerHTML = `
    <div class="card-poster">${posterHtml}${progressHtml}<span class="card-badge">${item.kind === 'show' ? 'TV' : item.kind === 'music' ? '♪' : 'Film'}</span></div>
    <div class="card-meta">
      <div class="card-title" title="${esc(item.title)}">${esc(truncate(item.title, 22))}</div>
      <div class="card-meta-row">
        <span class="card-year">${item.year || '?'}</span>
        ${ratingHtml}
      </div>
    </div>`;

  card.addEventListener('click', () => {
    if (opts.onPlay && item.file_path) {
      opts.onPlay(item);
    } else {
      AppState.navigate('detail', { media_id: item.id });
    }
  });
  return card;
}

function getPlaceholder(title, year) {
  const letter = (title.replace(/^(the|a|an)\s+/i, '').charAt(0) || '?').toUpperCase();
  const hue = (title.charCodeAt(0) * 37) % 360;
  return `<div class="placeholder" style="background:linear-gradient(135deg,hsl(${hue},40%,15%),hsl(${(hue+40)%360},40%,25%))">${letter}</div>`;
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function truncate(s, n) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

function renderCardsGrid(container, items, opts = {}) {
  container.innerHTML = '';
  if (!items || items.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">🎬</div><div class="empty-title">Nothing here yet</div><div class="empty-msg">Add library folders in Settings and run a scan.</div></div>`;
    return;
  }
  const grid = document.createElement('div');
  grid.className = 'cards-grid';
  for (const item of items) {
    grid.appendChild(createMediaCard(item, opts));
  }
  container.appendChild(grid);
}
