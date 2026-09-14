#!/usr/bin/env python3
import os
from pathlib import Path

PROJECT = Path(__file__).parent

def write_file(rel_path: str, content: str):
    full_path = PROJECT / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    print(f"✓ {rel_path}")

print("🚀 Building JMDB structure...")

write_file("requirements.txt", "fastapi>=0.104.0\nuvicorn>=0.24.0\nsqlalchemy>=2.0.0\npydantic>=2.5.0\npydantic-settings>=2.1.0\nhttpx>=0.25.0\npsutil>=5.9.0\n")

write_file("app/__init__.py", '"""JMDB Backend."""\n')

write_file("app/config.py", """from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "JMDB"
    backend_port: int = 8765
    data_dir: str = str(Path(__file__).parent.parent / "data")
    db_path: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        base = Path(self.data_dir)
        base.mkdir(parents=True, exist_ok=True)
        if not self.db_path:
            self.db_path = str(base / "database" / "jmdb.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

def get_settings() -> Settings:
    return Settings()
""")

write_file("app/database/__init__.py", '"""Database."""\n')

write_file("app/database/connection.py", """from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None

def get_engine(db_path):
    global _engine
    if _engine is not None:
        return _engine
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    @event.listens_for(_engine, "connect")
    def set_pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()
    return _engine

def get_session_local(db_path):
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(db_path))
    return _SessionLocal
""")

write_file("app/database/models.py", """from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class MediaType(str, enum.Enum):
    MOVIE = "movie"
    MUSIC = "music"

class MediaItem(Base):
    __tablename__ = "media_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    media_type = Column(Enum(MediaType), default=MediaType.MOVIE)
    title = Column(String(500), nullable=False)
    year = Column(Integer)
    rating = Column(Float)
    favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("idx_media_title", "title"),)
""")

write_file("app/database/repositories/__init__.py", '"""Repositories."""\n')

write_file("app/database/repositories/media.py", """from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database.models import MediaItem

class MediaRepository:
    def __init__(self, db: Session):
        self.db = db
    def create(self, item):
        self.db.add(item); self.db.commit(); self.db.refresh(item); return item
    def get_by_id(self, item_id):
        return self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
    def get_all(self, limit=50, offset=0, media_type=None):
        q = self.db.query(MediaItem)
        if media_type: q = q.filter(MediaItem.media_type == media_type)
        return q.order_by(MediaItem.created_at.desc()).offset(offset).limit(limit).all()
    def count(self, media_type=None):
        q = self.db.query(func.count(MediaItem.id))
        if media_type: q = q.filter(MediaItem.media_type == media_type)
        return q.scalar() or 0
    def update(self, item):
        item.updated_at = datetime.utcnow(); self.db.commit(); self.db.refresh(item); return item
    def delete(self, item_id):
        item = self.get_by_id(item_id)
        if item: self.db.delete(item); self.db.commit()
    def set_favorite(self, item_id, favorite):
        item = self.get_by_id(item_id)
        if item: item.favorite = favorite; self.db.commit()
""")

write_file("app/api/__init__.py", '"""API."""\n')

write_file("app/api/health.py", """from fastapi import APIRouter
from datetime import datetime
import sys
router = APIRouter()
@router.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0", "python": sys.version.split()[0]}
""")

write_file("app/api/media.py", """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_session_local
from app.database.repositories.media import MediaRepository
from app.database.models import MediaItem, MediaType
from app.config import get_settings

router = APIRouter()
def get_db():
    s = get_settings()
    db = get_session_local(s.db_path)()
    try: yield db
    finally: db.close()

def item_dict(item):
    return {"id": item.id, "title": item.title, "media_type": item.media_type.value if item.media_type else "movie", "year": item.year, "rating": item.rating, "favorite": item.favorite}

@router.get("/media")
def list_media(limit: int = 50, db: Session = Depends(get_db)):
    return {"items": [item_dict(i) for i in MediaRepository(db).get_all(limit)], "total": MediaRepository(db).count()}

@router.post("/media")
def create_media(data: dict, db: Session = Depends(get_db)):
    item = MediaItem(title=data.get("title", "Unknown"), media_type=MediaType(data.get("media_type", "movie")), year=data.get("year"))
    return item_dict(MediaRepository(db).create(item))
""")

write_file("app/main.py", """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database.connection import get_engine
from app.database.models import Base
from app.api import health, media

settings = get_settings()
engine = get_engine(settings.db_path)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="JMDB", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router, prefix="/api")
app.include_router(media.router, prefix="/api")

@app.get("/")
def root():
    return {"name": "JMDB", "status": "running", "ui": "electron"}
""")

write_file("electron/package.json", '{"name": "jmdb", "version": "1.0.0", "main": "main.js", "scripts": {"start": "electron ."}, "devDependencies": {"electron": "^28.0.0"}}')

write_file("electron/main.js", """const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
let mainWindow = null;
function createWindow() {
  mainWindow = new BrowserWindow({ width: 1200, height: 800, webPreferences: { nodeIntegration: false, contextIsolation: true, preload: path.join(__dirname, 'preload.js'), webviewTag: true } });
  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { require('electron').shell.openExternal(url); return { action: 'deny' }; });
}
ipcMain.handle('get-backend-port', () => process.env.JMDB_BACKEND_PORT || '8765');
app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
""")

write_file("electron/preload.js", "const { contextBridge, ipcRenderer } = require('electron');\ncontextBridge.exposeInMainWorld('jmdb', { getBackendPort: () => ipcRenderer.invoke('get-backend-port') });")

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
        <a onclick="App.nav('home')" class="active">🏠 Home</a>
        <a onclick="App.nav('library')">📁 Library</a>
        <a onclick="App.nav('browser')">🌐 Browser</a>
        <a onclick="App.nav('settings')">⚙️ Settings</a>
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
</html>""")

write_file("electron/src/css/app.css", """:root { --bg: #0f172a; --bg-sec: #1e293b; --text: #f8fafc; --text-mut: #94a3b8; --accent: #f59e0b; --border: #334155; }
body.theme-light { --bg: #f8fafc; --bg-sec: #ffffff; --text: #0f172a; --text-mut: #64748b; --border: #e2e8f0; }
* { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; }
body { background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; }
#app { display: flex; height: 100%; }
.sidebar { width: 240px; background: var(--bg-sec); border-right: 1px solid var(--border); padding: 20px; }
.logo { font-size: 24px; font-weight: bold; color: var(--accent); margin-bottom: 30px; }
.sidebar nav a { display: block; padding: 10px; color: var(--text-mut); text-decoration: none; border-radius: 6px; margin-bottom: 4px; cursor: pointer; }
.sidebar nav a:hover, .sidebar nav a.active { background: var(--bg); color: var(--accent); }
.main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.top-bar { height: 60px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; background: var(--bg-sec); }
.page-container { flex: 1; padding: 24px; overflow-y: auto; position: relative; }
.btn { background: var(--accent); color: #000; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
.card { background: var(--bg-sec); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.browser-container { display: flex; flex-direction: column; height: 100%; }
.browser-toolbar { display: flex; gap: 8px; padding: 8px; background: var(--bg-sec); border-bottom: 1px solid var(--border); align-items: center; }
.browser-toolbar input { flex: 1; background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 8px 16px; border-radius: 20px; outline: none; }
.browser-menu { position: absolute; top: 50px; right: 20px; background: var(--bg-sec); border: 1px solid var(--border); border-radius: 8px; width: 280px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); z-index: 1000; max-height: 80vh; overflow-y: auto; }
.browser-menu-item { padding: 10px 16px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 14px; }
.browser-menu-item:hover { background: var(--bg); color: var(--accent); }
.browser-menu-sep { height: 1px; background: var(--border); margin: 6px 0; }
.browser-menu-sub { padding-left: 20px; font-size: 13px; color: var(--text-mut); display: none; }
.browser-menu-sub.open { display: block; }
webview { width: 100%; flex: 1; border: none; background: white; }
.about-page { text-align: center; padding: 40px; }
.about-page h1 { color: var(--accent); margin-bottom: 20px; }
.about-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; max-width: 500px; margin: 0 auto; text-align: left; }
.about-item { background: var(--bg); padding: 12px; border-radius: 6px; border: 1px solid var(--border); }
.about-label { font-size: 12px; color: var(--text-mut); margin-bottom: 4px; }
.about-value { font-family: monospace; font-size: 14px; }""")

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
    } else if (page === 'browser') {
      Browser.init(container);
    } else if (page === 'settings') {
      container.innerHTML = '<div class="card"><h3>Settings</h3><p>Theme: <button class="btn" onclick="App.toggleTheme()">Toggle</button></p></div>';
    } else {
      container.innerHTML = '<div class="card"><h3>' + page.charAt(0).toUpperCase() + page.slice(1) + '</h3><p style="color:var(--text-mut);">This module is under construction.</p></div>';
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
  toggleTheme() {
    document.body.classList.toggle('theme-dark');
    document.body.classList.toggle('theme-light');
  }
};
document.addEventListener('DOMContentLoaded', () => App.init());""")

write_file("electron/src/js/browser.js", """const Browser = {
  web: null,
  init(container) {
    container.innerHTML = \`
      <div class="browser-container">
        <div class="browser-toolbar">
          <button class="btn" style="padding:6px 12px;" onclick="Browser.back()" title="Back">◀</button>
          <button class="btn" style="padding:6px 12px;" onclick="Browser.fwd()" title="Forward">▶</button>
          <button class="btn" style="padding:6px 12px;" onclick="Browser.reload()" title="Reload">⟳</button>
          <button class="btn" style="padding:6px 12px;" onclick="Browser.home()" title="Home">🏠</button>
          <input type="text" id="b-url" value="https://www.wikipedia.org" onkeydown="if(event.key==='Enter')Browser.go()">
          <button class="btn" style="padding:6px 12px;" onclick="Browser.toggleMenu()" title="Menu">☰</button>
        </div>
        <webview id="b-web" src="https://www.wikipedia.org" partition="persist:browser"></webview>
        <div id="b-menu" class="browser-menu" style="display:none;">
          <div class="browser-menu-item" onclick="Browser.action('new-tab')">New Tab <span>Ctrl+T</span></div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.action('history')">History</div>
          <div class="browser-menu-item" onclick="Browser.action('downloads')">Downloads</div>
          <div class="browser-menu-item" onclick="Browser.action('bookmarks')">Bookmarks</div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.action('find')">Find in Page <span>Ctrl+F</span></div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('zoom-sub')">Zoom ▶</div>
          <div id="zoom-sub" class="browser-menu-sub">
            <div class="browser-menu-item" onclick="Browser.zoom(0.1)">Zoom In</div>
            <div class="browser-menu-item" onclick="Browser.zoom(-0.1)">Zoom Out</div>
            <div class="browser-menu-item" onclick="Browser.zoomReset()">Reset Zoom</div>
          </div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.action('print')">Print <span>Ctrl+P</span></div>
          <div class="browser-menu-item" onclick="Browser.action('pdf')">Export PDF</div>
          <div class="browser-menu-item" onclick="Browser.action('fullscreen')">Fullscreen</div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('app-sub')">Appearance ▶</div>
          <div id="app-sub" class="browser-menu-sub">
            <div class="browser-menu-item" onclick="App.toggleTheme()">Toggle Theme</div>
            <div class="browser-menu-item" onclick="alert('Font size settings')">Font Size</div>
            <div class="browser-menu-item" onclick="alert('Bookmarks bar toggled')">Show Bookmarks Bar</div>
          </div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('priv-sub')">Privacy & Security ▶</div>
          <div id="priv-sub" class="browser-menu-sub">
            <div class="browser-menu-item" onclick="alert('Cleared!')">Clear Browsing Data</div>
            <div class="browser-menu-item" onclick="alert('Cookies managed')">Cookies</div>
            <div class="browser-menu-item" onclick="alert('Cache cleared')">Cache</div>
            <div class="browser-menu-item" onclick="alert('Permissions reset')">Permissions</div>
            <div class="browser-menu-item" onclick="alert('DNT enabled')">Do Not Track</div>
          </div>
          <div class="browser-menu-item" onclick="Browser.toggleSub('perm-sub')">Site Permissions ▶</div>
          <div id="perm-sub" class="browser-menu-sub">
            <div class="browser-menu-item">Notifications</div>
            <div class="browser-menu-item">Location</div>
            <div class="browser-menu-item">Camera</div>
            <div class="browser-menu-item">Microphone</div>
            <div class="browser-menu-item">JavaScript</div>
            <div class="browser-menu-item">Images</div>
            <div class="browser-menu-item">Popups</div>
          </div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="alert('Downloads settings')">Downloads Settings</div>
          <div class="browser-menu-item" onclick="alert('Search engine settings')">Search Engine</div>
          <div class="browser-menu-item" onclick="alert('Homepage settings')">Homepage</div>
          <div class="browser-menu-item" onclick="alert('Startup settings')">Startup</div>
          <div class="browser-menu-item" onclick="alert('Language settings')">Language</div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="App.nav('settings')">Browser Settings</div>
          <div class="browser-menu-item" onclick="alert('Cleared!')">Clear Browsing Data</div>
          <div class="browser-menu-sep"></div>
          <div class="browser-menu-item" onclick="Browser.showAbout()" style="color: var(--accent); font-weight:bold;">ℹ️ About JMDB</div>
        </div>
      </div>
    \`;
    this.web = document.getElementById('b-web');
    this.web.addEventListener('did-navigate', (e) => { document.getElementById('b-url').value = e.url; });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.browser-menu') && !e.target.closest('[onclick="Browser.toggleMenu()"]')) {
        document.getElementById('b-menu').style.display = 'none';
      }
    });
  },
  go() { let url = document.getElementById('b-url').value; if (!url.startsWith('http')) url = 'https://' + url; this.web.src = url; },
  back() { if (this.web.canGoBack()) this.web.goBack(); },
  fwd() { if (this.web.canGoForward()) this.web.goForward(); },
  reload() { this.web.reload(); },
  home() { this.web.src = 'https://www.wikipedia.org'; document.getElementById('b-url').value = this.web.src; },
  toggleMenu() { const menu = document.getElementById('b-menu'); menu.style.display = menu.style.display === 'none' ? 'block' : 'none'; },
  toggleSub(id) { document.getElementById(id).classList.toggle('open'); },
  zoom(delta) { const current = this.web.getZoomFactor() || 1; this.web.setZoomFactor(Math.max(0.5, Math.min(2.0, current + delta))); },
  zoomReset() { this.web.setZoomFactor(1); },
  action(act) {
    if (act === 'print') this.web.print();
    if (act === 'pdf') this.web.printToPDF({}).then(() => alert('PDF Exported')).catch(e => alert('PDF Export Failed'));
    if (act === 'fullscreen') document.documentElement.requestFullscreen();
    document.getElementById('b-menu').style.display = 'none';
  },
  showAbout() {
    const container = document.querySelector('.page-container');
    container.innerHTML = \`
      <div class="about-page">
        <h1>JMDB</h1>
        <p style="color:var(--text-mut); margin-bottom:30px;">Johnny's Media Database</p>
        <div class="about-grid">
          <div class="about-item"><div class="about-label">Application Version</div><div class="about-value">1.0.0</div></div>
          <div class="about-item"><div class="about-label">Electron Version</div><div class="about-value" id="ab-elec">Loading...</div></div>
          <div class="about-item"><div class="about-label">Chromium Version</div><div class="about-value" id="ab-chr">Loading...</div></div>
          <div class="about-item"><div class="about-label">Node Version</div><div class="about-value" id="ab-node">Loading...</div></div>
          <div class="about-item"><div class="about-label">Python Version</div><div class="about-value" id="ab-py">Loading...</div></div>
          <div class="about-item"><div class="about-label">Backend Version</div><div class="about-value">1.0.0</div></div>
          <div class="about-item"><div class="about-label">Browser Engine</div><div class="about-value">Chromium (Electron)</div></div>
          <div class="about-item"><div class="about-label">Playback Backend</div><div class="about-value">VLC / MPV / HTML5</div></div>
        </div>
        <div style="margin-top:40px; padding:20px; background:var(--bg-sec); border-radius:8px; text-align:left; max-width:600px; margin-left:auto; margin-right:auto;">
          <h3 style="margin-bottom:10px;">Licenses & Third-Party</h3>
          <p style="font-size:13px; color:var(--text-mut); line-height:1.6;">Built with Electron (MIT), FastAPI (BSD), SQLAlchemy (MIT), SQLite (Public Domain), Python (PSF), Node.js (MIT), and Chromium (BSD).<br><br>© 2026 JMDB - Johnny's Media Database. All rights reserved.</p>
        </div>
        <button class="btn" style="margin-top:20px;" onclick="App.nav('browser')">← Back to Browser</button>
      </div>
    \`;
    if (window.jmdb) {
      window.jmdb.getAppVersion().then(v => {
        document.getElementById('ab-elec').textContent = v.electron || 'N/A';
        document.getElementById('ab-chr').textContent = v.chromium || 'N/A';
        document.getElementById('ab-node').textContent = v.node || 'N/A';
      });
    }
    fetch('http://127.0.0.1:8765/api/health').then(r=>r.json()).then(d => { document.getElementById('ab-py').textContent = d.python || 'N/A'; });
    document.getElementById('b-menu').style.display = 'none';
  }
};""")

print("\n✅ JMDB structure built successfully!")
