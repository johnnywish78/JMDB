/**
 * JMDB renderer acceptance harness.
 *
 * Boots the REAL FastAPI backend (uvicorn) and loads the REAL renderer
 * (electron/src/index.html) inside jsdom with a `window.jmdb` bridge whose
 * api.* methods call the real backend over HTTP. It then navigates every page
 * and asserts the content area renders without errors. This exercises the real
 * renderer code + real DOM + real backend; only the Electron shell/transport is
 * substituted (unavailable headless).
 *
 * Usage: NODE_PATH=<dir-with-jsdom> node scripts/renderer_acceptance.js
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const ROOT = path.join(__dirname, '..');
const PORT = process.env.JMDB_PORT || '18933';
const API = `http://127.0.0.1:${PORT}`;
const { JSDOM } = require('jsdom');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function waitForBackend() {
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`${API}/api/health`);
      if (r.ok) return;
    } catch {}
    await sleep(200);
  }
  throw new Error('backend did not start');
}

async function seed() {
  const lib = fs.mkdtempSync(path.join(os.tmpdir(), 'jmdb-lib-'));
  fs.mkdirSync(path.join(lib, 'movies'), { recursive: true });
  fs.mkdirSync(path.join(lib, 'tv', 'My Show', 'Season 1'), { recursive: true });
  fs.writeFileSync(path.join(lib, 'movies', 'The Matrix (1999).mp4'), 'x');
  fs.writeFileSync(path.join(lib, 'movies', 'Inception 2010.mkv'), 'x');
  fs.writeFileSync(path.join(lib, 'tv', 'My Show', 'Season 1', 'My Show S01E01.mkv'), 'x');
  await fetch(`${API}/api/scan`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ folders: [lib], enrich: false }) });
  for (let i = 0; i < 100; i++) {
    const st = await (await fetch(`${API}/api/scan/status`)).json();
    if (!st.running) return;
    await sleep(100);
  }
}

function makeBridge(window) {
  const req = async (method, endpoint, body) => {
    try {
      const opts = { method };
      if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {
        opts.headers = { 'content-type': 'application/json' };
        opts.body = JSON.stringify(body);
      }
      const r = await fetch(API + endpoint, opts);
      const ct = r.headers.get('content-type') || '';
      const data = ct.includes('json') ? await r.json().catch(() => null) : null;
      return { ok: r.ok, status: r.status, data };
    } catch (e) { return { ok: false, error: e.message }; }
  };
  window.jmdb = {
    minimize: () => {}, maximize: () => {}, close: () => {},
    openExternal: (url) => { window.__openedExternal = url; },
    openFile: async () => ({ canceled: true, filePaths: [] }),
    openDirectory: async () => ({ canceled: true, filePaths: [] }),
    startBackend: async () => ({ ok: true }),
    stopBackend: async () => ({ ok: true }),
    api: {
      get: (e) => req('GET', e),
      post: (e, b) => req('POST', e, b),
      patch: (e, b) => req('PATCH', e, b),
      put: (e, b) => req('PUT', e, b),
      delete: (e) => req('DELETE', e),
    },
    navigate: () => {},
    playMedia: (p) => { window.__playPayload = p; },
    onPlay: () => {},
    playbackStart: (p) => req('POST', '/api/playback/start', p),
    playbackProgress: (a, b) => req('POST', '/api/playback/progress', { position_s: a, duration_s: b }),
    playbackStop: (a, b) => req('POST', '/api/playback/stop', { position_s: a, duration_s: b }),
    playbackFinish: () => req('POST', '/api/playback/finish', {}),
    playbackGetProgress: (k) => req('GET', `/api/playback/${k}`),
  };
}

async function main() {
  const backend = spawn(path.join(ROOT, '.venv', 'bin', 'python'),
    ['-m', 'uvicorn', 'app.api.server:app', '--host', '127.0.0.1', '--port', PORT, '--log-level', 'warning'],
    { cwd: ROOT, stdio: 'ignore' });

  const errors = [];
  try {
    await waitForBackend();
    await seed();

    const htmlPath = path.join(ROOT, 'electron', 'src', 'index.html');
    const html = fs.readFileSync(htmlPath, 'utf8');
    const dom = new JSDOM(html, {
      url: `file://${htmlPath}`,
      runScripts: 'dangerously',
      resources: 'usable',
      pretendToBeVisual: true,
      beforeParse: (window) => {
        makeBridge(window);
        // <webview> is an Electron-provided element; stub its API surface headless.
        const origCreate = window.document.createElement.bind(window.document);
        window.document.createElement = (tag, ...rest) => {
          const el = origCreate(tag, ...rest);
          if (String(tag).toLowerCase() === 'webview') {
            el.loadURL = (u) => { el.__url = u; };
            el.canGoBack = () => false; el.canGoForward = () => false;
            el.goBack = () => {}; el.goForward = () => {}; el.reload = () => {};
            el.getTitle = () => 'stub';
          }
          return el;
        };
        window.addEventListener('error', (e) => errors.push('window: ' + e.message));
      },
    });
    const { window } = dom;
    // give startup + home render time
    await sleep(1500);

    const pages = ['home', 'movies', 'tv', 'music', 'library', 'people', 'favorites', 'watchlist', 'history', 'search', 'recommendations', 'statistics', 'services', 'browser', 'settings'];
    const results = [];
    for (const page of pages) {
      await window.eval(`AppState.navigate(${JSON.stringify(page)})`);
      await sleep(400);
      const body = window.document.getElementById('contentBody');
      const text = body ? body.textContent.trim() : '';
      const htmlLen = body ? body.innerHTML.length : 0;
      const bad = /Page not found|Failed to load/i.test(text);
      results.push({ page, ok: htmlLen > 0 && !bad, len: htmlLen, text: text.slice(0, 200) });
    }

    let pass = true;
    for (const r of results) {
      console.log(`${r.ok ? 'PASS' : 'FAIL'} ${r.page} (html ${r.len})`);
      if (!r.ok) { pass = false; console.log('   text:', JSON.stringify(r.text)); }
    }
    if (errors.length) {
      console.log('WINDOW ERRORS:'); errors.forEach(e => console.log('  ' + e));
      pass = false;
    }
    console.log(pass ? 'RENDERER ACCEPTANCE: PASS' : 'RENDERER ACCEPTANCE: FAIL');
    process.exitCode = pass ? 0 : 1;
  } finally {
    backend.kill('SIGTERM');
  }
}

main().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
