#!/usr/bin/env python3
import os
from pathlib import Path

PROJECT = Path(__file__).parent
SRC = PROJECT / "electron" / "src"

def write(rel, content):
    p = SRC / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    print(f"OK {rel}")

print("Rebuilding JMDB UI to match reference design...")

# ============ CSS ============
write("css/app.css", r""":root {
  --bg-primary: #0a0e17;
  --bg-secondary: #111827;
  --bg-tertiary: #1a2332;
  --bg-card: #1e293b;
  --bg-hover: #253349;
  --bg-active: #2d3f57;
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border-color: #1e293b;
  --border-light: #334155;
  --accent: #f59e0b;
  --accent-hover: #d97706;
  --accent-secondary: #3b82f6;
  --success: #10b981;
  --danger: #ef4444;
  --sidebar-width: 260px;
  --header-height: 64px;
  --radius: 8px;
  --radius-lg: 12px;
  --shadow: 0 4px 6px rgba(0,0,0,0.4);
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
body.theme-light {
  --bg-primary: #f8fafc; --bg-secondary: #ffffff; --bg-tertiary: #f1f5f9;
  --bg-card: #ffffff; --bg-hover: #f1f5f9; --bg-active: #e2e8f0;
  --text-primary: #0f172a; --text-secondary: #475569; --text-muted: #94a3b8;
  --border-color: #e2e8f0; --border-light: #cbd5e1;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; overflow: hidden; font-family: var(--font); background: var(--bg-primary); color: var(--text-primary); }
#app { display: flex; height: 100vh; }

/* SIDEBAR */
.sidebar { width: var(--sidebar-width); min-width: var(--sidebar-width); background: var(--bg-secondary); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; overflow-y: auto; }
.sidebar-header { padding: 20px; border-bottom: 1px solid var(--border-color); display: flex; align-items: center; gap: 12px; }
.logo-icon { width: 48px; height: 48px; background: linear-gradient(135deg, var(--accent), var(--accent-hover)); border-radius: var(--radius); display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; color: #000; }
.logo-text { display: flex; flex-direction: column; }
.logo-title { font-size: 18px; font-weight: 700; }
.logo-subtitle { font-size: 11px; color: var(--text-muted); }
.version-badge { font-size: 11px; padding: 2px 8px; background: var(--bg-tertiary); border-radius: 12px; color: var(--text-muted); margin: 0 20px 12px; display: inline-block; width: fit-content; }
.nav-section { margin-bottom: 8px; }
.nav-section-title { font-size: 11px; font-weight: 600; color: var(--text-muted); padding: 8px 20px; text-transform: uppercase; letter-spacing: 0.5px; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 10px 20px; color: var(--text-secondary); text-decoration: none; cursor: pointer; font-size: 14px; transition: all 0.15s; }
.nav-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-item.active { background: var(--bg-active); color: var(--accent); border-left: 3px solid var(--accent); }
.nav-icon { font-size: 16px; width: 20px; text-align: center; }
.nav-label { flex: 1; }

/* MAIN */
.main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
.top-bar { height: var(--header-height); min-height: var(--header-height); background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); display: flex; align-items: center; padding: 0 24px; gap: 16px; }
.search-container { flex: 1; max-width: 600px; position: relative; }
.search-input { width: 100%; padding: 10px 16px 10px 40px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: var(--radius); color: var(--text-primary); font-size: 14px; outline: none; }
.search-input:focus { border-color: var(--accent); }
.search-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: var(--text-muted); }
.top-bar-actions { display: flex; align-items: center; gap: 12px; margin-left: auto; }
.icon-btn { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: transparent; border: 1px solid var(--border-color); border-radius: var(--radius); color: var(--text-secondary); cursor: pointer; font-size: 18px; }
.icon-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; border: none; border-radius: var(--radius); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.15s; text-decoration: none; }
.btn-primary { background: var(--accent); color: #000; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-secondary { background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); }
.btn-secondary:hover { background: var(--bg-hover); }
.btn-danger { background: var(--danger); color: white; }
.btn-ghost { background: transparent; color: var(--text-secondary); }
.btn-ghost:hover { background: var(--bg-hover); color: var(--text-primary); }
.btn-sm { padding: 6px 12px; font-size: 12px; }

/* PAGE */
.page-container { flex: 1; overflow-y: auto; padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-muted); font-size: 14px; }

/* SECTIONS */
.section { margin-bottom: 32px; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.section-title { font-size: 18px; font-weight: 600; }
.section-link { color: var(--text-muted); font-size: 13px; cursor: pointer; }
.section-link:hover { color: var(--accent); }

/* CARD GRID */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; }
.media-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden; cursor: pointer; transition: all 0.2s; }
.media-card:hover { transform: translateY(-2px); box-shadow: var(--shadow); border-color: var(--border-light); }
.media-card-poster { width: 100%; aspect-ratio: 2/3; background: linear-gradient(135deg, #1e293b, #0f172a); display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; }
.media-card-poster img { width: 100%; height: 100%; object-fit: cover; }
.media-card-poster .placeholder { font-size: 48px; opacity: 0.3; }
.media-card-info { padding: 12px; }
.media-card-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.media-card-meta { font-size: 12px; color: var(--text-muted); }

/* CONTINUE CARD */
.continue-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden; cursor: pointer; transition: all 0.2s; }
.continue-card:hover { border-color: var(--border-light); }
.continue-card-image { width: 100%; aspect-ratio: 16/9; background: linear-gradient(135deg, #1e293b, #0f172a); position: relative; }
.continue-card-image img { width: 100%; height: 100%; object-fit: cover; }
.continue-card-info { padding: 12px; }
.continue-card-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.continue-card-episode { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
.continue-card-progress { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-muted); }
.progress-bar { width: 100%; height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: var(--accent); }

/* STATS */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 24px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 20px; display: flex; align-items: center; gap: 16px; }
.stat-icon { width: 56px; height: 56px; background: var(--bg-tertiary); border-radius: var(--radius); display: flex; align-items: center; justify-content: center; font-size: 28px; }
.stat-value { font-size: 32px; font-weight: 700; }
.stat-label { font-size: 13px; color: var(--text-muted); }
.stat-sublabel { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

/* FORMS */
.form-group { margin-bottom: 16px; }
.form-label { display: block; font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-bottom: 6px; }
.form-input, .form-select, .form-textarea { width: 100%; padding: 10px 12px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: var(--radius); color: var(--text-primary); font-size: 14px; outline: none; font-family: var(--font); }
.form-input:focus, .form-select:focus { border-color: var(--accent); }
.form-textarea { min-height: 100px; resize: vertical; }

/* TOGGLE */
.toggle { position: relative; display: inline-block; width: 44px; height: 24px; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: var(--bg-tertiary); border-radius: 24px; transition: 0.3s; }
.toggle-slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background: var(--text-secondary); border-radius: 50%; transition: 0.3s; }
.toggle input:checked + .toggle-slider { background: var(--accent); }
.toggle input:checked + .toggle-slider:before { transform: translateX(20px); background: #000; }

/* BADGE */
.badge { display: inline-flex; padding: 2px 8px; font-size: 11px; font-weight: 600; border-radius: 12px; background: var(--bg-tertiary); color: var(--text-secondary); }
.badge-success { background: var(--success); color: #000; }
.badge-danger { background: var(--danger); color: #fff; }
.badge-primary { background: var(--accent); color: #000; }

/* MODAL */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-lg); max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; }
.modal-header { padding: 20px 24px; border-bottom: 1px solid var(--border-color); display: flex; align-items: center; justify-content: space-between; }
.modal-title { font-size: 18px; font-weight: 600; }
.modal-close { background: none; border: none; color: var(--text-muted); font-size: 20px; cursor: pointer; }
.modal-body { padding: 24px; }
.modal-footer { padding: 16px 24px; border-top: 1px solid var(--border-color); display: flex; justify-content: flex-end; gap: 8px; }

/* TOAST */
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 2000; display: flex; flex-direction: column; gap: 8px; }
.toast { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius); padding: 12px 16px; min-width: 300px; box-shadow: var(--shadow); display: flex; align-items: center; gap: 12px; }
.toast-success { border-left: 4px solid var(--success); }
.toast-error { border-left: 4px solid var(--danger); }
.toast-info { border-left: 4px solid var(--accent-secondary); }

/* LOADING */
.loading-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 3000; gap: 16px; }
.loading-spinner { width: 48px; height: 48px; border: 4px solid var(--border-color); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* EMPTY */
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-muted); }
.empty-state-icon { font-size: 64px; margin-bottom: 16px; opacity: 0.5; }
.empty-state-title { font-size: 20px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }

/* DETAIL */
.detail-header { display: flex; gap: 32px; margin-bottom: 32px; }
.detail-poster { width: 300px; min-width: 300px; aspect-ratio: 2/3; background: var(--bg-tertiary); border-radius: var(--radius-lg); overflow: hidden; }
.detail-poster img { width: 100%; height: 100%; object-fit: cover; }
.detail-info { flex: 1; }
.detail-title { font-size: 32px; font-weight: 700; margin-bottom: 8px; }
.detail-meta { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.detail-meta-item { font-size: 14px; color: var(--text-secondary); }
.detail-description { font-size: 15px; line-height: 1.7; color: var(--text-secondary); margin-bottom: 24px; }
.detail-actions { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.genre-tags { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.genre-tag { padding: 4px 12px; background: var(--bg-tertiary); border-radius: 16px; font-size: 12px; color: var(--text-secondary); }

/* SERVICE CARD */
.service-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 20px; display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.service-icon { width: 48px; height: 48px; background: var(--bg-tertiary); border-radius: var(--radius); display: flex; align-items: center; justify-content: center; font-size: 24px; }
.service-info { flex: 1; }
.service-name { font-size: 16px; font-weight: 600; }
.service-status { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.service-actions { display: flex; gap: 8px; }

/* SETTINGS */
.settings-section { margin-bottom: 24px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 24px; }
.settings-section-title { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px; }
.settings-item { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border-color); }
.settings-item:last-child { border-bottom: none; }
.settings-item-title { font-size: 14px; font-weight: 500; }
.settings-item-desc { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

/* ABOUT */
.about-container { text-align: center; padding: 40px 20px; }
.about-logo { width: 120px; height: 120px; background: linear-gradient(135deg, var(--accent), var(--accent-hover)); border-radius: var(--radius-lg); display: flex; align-items: center; justify-content: center; font-size: 60px; font-weight: bold; color: #000; margin: 0 auto 24px; }
.about-title { font-size: 32px; font-weight: 700; margin-bottom: 4px; }
.about-subtitle { font-size: 16px; color: var(--text-muted); margin-bottom: 32px; }
.about-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; max-width: 500px; margin: 0 auto 32px; text-align: left; }
.about-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius); padding: 12px 16px; }
.about-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.about-value { font-size: 14px; font-family: monospace; }
.about-licenses { max-width: 600px; margin: 32px auto 0; text-align: left; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 20px; }

/* BROWSER */
.browser-container { display: flex; flex-direction: column; height: 100%; }
.browser-toolbar { display: flex; gap: 8px; padding: 8px 12px; background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); align-items: center; }
.browser-toolbar input { flex: 1; background: var(--bg-tertiary); border: 1px solid var(--border-color); color: var(--text-primary); padding: 8px 16px; border-radius: 20px; outline: none; }
.browser-menu { position: absolute; top: 50px; right: 20px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-lg); width: 320px; box-shadow: var(--shadow); z-index: 1000; max-height: 80vh; overflow-y: auto; padding: 8px 0; }
.browser-menu-item { padding: 10px 16px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 14px; color: var(--text-primary); }
.browser-menu-item:hover { background: var(--bg-hover); }
.browser-menu-item .menu-icon { width: 20px; text-align: center; color: var(--text-secondary); }
.browser-menu-item .menu-shortcut { font-size: 12px; color: var(--text-muted); }
.browser-menu-sep { height: 1px; background: var(--border-color); margin: 4px 0; }
.browser-menu-sub { padding-left: 20px; display: none; }
.browser-menu-sub.open { display: block; }
.browser-menu-sub .browser-menu-item { font-size: 13px; }
webview { width: 100%; flex: 1; border: none; background: white; }

/* TABS */
.tabs { display: flex; border-bottom: 1px solid var(--border-color); margin-bottom: 20px; }
.tab { padding: 10px 16px; font-size: 14px; color: var(--text-secondary); cursor: pointer; border-bottom: 2px solid transparent; }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab:hover { color: var(--text-primary); }

/* TABLE */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border-color); }
.data-table th { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }

/* SCROLLBAR */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

.hidden { display: none !important; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-1 { gap: 8px; }
.gap-2 { gap: 16px; }
.mt-1 { margin-top: 8px; }
.mt-2 { margin-top: 16px; }
.mt-3 { margin-top: 24px; }
.mb-1 { margin-bottom: 8px; }
.mb-2 { margin-bottom: 16px; }
.mb-3 { margin-bottom: 24px; }
.text-muted { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }
.text-accent { color: var(--accent); }
""")

# ============ HTML ============
write("index.html", """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https: http:; connect-src 'self' http://127.0.0.1:*;">
  <title>JMDB - Johnny's Media Database</title>
  <link rel="stylesheet" href="css/app.css">
</head>
<body class="theme-dark">
  <div id="app">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo-icon">J</div>
        <div class="logo-text">
          <div class="logo-title">JMDB</div>
          <div class="logo-subtitle">Johnny's Media Database</div>
        </div>
      </div>
      <span class="version-badge">v1.0.0</span>
      <nav>
        <div class="nav-section">
          <div class="nav-section-title">Library</div>
          <a class="nav-item active" data-page="home"><span class="nav-icon">🏠</span><span class="nav-label">Home</span></a>
          <a class="nav-item" data-page="movies"><span class="nav-icon">🎬</span><span class="nav-label">Movies</span></a>
          <a class="nav-item" data-page="tvshows"><span class="nav-icon">📺</span><span class="nav-label">TV Shows</span></a>
          <a class="nav-item" data-page="music"><span class="nav-icon">🎵</span><span class="nav-label">Music</span></a>
          <a class="nav-item" data-page="people"><span class="nav-icon">👤</span><span class="nav-label">People</span></a>
          <a class="nav-item" data-page="recommended"><span class="nav-icon"></span><span class="nav-label">Recommended</span></a>
        </div>
        <div class="nav-section">
          <div class="nav-section-title">Your Lists</div>
          <a class="nav-item" data-page="favorites"><span class="nav-icon">❤️</span><span class="nav-label">Favorites</span></a>
          <a class="nav-item" data-page="watchlist"><span class="nav-icon">⭐</span><span class="nav-label">Watchlist</span></a>
          <a class="nav-item" data-page="history"><span class="nav-icon">🕐</span><span class="nav-label">History</span></a>
          <a class="nav-item" data-page="collections"><span class="nav-icon"></span><span class="nav-label">Collections</span></a>
        </div>
        <div class="nav-section">
          <div class="nav-section-title">More</div>
          <a class="nav-item" data-page="browser"><span class="nav-icon">🌐</span><span class="nav-label">Browser Hub</span></a>
          <a class="nav-item" data-page="services"><span class="nav-icon">🔌</span><span class="nav-label">Services</span></a>
          <a class="nav-item" data-page="statistics"><span class="nav-icon">📊</span><span class="nav-label">Statistics</span></a>
          <a class="nav-item" data-page="settings"><span class="nav-icon">️</span><span class="nav-label">Settings</span></a>
        </div>
      </nav>
    </aside>
    <main class="main-content">
      <header class="top-bar">
        <div class="search-container">
          <span class="search-icon">🔍</span>
          <input type="text" id="global-search" class="search-input" placeholder="Search library, movies, shows, music, people...">
        </div>
        <div class="top-bar-actions">
          <button id="theme-toggle" class="icon-btn" title="Toggle theme">🌙</button>
          <button id="add-library-btn" class="btn btn-primary">+ Add Library</button>
        </div>
      </header>
      <div id="page-container" class="page-container"></div>
    </main>
  </div>
  <div id="modal-container" class="modal-container"></div>
  <div id="toast-container" class="toast-container"></div>
  <div id="loading-overlay" class="loading-overlay hidden">
    <div class="loading-spinner"></div>
    <div class="loading-text">Loading...</div>
  </div>
  <script src="js/app.js"></script>
  <script src="js/browser.js"></script>
</body>
</html>""")

print("\nUI rebuild complete!")
