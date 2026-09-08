/**
 * JMDB — Services Page
 */
// Recognizable brand marks drawn as inline SVG (brand color + signature glyph).
const SERVICE_ICONS = {
  youtube: { bg: '#ff0000', icon: '<svg viewBox="0 0 24 24" width="26" height="26" fill="white"><path d="M23 12s0-3.8-.5-5.6c-.3-1-1.1-1.8-2.1-2C18.6 4 12 4 12 4s-6.6 0-8.4.4c-1 .2-1.8 1-2.1 2C1 8.2 1 12 1 12s0 3.8.5 5.6c.3 1 1.1 1.8 2.1 2 1.8.4 8.4.4 8.4.4s6.6 0 8.4-.4c-1 0 0 0 0 0 1-.2 1.8-1 2.1-2 .5-1.8.5-5.6.5-5.6z" fill="#ff0000"/><path d="M9.8 15.5V8.5l6 3.5z" fill="white"/></svg>' },
  telegram: { bg: '#2aabee', icon: '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M21.9 4.6c.3-1.3-.9-2.2-2-1.7L2.7 9.6c-1.3.5-1.2 2.4.1 2.8l4.4 1.4 1.7 5.2c.4 1.2 1.9 1.5 2.7.6l2.4-2.4 4.5 3.3c1 .7 2.4.2 2.7-1z" fill="white"/><path d="M9.1 13.4l8.6-7.8c.4-.3.8.2.5.5l-7 6.8-.3 3z" fill="#2aabee"/></svg>' },
  spotify: { bg: '#1db954', icon: '<svg viewBox="0 0 24 24" width="26" height="26"><circle cx="12" cy="12" r="11" fill="#1db954"/><path d="M7 9.5c3.6-1 7.6-.7 10.6 1M7.4 12.6c3-.8 6.4-.5 9 .9M7.8 15.5c2.4-.6 5-.4 7.2.8" stroke="white" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>' },
  tvtime: { bg: '#f5a623', icon: '<svg viewBox="0 0 24 24" width="26" height="26"><rect x="2" y="6" width="20" height="14" rx="2.5" fill="white"/><path d="M8 2l4 4 4-4" stroke="white" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M8 13l2.6 2.6L16 10" stroke="#f5a623" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' },
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
