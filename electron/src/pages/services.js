/**
 * JMDB — Services Page
 */
const SERVICE_ICONS = {
  youtube: { bg: '#ff0000', icon: '▶' },
  telegram: { bg: '#2aabee', icon: '✈' },
  spotify: { bg: '#1db954', icon: '♪' },
  tvtime: { bg: '#f5a623', icon: '📺' },
};

async function renderServices() {
  const body = document.getElementById('contentBody');
  body.innerHTML = '<div class="content-loading"><div class="spinner"></div></div>';

  try {
    const data = await API.get('/api/services');
    const services = data.services || [];

    let html = `<div class="section-header"><span class="section-title">Services</span><span class="section-sub">Open external services in the JMDB Browser</span></div>`;
    html += '<div class="services-grid">';

    for (const svc of services) {
      const ic = SERVICE_ICONS[svc.key] || { bg: '#5c6478', icon: '🔗' };
      html += `
        <div class="service-card">
          <div class="service-icon" style="background:${ic.bg}">${ic.icon}</div>
          <div>
            <div class="service-name">${esc(svc.name)}</div>
            <div class="service-desc">${esc(svc.note)}</div>
          </div>
          <div class="service-actions">
            <button class="btn btn-sm btn-accent" onclick="openService('${esc(svc.url)}','${esc(svc.name)}')">Open in JMDB</button>
            <button class="btn btn-sm" onclick="jmdb.openExternal('${esc(svc.url)}')">↗ External</button>
          </div>
        </div>`;
    }

    html += '</div>';
    body.innerHTML = html;
    body.classList.remove('hidden');
    document.getElementById('contentLoading').classList.add('hidden');
  } catch (e) {
    body.innerHTML = `<div class="content-error"><p>${esc(e.message)}</p></div>`;
  }
}

function openService(url, name) {
  AppState.navigate('browser', { url, title: name });
}
