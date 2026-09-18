const Player = {
  activeMediaId: null,
  activeFile: null,
  backendPort: 8765,
  playerType: 'mpv',
  playbackInterval: null,
  eventCleanup: null,
  initialized: false,
  duration: 0,
  position: 0,
  paused: true,
  volume: 80,
  speed: 1,

  init(container) {
    container.innerHTML = `
      <div class="player-container" style="height:100%;display:flex;flex-direction:column;background:#000;">
        <div id="player-video-area" style="flex:1;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;">
          <div id="player-placeholder" style="text-align:center;color:var(--text-muted);">
            <div style="font-size:72px;margin-bottom:16px;">▶</div>
            <h2>Select a media item to play</h2>
            <p style="margin-top:8px;font-size:14px;">Navigate to Library and choose a movie or show</p>
          </div>

          <div id="player-mpv-status" style="display:none;text-align:center;color:var(--text-muted);">
            <div style="font-size:56px;margin-bottom:16px;">▶</div>
            <h2>MPV Player</h2>
            <p id="player-mpv-status-text" style="margin-top:8px;font-size:14px;">Starting...</p>
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

            <div class="player-time" id="player-time" style="color:white;font-size:12px;min-width:120px;text-align:center;">
              --:-- / --:--
            </div>

            <div style="flex:1;"></div>

            <div style="display:flex;align-items:center;gap:8px;">
              <span style="color:white;font-size:14px;">🔊</span>
              <input
                type="range"
                id="volume-slider"
                min="0"
                max="100"
                value="80"
                onchange="Player.setVolume(this.value)"
                style="width:80px;"
              >
            </div>

            <button
              class="btn btn-secondary btn-sm"
              id="btn-fullscreen"
              onclick="Player.toggleFullscreen()"
              title="Fullscreen"
            >⛶</button>
          </div>

          <div class="player-title-bar" style="padding:4px 16px;background:rgba(0,0,0,0.5);display:flex;justify-content:space-between;align-items:center;">
            <span id="player-title" style="color:white;font-size:14px;font-weight:500;">
              No media selected
            </span>

            <select
              id="player-backend-select"
              onchange="Player.setBackend(this.value)"
              style="background:var(--bg-tertiary);color:var(--text-primary);border:1px solid var(--border-color);border-radius:4px;padding:4px 8px;font-size:12px;"
            >
              <option value="mpv">MPV</option>
              <option value="vlc">VLC</option>
              <option value="auto">Auto</option>
            </select>
          </div>
        </div>
      </div>
    `;

    const progBar = document.getElementById('player-progress-bar');

    if (progBar) {
      progBar.addEventListener('click', (event) => {
        this.seekTo(event);
      });
    }

    if (window.jmdb?.player?.onEvent) {
      if (this.eventCleanup) {
        this.eventCleanup();
      }

      this.eventCleanup = window.jmdb.player.onEvent((message) => {
        this.handleMpvEvent(message);
      });
    }

    this.initialized = true;
    this.updatePlayButton();
  },

  async loadMedia(mediaId) {
    if (!window.jmdb?.player) {
      App.toast('Player IPC is not available', 'error');
      return;
    }

    this.activeMediaId = mediaId;
    this.stopProgressTracking();

    try {
      const res = await fetch(
        `http://127.0.0.1:${this.backendPort}/api/playback/${mediaId}`
      );

      if (!res.ok) {
        throw new Error(`Playback API returned HTTP ${res.status}`);
      }

      const data = await res.json();

      const titleEl = document.getElementById('player-title');
      if (titleEl) {
        titleEl.textContent = data.title || 'Unknown';
      }

      if (!data.files || data.files.length === 0) {
        this.showPlaceholder(
          '⚠️',
          'No playable files found',
          'This item has no associated media files.'
        );
        return;
      }

      this.activeFile = data.files[0];

      const position =
        data.progress && Number.isFinite(Number(data.progress.position))
          ? Number(data.progress.position)
          : 0;

      const settings = await this.getPlayerSettings();

      const backend =
        settings.default_player ||
        this.playerType ||
        'mpv';

      this.playerType = backend;

      if (backend === 'vlc') {
        App.toast('VLC backend is not connected yet; using MPV.', 'info');
      }

      const mpvPath = settings.mpv_path || '/usr/bin/mpv';

      this.showMpvStatus('Starting MPV...');

      const result = await window.jmdb.player.start(
        this.activeFile.file_path,
        {
          mpvPath
        }
      );

      console.log('[JMDB Player] MPV started:', result);

      this.duration = 0;
      this.position = position;
      this.paused = true;

      await this.observeProperties();

      if (position > 0) {
        await window.jmdb.player.setProperty(
          'time-pos',
          position
        );
      }

      await window.jmdb.player.setProperty(
        'volume',
        this.volume
      );

      await window.jmdb.player.setProperty(
        'pause',
        false
      );

      this.paused = false;

      this.hideMpvStatus();
      this.updatePlayButton();

      this.startProgressTracking(mediaId);
      await this.refreshState();

    } catch (error) {
      console.error(
        '[JMDB Player] Failed to start playback:',
        error
      );

      this.showPlaceholder(
        '❌',
        'Playback Error',
        error.message || 'Could not start MPV.'
      );

      App.toast(
        `Playback failed: ${error.message || 'unknown error'}`,
        'error'
      );
    }
  },

  async getPlayerSettings() {
    try {
      const res = await fetch(
        `http://127.0.0.1:${this.backendPort}/api/settings`
      );

      if (!res.ok) {
        return {};
      }

      const data = await res.json();

      return data || {};
    } catch (error) {
      console.warn(
        '[JMDB Player] Could not load player settings:',
        error
      );

      return {};
    }
  },

  async observeProperties() {
    try {
      await window.jmdb.player.observeProperty(
        'time-pos',
        1
      );

      await window.jmdb.player.observeProperty(
        'duration',
        2
      );

      await window.jmdb.player.observeProperty(
        'pause',
        3
      );

      await window.jmdb.player.observeProperty(
        'volume',
        4
      );

      await window.jmdb.player.observeProperty(
        'speed',
        5
      );
    } catch (error) {
      console.warn(
        '[JMDB Player] Property observation setup failed:',
        error
      );
    }
  },

  handleMpvEvent(message) {
    if (!message) {
      return;
    }

    if (message.event === 'property-change') {
      this.handlePropertyChange(message);
      return;
    }

    if (message.event === 'end-file') {
      this.handleEndFile(message);
      return;
    }

    if (message.event === 'start-file') {
      this.showMpvStatus('Loading media...');
      return;
    }

    if (message.event === 'file-loaded') {
      this.hideMpvStatus();
      return;
    }
  },

  handlePropertyChange(message) {
    switch (message.name) {
      case 'time-pos':
        if (Number.isFinite(Number(message.data))) {
          this.position = Number(message.data);
          this.updateProgressUI();
        }
        break;

      case 'duration':
        if (Number.isFinite(Number(message.data))) {
          this.duration = Number(message.data);
          this.updateProgressUI();
        }
        break;

      case 'pause':
        this.paused = Boolean(message.data);
        this.updatePlayButton();
        break;

      case 'volume':
        if (Number.isFinite(Number(message.data))) {
          this.volume = Number(message.data);

          const slider = document.getElementById(
            'volume-slider'
          );

          if (slider) {
            slider.value = String(this.volume);
          }
        }
        break;

      case 'speed':
        if (Number.isFinite(Number(message.data))) {
          this.speed = Number(message.data);
        }
        break;
    }
  },

  async handleEndFile(message) {
    this.stopProgressTracking();

    const reason = message.reason || 'unknown';

    if (reason === 'eof') {
      await this.saveProgress(
        this.activeMediaId,
        this.duration,
        this.duration,
        true
      );
    }

    this.paused = true;
    this.updatePlayButton();

    console.log(
      '[JMDB Player] MPV end-file:',
      reason
    );
  },

  async togglePlay() {
    if (!window.jmdb?.player) {
      return;
    }

    try {
      await window.jmdb.player.command([
        'cycle',
        'pause'
      ]);
    } catch (error) {
      console.error(
        '[JMDB Player] Toggle play failed:',
        error
      );
    }
  },

  async stop() {
    if (!window.jmdb?.player) {
      return;
    }

    try {
      await this.saveCurrentProgress();

      await window.jmdb.player.stop();

      this.stopProgressTracking();

      this.activeFile = null;
      this.duration = 0;
      this.position = 0;
      this.paused = true;

      this.showPlaceholder(
        '▶',
        'Select a media item to play',
        'Navigate to Library and choose a movie or show'
      );

      this.updateProgressUI();
      this.updatePlayButton();

    } catch (error) {
      console.error(
        '[JMDB Player] Stop failed:',
        error
      );

      App.toast(
        `Stop failed: ${error.message}`,
        'error'
      );
    }
  },

  async setVolume(value) {
    const volume = Math.max(
      0,
      Math.min(100, Number(value) || 0)
    );

    this.volume = volume;

    try {
      await window.jmdb.player.setProperty(
        'volume',
        volume
      );
    } catch (error) {
      console.error(
        '[JMDB Player] Volume change failed:',
        error
      );
    }
  },

  async setSpeed(value) {
    const speed = Number(value);

    if (!Number.isFinite(speed) || speed <= 0) {
      return;
    }

    this.speed = speed;

    try {
      await window.jmdb.player.setProperty(
        'speed',
        speed
      );
    } catch (error) {
      console.error(
        '[JMDB Player] Speed change failed:',
        error
      );
    }
  },

  async toggleFullscreen() {
    try {
      const status = await window.jmdb.player.status();

      if (!status.running) {
        return;
      }

      await window.jmdb.player.command([
        'cycle',
        'fullscreen'
      ]);
    } catch (error) {
      console.error(
        '[JMDB Player] Fullscreen failed:',
        error
      );
    }
  },

  setBackend(type) {
    this.playerType = type;

    if (type === 'mpv') {
      App.toast('Player backend: MPV', 'info');
      return;
    }

    if (type === 'vlc') {
      App.toast(
        'VLC backend is not connected yet.',
        'info'
      );
      return;
    }

    App.toast(
      'Auto backend currently selects MPV.',
      'info'
    );
  },

  async seekTo(event) {
    if (!this.duration) {
      return;
    }

    const bar = event.currentTarget;
    const rect = bar.getBoundingClientRect();

    if (!rect.width) {
      return;
    }

    const ratio = Math.max(
      0,
      Math.min(
        1,
        (event.clientX - rect.left) / rect.width
      )
    );

    const position = ratio * this.duration;

    try {
      await window.jmdb.player.setProperty(
        'time-pos',
        position
      );

      this.position = position;
      this.updateProgressUI();
    } catch (error) {
      console.error(
        '[JMDB Player] Seek failed:',
        error
      );
    }
  },

  async refreshState() {
    if (!window.jmdb?.player) {
      return;
    }

    const properties = [
      ['time-pos', 'position'],
      ['duration', 'duration'],
      ['pause', 'paused'],
      ['volume', 'volume'],
      ['speed', 'speed']
    ];

    for (const [property, stateKey] of properties) {
      try {
        const result =
          await window.jmdb.player.getProperty(property);

        if (!result) {
          continue;
        }

        if (stateKey === 'position') {
          const value = Number(result.data);
          if (Number.isFinite(value)) {
            this.position = value;
          }
        } else if (stateKey === 'duration') {
          const value = Number(result.data);
          if (Number.isFinite(value)) {
            this.duration = value;
          }
        } else if (stateKey === 'paused') {
          this.paused = Boolean(result.data);
        } else if (stateKey === 'volume') {
          const value = Number(result.data);
          if (Number.isFinite(value)) {
            this.volume = value;
          }
        } else if (stateKey === 'speed') {
          const value = Number(result.data);
          if (Number.isFinite(value)) {
            this.speed = value;
          }
        }
      } catch (error) {
        console.debug(
          `[JMDB Player] MPV property unavailable during refresh: ${property}`,
          error?.message || error
        );
      }
    }

    const slider = document.getElementById(
      'volume-slider'
    );

    if (slider) {
      slider.value = String(this.volume);
    }

    this.updateProgressUI();
    this.updatePlayButton();
  },

  updateProgressUI() {
    const pct =
      this.duration > 0
        ? Math.max(
            0,
            Math.min(
              100,
              (this.position / this.duration) * 100
            )
          )
        : 0;

    const fill = document.getElementById(
      'progress-fill'
    );

    if (fill) {
      fill.style.width = `${pct}%`;
    }

    const timeEl = document.getElementById(
      'player-time'
    );

    if (timeEl) {
      timeEl.textContent =
        `${this.formatTime(this.position)} / ${this.formatTime(this.duration)}`;
    }
  },

  updatePlayButton() {
    const btn = document.getElementById(
      'btn-play'
    );

    if (btn) {
      btn.textContent = this.paused ? '▶' : '⏸';
    }
  },

  startProgressTracking(mediaId) {
    this.stopProgressTracking();

    this._trackingMediaId = mediaId;

    this.playbackInterval = setInterval(
      () => {
        this.saveCurrentProgress();
      },
      5000
    );
  },

  stopProgressTracking() {
    if (this.playbackInterval) {
      clearInterval(this.playbackInterval);
      this.playbackInterval = null;
    }

    if (
      this._trackingMediaId &&
      this.position >= 0
    ) {
      this.saveCurrentProgress();
    }
  },

  async saveCurrentProgress() {
    if (!this._trackingMediaId) {
      return;
    }

    await this.saveProgress(
      this._trackingMediaId,
      this.position,
      this.duration,
      false
    );
  },

  async saveProgress(
    mediaId,
    position,
    duration,
    completed = false
  ) {
    if (!mediaId) {
      return;
    }

    try {
      await fetch(
        `http://127.0.0.1:${this.backendPort}/api/playback/${mediaId}/progress`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            position: Number(position) || 0,
            duration: Number(duration) || 0,
            completed: Boolean(completed)
          })
        }
      );
    } catch (error) {
      console.error(
        '[JMDB Player] Failed to save progress:',
        error
      );
    }
  },

  async showPlaceholder(icon, title, text) {
    const placeholder = document.getElementById(
      'player-placeholder'
    );

    if (!placeholder) {
      return;
    }

    placeholder.innerHTML = `
      <div style="font-size:48px;margin-bottom:16px;">${icon}</div>
      <h3>${title}</h3>
      <p style="margin-top:8px;font-size:14px;">${text}</p>
    `;

    placeholder.style.display = 'block';

    const status = document.getElementById(
      'player-mpv-status'
    );

    if (status) {
      status.style.display = 'none';
    }
  },

  showMpvStatus(text) {
    const placeholder = document.getElementById(
      'player-placeholder'
    );

    const status = document.getElementById(
      'player-mpv-status'
    );

    const statusText = document.getElementById(
      'player-mpv-status-text'
    );

    if (placeholder) {
      placeholder.style.display = 'none';
    }

    if (status) {
      status.style.display = 'block';
    }

    if (statusText) {
      statusText.textContent = text;
    }
  },

  hideMpvStatus() {
    const status = document.getElementById(
      'player-mpv-status'
    );

    if (status) {
      status.style.display = 'none';
    }

    const placeholder = document.getElementById(
      'player-placeholder'
    );

    if (placeholder && this.activeFile) {
      placeholder.style.display = 'none';
    }
  },

  formatTime(seconds) {
    if (
      seconds === null ||
      seconds === undefined ||
      !Number.isFinite(Number(seconds)) ||
      Number(seconds) < 0
    ) {
      return '--:--';
    }

    const total = Math.floor(Number(seconds));

    const hours = Math.floor(total / 3600);
    const minutes = Math.floor(
      (total % 3600) / 60
    );
    const secs = total % 60;

    if (hours > 0) {
      return `${hours}:${minutes
        .toString()
        .padStart(2, '0')}:${secs
        .toString()
        .padStart(2, '0')}`;
    }

    return `${minutes}:${secs
      .toString()
      .padStart(2, '0')}`;
  }
};

window.Player = Player;
