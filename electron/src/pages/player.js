/**
 * JMDB — Player Page
 * Full-featured media player with real <video> element.
 */
let _playerState = {
  mediaKey: null,
  title: '',
  subtitle: '',
  filePath: null,
  duration: 0,
  position: 0,
  playing: false,
  volume: 70,
  muted: false,
  speed: 1.0,
  fullscreen: false,
  payload: null,
};

let _progressTimer = null;
let _videoEl = null;

async function renderPlayer(params) {
  const payload = params.payload;
  if (!payload || !payload.file_path) {
    AppState.toast('No media file to play', 'error');
    AppState.navigate(AppState._prevPage || 'home');
    return;
  }

  // Remember previous page
  AppState._prevPage = AppState.currentPage;

  const body = document.getElementById('contentBody');
  body.style.padding = '0';
  body.style.overflow = 'hidden';

  // Get existing progress
  let resumePos = 0;
  try {
    const pr = await API.get(`/api/playback/${payload.media_key}`);
    resumePos = pr?.progress?.position_s || 0;
  } catch {}

  _playerState = {
    ..._playerState,
    mediaKey: payload.media_key,
    title: payload.title || 'Unknown',
    subtitle: payload.subtitle || '',
    filePath: payload.file_path,
    duration: payload.duration_s || 0,
    position: resumePos,
    payload,
  };

  body.innerHTML = `
    <div class="player-container" id="playerContainer">
      <div class="player-video" id="playerVideo">
        <video id="playerVideoEl" src="${esc(payload.file_path)}" playsinline></video>
        <div class="player-overlay" id="playerOverlay">
          <div class="player-top-bar">
            <button class="player-back" onclick="playerClose()">◀ Back</button>
            <div>
              <div class="player-title">${esc(_playerState.title)}</div>
              <div class="player-subtitle">${esc(_playerState.subtitle)}</div>
            </div>
          </div>
          <div class="player-controls">
            <div class="player-progress" id="playerProgress" onclick="playerSeek(event)">
              <div class="player-progress-fill" id="playerProgressFill" style="width:${_playerState.duration ? (_playerState.position/_playerState.duration*100) : 0}%"></div>
            </div>
            <div class="player-buttons">
              <button class="player-btn" onclick="playerSkip(-10)" title="Rewind 10s">⏪</button>
              <button class="player-btn" id="playerPlayBtn" onclick="playerToggle()" title="Play/Pause (Space)">▶</button>
              <button class="player-btn" onclick="playerSkip(10)" title="Forward 10s">⏩</button>
              <span class="player-time" id="playerTime">${clock(_playerState.position)} / ${clock(_playerState.duration)}</span>
              <div style="flex:1;"></div>
              <button class="player-btn" onclick="playerPrev()" title="Previous (P)">⏮</button>
              <button class="player-btn" onclick="playerNext()" title="Next (N)">⏭</button>
              <div class="player-volume">
                <button class="player-btn" id="playerMuteBtn" onclick="playerMuteToggle()" title="Mute (M)">🔊</button>
                <input type="range" class="player-slider" id="playerVolumeSlider" min="0" max="100" value="${_playerState.volume}" oninput="playerSetVolume(this.value)">
              </div>
              <select class="settings-select" id="playerSpeedSelect" onchange="playerSetSpeed(parseFloat(this.value))" style="background:rgba(255,255,255,0.1);color:white;border-color:rgba(255,255,255,0.2);">
                <option value="0.5">0.5x</option>
                <option value="0.75">0.75x</option>
                <option value="1" selected>1x</option>
                <option value="1.25">1.25x</option>
                <option value="1.5">1.5x</option>
                <option value="2">2x</option>
                <option value="3">3x</option>
              </select>
              <button class="player-btn" id="playerFsBtn" onclick="playerToggleFullscreen()" title="Fullscreen (F)">⛶</button>
            </div>
          </div>
        </div>
        ${resumePos > 30 ? `<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,0.8);padding:16px 24px;border-radius:12px;display:flex;gap:12px;align-items:center;" id="resumeBanner">
          <span style="color:white;font-size:14px;">Resumed at ${clock(resumePos)}</span>
          <button class="btn btn-sm btn-accent" onclick="playerSeekTo(${resumePos});this.parentElement.remove();">Resume</button>
          <button class="btn btn-sm" onclick="playerSeekTo(0);this.parentElement.remove();">Start Over</button>
        </div>` : ''}
      </div>
    </div>`;

  body.classList.remove('hidden');
  document.getElementById('contentLoading').classList.add('hidden');

  _videoEl = document.getElementById('playerVideoEl');

  // Report playback start
  jmdb.playbackStart({
    media_key: _playerState.mediaKey,
    title: _playerState.title,
    subtitle: _playerState.subtitle,
    file_path: _playerState.filePath,
    duration_s: _playerState.duration,
    media_id: _playerState.payload?.media_id,
    episode_id: _playerState.payload?.episode_id,
    show_id: _playerState.payload?.show_id,
    season: _playerState.payload?.season,
    number: _playerState.payload?.number,
  }).catch(() => {});

  // Resume position
  if (resumePos > 0) {
    _videoEl.currentTime = resumePos;
  }

  // Video events
  _videoEl.addEventListener('timeupdate', () => {
    _playerState.position = _videoEl.currentTime;
    _playerState.duration = _videoEl.duration || _playerState.duration;
    updatePlayerUI();
    // Throttled progress save
    if (Math.floor(_playerState.position) % 5 === 0) {
      jmdb.playbackProgress(_playerState.position, _playerState.duration).catch(() => {});
    }
  });

  _videoEl.addEventListener('play', () => {
    _playerState.playing = true;
    document.getElementById('playerPlayBtn').textContent = '⏸';
    startProgressTimer();
  });

  _videoEl.addEventListener('pause', () => {
    _playerState.playing = false;
    document.getElementById('playerPlayBtn').textContent = '▶';
    stopProgressTimer();
    jmdb.playbackProgress(_playerState.position, _playerState.duration).catch(() => {});
  });

  _videoEl.addEventListener('ended', async () => {
    stopProgressTimer();
    await jmdb.playbackFinish();
    playerClose();
  });

  _videoEl.addEventListener('error', () => {
    AppState.toast('Playback error — file may be unavailable or codec not supported.', 'error');
  });

  // Start playback
  _videoEl.play().catch(() => {});

  // Keyboard shortcuts
  document.addEventListener('keydown', playerKeyHandler);
}

function playerKeyHandler(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  switch(e.key) {
    case ' ': e.preventDefault(); playerToggle(); break;
    case 'ArrowRight': e.preventDefault(); playerSkip(10); break;
    case 'ArrowLeft': e.preventDefault(); playerSkip(-10); break;
    case 'ArrowUp': e.preventDefault(); playerSetVolume(Math.min(100, _playerState.volume + 5)); break;
    case 'ArrowDown': e.preventDefault(); playerSetVolume(Math.max(0, _playerState.volume - 5)); break;
    case 'm': case 'M': playerMuteToggle(); break;
    case 'f': case 'F': playerToggleFullscreen(); break;
    case 'Escape': playerClose(); break;
    case 'n': case 'N': playerNext(); break;
    case 'p': case 'P': playerPrev(); break;
  }
}

function updatePlayerUI() {
  const fill = document.getElementById('playerProgressFill');
  const time = document.getElementById('playerTime');
  if (fill) fill.style.width = (_playerState.duration ? (_playerState.position / _playerState.duration * 100) : 0) + '%';
  if (time) time.textContent = `${clock(_playerState.position)} / ${clock(_playerState.duration)}`;
}

function playerToggle() {
  if (!_videoEl) return;
  if (_videoEl.paused) _videoEl.play().catch(()=>{});
  else _videoEl.pause();
}

function playerSkip(seconds) {
  if (!_videoEl) return;
  _videoEl.currentTime = Math.max(0, Math.min(_videoEl.duration || 0, _videoEl.currentTime + seconds));
}

function playerSeek(e) {
  if (!_videoEl || !_videoEl.duration) return;
  const rect = e.currentTarget.getBoundingClientRect();
  const pct = (e.clientX - rect.left) / rect.width;
  _videoEl.currentTime = pct * _videoEl.duration;
}

function playerSeekTo(pos) {
  if (!_videoEl) return;
  _videoEl.currentTime = pos;
  if (_videoEl.paused) _videoEl.play().catch(()=>{});
}

function playerSetVolume(val) {
  val = parseInt(val);
  _playerState.volume = val;
  _playerState.muted = val === 0;
  if (_videoEl) { _videoEl.volume = val / 100; _videoEl.muted = val === 0; }
  const btn = document.getElementById('playerMuteBtn');
  if (btn) btn.textContent = val === 0 ? '🔇' : val < 50 ? '🔉' : '🔊';
  const slider = document.getElementById('playerVolumeSlider');
  if (slider) slider.value = val;
}

function playerMuteToggle() {
  _playerState.muted = !_playerState.muted;
  if (_videoEl) _videoEl.muted = _playerState.muted;
  const btn = document.getElementById('playerMuteBtn');
  if (btn) btn.textContent = _playerState.muted ? '🔇' : '🔊';
}

function playerSetSpeed(speed) {
  _playerState.speed = speed;
  if (_videoEl) _videoEl.playbackRate = speed;
}

function playerToggleFullscreen() {
  const container = document.getElementById('playerContainer');
  if (!container) return;
  _playerState.fullscreen = !_playerState.fullscreen;
  const btn = document.getElementById('playerFsBtn');
  if (_playerState.fullscreen) {
    if (container.requestFullscreen) container.requestFullscreen();
    if (btn) btn.textContent = '⛶';
  } else {
    if (document.exitFullscreen) document.exitFullscreen();
    if (btn) btn.textContent = '⛶';
  }
}

function playerPrev() {
  playerSkip(-30);
}

function playerNext() {
  // Trigger backend next-episode logic
  jmdb.playbackFinish().then(r => {
    if (r?.data?.next_payload) {
      renderPlayer({ payload: r.data.next_payload });
    }
  }).catch(() => playerClose());
}

function startProgressTimer() {
  stopProgressTimer();
  _progressTimer = setInterval(() => {
    if (_playerState.playing && _videoEl) {
      jmdb.playbackProgress(_videoEl.currentTime, _videoEl.duration || _playerState.duration).catch(() => {});
    }
  }, 5000);
}

function stopProgressTimer() {
  if (_progressTimer) { clearInterval(_progressTimer); _progressTimer = null; }
}

function playerClose() {
  stopProgressTimer();
  document.removeEventListener('keydown', playerKeyHandler);
  if (_videoEl) { _videoEl.pause(); _videoEl.src = ''; }

  // Save final position
  jmdb.playbackStop(_playerState.position, _playerState.duration).catch(() => {});

  // Restore content area
  const body = document.getElementById('contentBody');
  body.style.padding = '';
  body.style.overflow = '';
  body.innerHTML = '';

  // Go back to previous page
  const prev = AppState._prevPage || 'home';
  AppState.navigate(prev);
}

function clock(seconds) {
  seconds = Math.max(0, Math.floor(seconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
  return `${m}:${s.toString().padStart(2,'0')}`;
}
