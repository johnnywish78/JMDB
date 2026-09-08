/**
 * JMDB Electron — Main Process
 */
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

// In Electron, require('electron') returns the API object automatically
// This works because Electron injects the module before loading the app
let electronAPI;
try {
  electronAPI = require('electron');
} catch (err) {
  console.error('Failed to require electron:', err.message);
  process.exit(1);
}

// Verify we got the API, not a path string
if (typeof electronAPI === 'string') {
  console.error('ERROR: require("electron") returned a path string, not the API object');
  console.error('This indicates a module resolution issue.');
  process.exit(1);
}

const { app, BrowserWindow, ipcMain, shell, dialog } = electronAPI;

let mainWindow = null;
let backendProcess = null;
let apiUrl = 'http://127.0.0.1:18932';
let apiToken = '';

function findPython() {
  const fs = require('fs');
  const candidates = [
    path.join(app.getAppPath(), '..', '.venv', 'bin', 'python'),
    path.join(app.getAppPath(), '.venv', 'bin', 'python'),
    path.join(app.getAppPath(), '..', '.venv', 'bin', 'python3'),
    path.join(app.getAppPath(), '.venv', 'bin', 'python3'),
  ];
  for (const c of candidates) {
    try { if (fs.existsSync(c)) return c; } catch {}
  }
  for (const name of ['python3', 'python']) {
    try {
      const { execSync } = require('child_process');
      const out = execSync(`command -v ${name}`, { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
      if (out) return out;
    } catch {}
  }
  return null;
}

function repoRoot() {
  const fs = require('fs');
  const up = path.join(app.getAppPath(), '..');
  if (fs.existsSync(path.join(up, 'run.py'))) return up;
  if (fs.existsSync(path.join(app.getAppPath(), 'run.py'))) return app.getAppPath();
  return up;
}

function startBackend() {
  return new Promise((resolve, reject) => {
    const py = findPython();
    if (!py) { reject(new Error('No Python interpreter found for backend')); return; }
    const venvPython = py;
    const args = [
      '-m', 'uvicorn', 'app.api.server:app',
      '--host', '127.0.0.1',
      '--port', '18932',
      '--log-level', 'warning'
    ];
    backendProcess = spawn(venvPython, args, { cwd: repoRoot(), stdio: 'pipe' });

    backendProcess.stdout.on('data', (data) => {
      const line = data.toString();
      const m = line.match(/token:\s*(\w+)/);
      if (m) { apiToken = m[1]; }
    });
    backendProcess.stderr.on('data', (data) => {
      const line = data.toString().trim();
      if (line) console.error('[backend]', line);
    });

    const startTime = Date.now();
    const checkReady = () => {
      http.get(apiUrl + '/api/health', (res) => {
        if (res.statusCode === 200) resolve({});
        else setTimeout(checkReady, 500);
      }).on('error', () => {
        if (Date.now() - startTime > 20000) reject(new Error('Backend timeout'));
        else setTimeout(checkReady, 500);
      });
    };
    checkReady();
  });
}

function stopBackend() {
  if (backendProcess) { backendProcess.kill('SIGTERM'); backendProcess = null; }
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 900, minHeight: 600,
    frame: false, backgroundColor: '#0b0d12',
    webPreferences: {
      preload: path.join(app.getAppPath(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webviewTag: true
    }
  });
  mainWindow.setMenuBarVisibility(false);
  mainWindow.loadFile(path.join(app.getAppPath(), 'src', 'index.html'));
  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── IPC Handlers ─────────────────────────────────────────────────────────────

ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window:close', () => mainWindow?.close());
ipcMain.handle('shell:openExternal', (_e, url) => shell.openExternal(url));
ipcMain.handle('dialog:openFile', async (_e, opts) => {
  const result = await dialog.showOpenDialog(mainWindow, opts);
  return result;
});
ipcMain.handle('dialog:openDirectory', async (_e, opts) => {
  const result = await dialog.showOpenDialog(mainWindow, { ...opts, properties: ['openDirectory'] });
  return result;
});
ipcMain.handle('backend:start', async () => {
  try { await startBackend(); return { ok: true }; }
  catch (err) { return { ok: false, error: err.message }; }
});
ipcMain.handle('backend:stop', () => { stopBackend(); return { ok: true }; });
ipcMain.handle('api:request', async (_e, method, endpoint, body) => {
  try {
    const url = new URL(endpoint, apiUrl);
    const headers = { 'X-JMDB-Token': apiToken };
    const options = { method, headers };
    if (body !== undefined && body !== null && ['POST', 'PUT', 'PATCH'].includes(method)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    options.signal = controller.signal;
    const resp = await fetch(url.toString(), options);
    clearTimeout(timer);
    const ct = resp.headers.get('content-type') || '';
    let data = null;
    if (ct.includes('application/json')) {
      try { data = await resp.json(); } catch { data = null; }
    } else {
      const text = await resp.text().catch(() => '');
      data = text ? { raw: text } : null;
    }
    return { ok: resp.ok, status: resp.status, data };
  } catch (err) { return { ok: false, error: err.message }; }
});
ipcMain.on('nav:navigate', (_e, page) => {});
ipcMain.on('play:payload', (_e, payload) => {
  // Forward external/legacy play requests into the renderer's player.
  if (mainWindow) mainWindow.webContents.send('play:from-main', payload);
});

// ── App Lifecycle ────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  try {
    await startBackend();
    createMainWindow();
  } catch (err) {
    console.error('[jmdb] Backend failed:', err);
    dialog.showErrorBox('JMDB Backend Error', err.message);
    app.quit();
  }
});

app.on('window-all-closed', () => { stopBackend(); if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { stopBackend(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createMainWindow(); });
