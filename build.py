#!/usr/bin/env python3
import os
from pathlib import Path

PROJECT = Path(__file__).parent

def write_file(rel_path: str, content: str):
    full_path = PROJECT / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    print(f"✓ {rel_path}")

print("🚀 Building complete JMDB structure...")

# 1. Root Files
write_file("requirements.txt", """fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
httpx>=0.25.0
psutil>=5.9.0
""")

write_file("electron/package.json", """{
  "name": "jmdb",
  "version": "1.0.0",
  "main": "main.js",
  "scripts": { "start": "electron ." },
  "devDependencies": { "electron": "^28.0.0" }
}""")

# 2. Electron Core
write_file("electron/main.js", """const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200, height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webviewTag: true
    }
  });
  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

ipcMain.handle('get-backend-port', () => process.env.JMDB_BACKEND_PORT || '8765');
ipcMain.handle('show-open-dialog', async () => { /* Placeholder for native dialog */ return { canceled: false, filePaths: ['/tmp'] }; });

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
""")

write_file("electron/preload.js", """const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('jmdb', {
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  showOpenDialog: () => ipcRenderer.invoke('show-open-dialog')
});
""")

# 3. Frontend HTML
write_file("electron/src/index.html", """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:*;">
  <title>JMDB</title>
  <link rel="stylesheet" href="css/app.css">
</head>
<body class="theme-dark">
  <div id="app">
    <aside class="sidebar">
      <div class="logo">JMDB</div>
      <nav>
        <a href="#" onclick="App.nav('home')" class="active">🏠 Home</a>
        <a href="#" onclick="App.nav('library')">📁 Library</a>
        <a href="#" onclick="App.nav('browser')">🌐 Browser</a>
        <a href="#" onclick="App.nav('settings')">⚙️ Settings</a>
      </nav>
    </aside>
    <main class="main-content">
      <header class="top-bar">
        <h2 id="page-title">Home</h2>
        <button class="btn" onclick="App.toggleTheme()">🌙 Theme</button>
      </header>
      <div id="page-container" class="page-container"></div>
    </main>
  </div>
  <script src="js/app.js"></script>
  <script src="js/browser.js"></script>
</body>
</html>
""")

# 4. Frontend CSS
write_file("electron/src/css/app.css", """:root {
  --bg: #0f172a; --bg-sec: #1e293b; --text: #f8fafc; --text-mut: #94a3b8;
  --accent: #f59e0b; --border: #334155;
}
body.theme-light { --bg: #f8fafc; --bg-sec: #ffffff; --text: #0f172a; --text-mut: #64748b; --border: #e2e8f0; }
* { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; }
body { background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; }
#app { display: flex; height: 100%; }
.sidebar { width: 240px; background: var(--bg-sec); border-right: 1px solid var(--border); padding: 20px; display: flex; flex-direction: column; }
.logo { font-size: 24px; font-weight: bold; color: var(--accent); margin-bottom: 30px; }
.sidebar nav a { display: block; padding: 10px; color: var(--text-mut); text-decoration: none; border-radius: 6px; margin-bottom: 4px; }
.sidebar nav a:hover, .sidebar nav a.active { background: var(--bg); color: var(--accent); }
.main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.top-bar { height: 60px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; background: var(--bg-sec); }
.page-container { flex: 1; padding: 24px; overflow-y: auto; }
.btn { background: var(--accent); color: #000; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
.card { background: var(--bg-sec); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
/* Browser Styles */
.browser-toolbar { display: flex; gap: 8px; padding: 8px; background: var(--bg-sec); border-bottom: 1px solid var(--border); }
.browser-toolbar input { flex: 1; background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 6px 12px; border-radius: 20px; }
.browser-menu { position: absolute; top: 50px; right: 20px; background: var(--bg-sec); border: 1px solid var(--border); border-radius: 8px; width: 250px; box-shadow: 0 10px 15px rgba(0,0,0,0.5); z-index: 100; }
.browser-menu-item { padding: 10px 16px; cursor: pointer; display: flex; justify-content: space-between; }
.browser-menu-item:hover { background: var(--bg); }
.browser-menu-sep { height: 1px; background: var(--border); margin: 4px 0; }
webview { width: 100%; height: calc(100vh - 110px); border: none; }
""")

# 5. Frontend JS
write_file("electron/src/js/app.js", """const App = {
  port: 8765,
  async init() {
    if (window.jmdb) this.port = await window.jmdb.getBackendPort();
    this.nav('home');
  },
  nav(page) {
    document.querySelectorAll('.sidebar nav a').forEach(a => a.classList.remove('active'));
    event?.target?.classList.add('active');
    document.getElementById('page-title').textContent = page.charAt(0).toUpperCase() + page.slice(1);
    const container = document.getElementById('page-container');
    container.innerHTML = '';
    
    if (page === 'home') {
      container.innerHTML = '<div class="card"><h3>Welcome to JMDB</h3><p style="color:var(--text-mut);margin-top:8px;">Your media database is running.</p><button class="btn" style="margin-top:16px;" onclick="App.testApi()">Test Backend Connection</button><p id="api-result" style="margin-top:8px;font-size:13px;"></p></div>';
    } else if (page === 'library') {
      container.innerHTML = '<div class="card"><h3>Library Scanner</h3><p style="color:var(--text-mut);margin:8px 0;">Scan a local folder for media files.</p><button class="btn" onclick="App.scanLibrary()">📁 Select Folder & Scan</button><pre id="scan-result" style="margin-top:16px;font-size:12px;color:var(--text-mut);"></pre></div>';
    } else if (page === 'browser') {
      Browser.init(container);
    } else if (page === 'settings') {
      container.innerHTML = '<div class="card"><h3>Settings</h3><p>Theme: <button class="btn" onclick="App.toggleTheme()">Toggle</button></p></div>';
    }
  },
  async testApi() {
    try {
      const res = await fetch(`http://127.0.0.1:${this.port}/api/health`);
      const data = await res.json();
      document.getElementById('api-result').textContent = `✅ Connected! Python: ${data.python}`;
      document.getElementById('api-result').style.color = '#10b981';
    } catch (e) {
      document.getElementById('api-result').textContent = '❌ Backend not reachable.';
      document.getElementById('api-result').style.color = '#ef4444';
    }
  },
  async scanLibrary() {
    document.getElementById('scan-result').textContent = 'Scanning... (Simulated for demo)';
    setTimeout(() => {
      document.getElementById('scan-result').textContent = '✅ Found 0 media files in /tmp (Demo mode).\\nBackend API /api/library/scan is ready for real paths.';
    }, 1000);
  },
  toggleTheme() {
    document.body.classList.toggle('theme-dark');
    document.body.classList.toggle('theme-light');
  }
};
document.addEventListener('DOMContentLoaded', () => App.init());
""")

write_file("electron/src/js/browser.js", """const Browser = {
  init(container) {
    container.innerHTML = `
      <div class="browser-toolbar">
        <button class="btn" style="padding:4px 12px;" onclick="Browser.back()">◀</button>
        <button class="btn" style="padding:4px 12px;" onclick="Browser.fwd()">▶</button>
        <button class="btn" style="padding:4px 12px;" onclick="Browser.reload()">⟳</button>
        <input type="text" id="b-url" value="https://www.wikipedia.org" onkeydown="if(event.key==='Enter')Browser.go()">
        <button class="btn" style="padding:4px 12px;" onclick="Browser.toggleMenu()">☰</button>
      </div>
      <webview id="b-web" src="https://www.wikipedia.org" partition="persist:browser"></webview>
      <div id="b-menu" class="browser-menu" style="display:none;">
        <div class="browser-menu-item" onclick="Browser.zoom(0.1)">Zoom In <span>+</span></div>
        <div class="browser-menu-item" onclick="Browser.zoom(-0.1)">Zoom Out <span>-</span></div>
        <div class="browser-menu-sep"></div>
        <div class="browser-menu-item" onclick="Browser.action('print')">Print</div>
        <div class="browser-menu-item" onclick="Browser.action('fullscreen')">Fullscreen</div>
        <div class="browser-menu-sep"></div>
        <div class="browser-menu-item" onclick="App.nav('settings')">Browser Settings</div>
        <div class="browser-menu-sep"></div>
        <div class="browser-menu-item" onclick="alert('JMDB v1.0.0\\nElectron Browser Engine')">About JMDB</div>
      </div>
    `;
    this.web = document.getElementById('b-web');
    this.web.addEventListener('did-navigate', (e) => { document.getElementById('b-url').value = e.url; });
  },
  go() {
    let url = document.getElementById('b-url').value;
    if (!url.startsWith('http')) url = 'https://' + url;
    this.web.src = url;
  },
  back() { if (this.web.canGoBack()) this.web.goBack(); },
  fwd() { if (this.web.canGoForward()) this.web.goForward(); },
  reload() { this.web.reload(); },
  toggleMenu() {
    const menu = document.getElementById('b-menu');
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
  },
  zoom(delta) {
    const current = this.web.getZoomFactor() || 1;
    this.web.setZoomFactor(Math.max(0.5, Math.min(2.0, current + delta)));
  },
  action(act) {
    if (act === 'print') this.web.print();
    if (act === 'fullscreen') document.documentElement.requestFullscreen();
    document.getElementById('b-menu').style.display = 'none';
  }
};
""")

# 6. Updated Backend API (Scanner & Playback)
write_file("app/api/library.py", """from fastapi import APIRouter, BackgroundTasks
from app.media.scanner import scan_directory

router = APIRouter()

@router.get("/library")
def get_libraries():
    return {"libraries": []}

@router.post("/library/scan")
def scan_library(path: str, bg: BackgroundTasks):
    # In a real app, this would run in background and update a state
    files = scan_directory(path)
    return {"status": "completed", "found": len(files)}
""")

write_file("app/media/scanner.py", """from pathlib import Path

SUPPORTED = {".mp4", ".mkv", ".avi", ".mp3", ".flac", ".jpg", ".png"}

def scan_directory(directory: str):
    results = []
    d = Path(directory)
    if not d.exists() or not d.is_dir():
        return results
    for f in d.rglob("*"):
        if f.is_file() and f.suffix.lower() in SUPPORTED:
            results.append({"name": f.name, "path": str(f), "size": f.stat().st_size})
    return results
""")

# 7. Update main.py to include new routers
write_file("app/main.py", """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database.connection import get_engine
from app.database.models import Base
from app.api import health, media, library

settings = get_settings()
engine = get_engine(settings.db_path)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="JMDB", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(library.router, prefix="/api")

@app.get("/")
def root():
    return {"name": "JMDB", "status": "running", "ui": "electron"}
""")

# 8. Ultimate Runner (Backend + Electron)
write_file("run.py", """#!/usr/bin/env python3
import subprocess, sys, time, urllib.request, os
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
ELECTRON_DIR = ROOT / "electron"

def check_deps():
    try:
        import fastapi, uvicorn, sqlalchemy
        print("[JMDB] Python Dependencies OK")
    except ImportError:
        print("ERROR: Run 'pip install -r requirements.txt'")
        sys.exit(1)

def start_backend():
    port = 8765
    print(f"[JMDB] Starting Backend on 127.0.0.1:{port}")
    env = os.environ.copy()
    env["JMDB_BACKEND_PORT"] = str(port)
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def wait_backend(port, timeout=15):
    url = f"http://127.0.0.1:{port}/api/health"
    for _ in range(timeout * 2):
        try:
            if urllib.request.urlopen(url, timeout=1).getcode() == 200:
                return True
        except: pass
        time.sleep(0.5)
    return False

def start_electron(port):
    npm = ELECTRON_DIR / "node_modules" / ".bin" / "electron"
    if not npm.exists():
        print("[JMDB] Installing Electron (one time)...")
        subprocess.run(["npm", "install"], cwd=str(ELECTRON_DIR), capture_output=True)
    
    print("[JMDB] Launching Desktop UI...")
    env = os.environ.copy()
    env["JMDB_BACKEND_PORT"] = str(port)
    return subprocess.Popen([str(npm), str(ELECTRON_DIR)], cwd=str(ELECTRON_DIR), env=env)

if __name__ == "__main__":
    print("="*50)
    print("  JMDB - Johnny's Media Database v1.0.0")
    print("="*50)
    check_deps()
    
    bp = start_backend()
    if not wait_backend(8765):
        print("[JMDB] ERROR: Backend failed to start.")
        sys.exit(1)
        
    print("[JMDB] ✅ Backend Healthy!")
    
    # Check if we are in a GUI environment
    if os.environ.get("DISPLAY") or sys.platform == "darwin" or sys.platform == "win32":
        ep = start_electron(8765)
        try:
            ep.wait()
        except KeyboardInterrupt:
            pass
        finally:
            bp.terminate()
    else:
        print("[JMDB] No display detected. Running backend only.")
        print("[JMDB] Open http://127.0.0.1:8765 in your browser.")
        try:
            bp.wait()
        except KeyboardInterrupt:
            bp.terminate()
""")

print("\\n" + "="*50)
print("✅ JMDB Full Structure Built Successfully!")
print("Next steps:")
print("1. cd electron && npm install")
print("2. cd .. && source venv/bin/activate")
print("3. python run.py")
print("="*50)
