const Player = {
  activeMediaId: null,
  activeFile: null,
  backendPort: 8765,
  playerType: 'mpv',
  videoEl: null,
  playbackInterval: null,

  init(container) {
    container.innerHTML = `
      <div class="player-container" style="height:100%;display:flex;flex-direction:column;background:#000;">
        <div id="player-video-area" style="flex:1;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;">
          <video id="player-video" style="width:100%;height:100%;object-fit:contain;display:none;"></video>
          <div id="player-placeholder" style="text-align:center;color:var(--text-muted);">
            <div style="font-size:72px;margin-bottom:16px;">▶</div>
            <h2>Select a media item to play</h2>
            <p style="margin-top:8px;font-size:14px;">Navigate to Library and choose a movie or show</p>
          </div>
        </div>
        <div class="player-controls" id="player-controls">
          <div class="player-progress" id="player-progress-bar" style="cursor:pointer;padding:8px 16px 4px;">
            <div class="progress-track" style="width:100%;height:4px;background:rgba(255,255,255,0.2);border-radius:2px;position:relative;">
              <div id="progress-fill" style="height:100%;background:var(--accent);border-radius:2px;width:0%;position:absolute;top:0;left:0;"></div>
            </div>
          </div>
          <div class="player-buttons" style="display:flex;align-items:center;gap:12px;padding:8px 16px;">
            <button class="btn btn-secondary btn-sm" id="btn-play" onclick="Player.togglePlay()" title="Play/Pause">▶</button>
            <button class="btn btn-secondary btn-sm" id="btn-stop" onclick="Player.stop()" title="Stop">⏹</button>
            <div class="player-time" id="player-time" style="color:white;font-size:12px;min-width:120px;text-align:center;">--:-- / --:--</div>
            <div style="flex:1;"></div>
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="color:white;font-size:14px;">🔊</span>
              <input type="range" id="volume-slider" min="0" max="100" value="80" onchange="Player.setVolume(this.value)" style="width:80px;">
            </div>
            <button class="btn btn-secondary btn-sm" id="btn-fullscreen" onclick="Player.toggleFullscreen()" title="Fullscreen">⛶</button>
          </div>
          <div class="player-title-bar" style="padding:4px 16px;background:rgba(0,0,0,0.5);display:flex;justify-content:space-between;align-items:center;">
            <span id="player-title" style="color:white;font-size:14px;font-weight:500;">No media selected</span>
            <select id="player-backend-select" onchange="Player.setBackend(this.value)" style="background:var(--bg-tertiary);color:var(--text-primary);border:1px solid var(--border-color);border-radius:4px;padding:4px 8px;font-size:12px;">
              <option value="mpv">MPV</option>
              <option value="vlc">VLC</option>
              <option value="auto">Auto</option>
            </select>
          </div>
        </div>
      </div>
    `;
    this.videoEl = document.getElementById('player-video');
    if (this.videoEl) {
      this.videoEl.addEventListener('timeupdate', () => this.onTimeUpdate());
      this.videoEl.addEventListener('ended', () => this.onEnded());
      this.videoEl.addEventListener('error', (e) => this.onVideoError(e));
      this.videoEl.addEventListener('loadedmetadata', () => this.onMetadataLoaded());
    }
    const progBar = document.getElementById('player-progress-bar');
    if (progBar) {
      progBar.addEventListener('click', (e) => this.seekTo(e));
    }
  },

  async loadMedia(mediaId) {
    this.activeMediaId = mediaId;
    try {
      const res = await fetch(`http://127.0.0.1:${this.backendPort}/api/playback/${mediaId}`);
      const data = await res.json();
      
      document.getElementById('player-title').textContent = data.title || 'Unknown';
      
      const placeholder = document.getElementById('player-placeholder');
      const video = document.getElementById('player-video');
      
      if (placeholder) placeholder.style.display = 'none';
      if (video) video.style.display = 'block';
      
      if (data.files && data.files.length > 0) {
        this.activeFile = data.files[0];
        video.src = data.files[0].file_path;
        
        if (data.progress) {
          video.currentTime = data.progress.position || 0;
        }
        video.play().catch(() => {
          console.log('Autoplay blocked, waiting for user interaction');
        });
        this.startProgressTracking(mediaId);
      } else {
        if (placeholder) {
          placeholder.innerHTML = `<div style="font-size:48px;margin-bottom:16px;">⚠️</div><h3>No playable files found</h3><p style="margin-top:8px;">This item has no associated media files.</p>`;
          placeholder.style.display = 'block';
        }
        if (video) video.style.display = 'none';
      }
    } catch (e) {
      console.error('Failed to load media for playback:', e);
      App.toast('Failed to load media', 'error');
    }
  },

  togglePlay() {
    if (!this.videoEl) return;
    if (this.videoEl.paused) {
      this.videoEl.play().catch(() => {});
    } else {
      this.videoEl.pause();
    }
    this.updatePlayButton();
  },

  stop() {
    if (!this.videoEl) return;
    this.videoEl.pause();
    this.videoEl.currentTime = 0;
    this.stopProgressTracking();
    this.updatePlayButton();
  },

  setVolume(val) {
    if (this.videoEl) {
      this.videoEl.volume = val / 100;
    }
  },

  toggleFullscreen() {
    const container = document.querySelector('.player-container');
    if (!container) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      container.requestFullscreen().catch(() => {});
    }
  },

  setBackend(type) {
    this.playerType = type;
    App.toast(`Player backend: ${type.toUpperCase()}`, 'info');
  },

  seekTo(e) {
    if (!this.videoEl || !this.videoEl.duration) return;
    const bar = e.currentTarget;
    const rect = bar.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    this.videoEl.currentTime = ratio * this.videoEl.duration;
  },

  onTimeUpdate() {
    if (!this.videoEl || !this.videoEl.duration) return;
    const pct = (this.videoEl.currentTime / this.videoEl.duration) * 100;
    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = pct + '%';
    
    const cur = this.formatTime(this.videoEl.currentTime);
    const tot = this.formatTime(this.videoEl.duration);
    const timeEl = document.getElementById('player-time');
    if (timeEl) timeEl.textContent = `${cur} / ${tot}`;
  },

  onMetadataLoaded() {
    if (this.activeMediaId) {
      this.startProgressTracking(this.activeMediaId);
    }
  },

  onEnded() {
    this.stopProgressTracking();
    this.updatePlayButton();
    if (this.activeMediaId) {
      this.saveProgress(this.activeMediaId, this.videoEl?.duration || 0, true);
    }
  },

  onVideoError(e) {
    console.error('Video error:', e);
    App.toast('Video playback error. File may not be accessible.', 'error');
    const placeholder = document.getElementById('player-placeholder');
    if (placeholder) {
      placeholder.innerHTML = `<div style="font-size:48px;margin-bottom:16px;">❌</div><h3>Playback Error</h3><p style="margin-top:8px;">Could not play the selected file.</p>`;
      placeholder.style.display = 'block';
    }
    const video = document.getElementById('player-video');
    if (video) video.style.display = 'none';
  },

  updatePlayButton() {
    const btn = document.getElementById('btn-play');
    if (btn && this.videoEl) {
      btn.textContent = this.videoEl.paused ? '▶' : '⏸';
    }
  },

  startProgressTracking(mediaId) {
    this.stopProgressTracking();
    this._trackingMediaId = mediaId;
    this.playbackInterval = setInterval(() => {
      if (this.videoEl && this.videoEl.duration) {
        this.saveProgress(mediaId, this.videoEl.currentTime, this.videoEl.duration);
      }
    }, 5000);
  },

  stopProgressTracking() {
    if (this.playbackInterval) {
      clearInterval(this.playbackInterval);
      this.playbackInterval = null;
    }
    if (this._trackingMediaId && this.videoEl) {
      this.saveProgress(this._trackingMediaId, this.videoEl.currentTime, this.videoEl.duration);
    }
  },

  async saveProgress(mediaId, position, duration) {
    try {
      await fetch(`http://127.0.0.1:${this.backendPort}/api/playback/${mediaId}/progress`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position, duration })
      });
    } catch (e) {
      console.error('Failed to save progress:', e);
    }
  },

  formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
};

window.Player = Player;
