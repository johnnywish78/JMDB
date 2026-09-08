/** Full-featured media player overlay.
 *
 * Real controls only: play/pause, seek bar with buffered indicator, volume +
 * mute, speed, subtitles (external srt/vtt served by the backend), PiP,
 * fullscreen, prev/next in queue, restart, resume prompt, autoplay-next,
 * keyboard shortcuts, auto-hiding chrome. Progress is reported to the Python
 * backend, which owns resume/watched/next-episode decisions.
 */
import { api, artUrl } from "./api.js";
import { el, formatClock, icon, toast } from "./ui.js";
import { navigate } from "./router.js";
import { store } from "./store.js";

const IDLE_TIMEOUT = 2800;

let active = null; // current player instance

export async function openPlayer({ mediaType, mediaId, context = null, startAt = null }) {
  if (active) active.close(true);
  let data;
  try {
    data = await api.post("/api/playback/start", { media_type: mediaType, media_id: mediaId, context });
  } catch (error) {
    toast(`Playback failed: ${error.message || error}`, "error");
    return;
  }
  // engine choice: mpv (multi-codec, VLC-style) when the desktop bridge and
  // the binary are available; the built-in Chromium player otherwise
  const { engine, bridge } = await resolveEngine();
  if (engine === "mpv") {
    const handoff = new MpvHandoff(data, bridge, { requestedStart: startAt });
    const started = await handoff.start();
    if (started) {
      active = handoff;
      return handoff;
    }
    // the engine refused honestly (mpv missing, no X window, bad file) —
    // fall through to the built-in player
  }
  active = new Player(data, { requestedStart: startAt });
  active.open();
  return active;
}

/** Decide the playback engine for this run. Pure bridge detection — never
 * assumes mpv exists; "chromium" is always the honest fallback. */
async function resolveEngine() {
  const bridge = window.jmdb && window.jmdb.mpv ? window.jmdb.mpv : null;
  if (!bridge) return { engine: "chromium", bridge: null };
  const setting = String(store.settings.player_engine || "auto");
  if (setting === "chromium") return { engine: "chromium", bridge };
  try {
    const status = await bridge.status();
    if (status && status.available) return { engine: "mpv", bridge, status };
    if (setting === "mpv") {
      toast(`mpv engine unavailable: ${status?.reason || "not installed"} — using the built-in player`, "error");
    }
    return { engine: "chromium", bridge };
  } catch {
    return { engine: "chromium", bridge };
  }
}

/** mpv-engine handoff: the real decoding lives in the main process (mpv
 * embedded in the window, controls in a native overlay). This class owns the
 * renderer side — session data, queue moves, and honest fallback. */
class MpvHandoff {
  constructor(data, bridge, { requestedStart = null } = {}) {
    this.data = data;
    this.bridge = bridge;
    this.media = data.media;
    this.sessionId = data.session_id;
    this.requestedStart = requestedStart;
    this.closed = false;
    this.offs = [];
    this.root = null;
  }

  get seekStep() {
    const step = Number(store.settings.seek_step_seconds);
    return Number.isFinite(step) && step > 0 && step <= 120 ? step : 10;
  }
  get volumeStep() {
    const step = Number(store.settings.volume_step);
    return Number.isFinite(step) && step > 0 && step <= 50 ? step : 5;
  }

  async start() {
    const file = this.media.file || {};
    const payload = {
      path: file.path || "",
      fileExists: file.exists !== false,
      url: this.data.stream_url,
      start: this.requestedStart ?? this.data.position ?? 0,
      duration: this.data.duration_hint || 0,
      volume: Number(store.settings.player_default_volume ?? 90),
      title: this.media.subtitle ? `${this.media.title} — ${this.media.subtitle}` : this.media.title,
      sessionId: this.sessionId,
      mediaType: this.media.type,
      mediaId: this.media.id,
      subtitles: (this.data.subtitles || []).filter((s) => s.path),
      subtitleLanguage: String(store.settings.default_subtitle_language || ""),
      queue: this.data.queue || [],
      autoplayNext: Boolean(this.data.autoplay_next),
      seekStep: this.seekStep,
      volumeStep: this.volumeStep,
    };
    let result;
    try {
      result = await this.bridge.open(payload);
    } catch (error) {
      result = { ok: false, error: error.message || String(error) };
    }
    if (!result || !result.ok) {
      toast(`mpv engine: ${(result && result.error) || "could not start"} — using the built-in player`, "error");
      return false;
    }

    document.body.classList.add("player-open");
    this.root = el("div", { class: "player mpv-mode" },
      el("div", { class: "mpv-backing" },
        el("h3", {}, this.media.title),
        el("p", {}, "Playing through the embedded mpv engine (multi-codec)."),
        el("p", { class: "hint" }, "Controls are on the video — move the mouse. Esc returns here.")));
    const mount = document.getElementById("player-root") || document.body;
    mount.append(this.root);

    this.offs.push(window.jmdb.on("mpv:closed", () => this.close(true)));
    this.offs.push(window.jmdb.on("mpv:next", (next) => this.queueMove(next)));
    this.offs.push(window.jmdb.on("mpv:prev", (next) => this.queueMove(next)));
    return true;
  }

  queueMove(next) {
    if (!next || !next.mediaType || !next.mediaId) return;
    this.close(true);
    openPlayer({ mediaType: next.mediaType, mediaId: next.mediaId, context: this.data.context || null, startAt: 0 });
  }

  close(skipReport = true) {
    if (this.closed) return;
    this.closed = true;
    for (const off of this.offs) off();
    this.offs = [];
    document.body.classList.remove("player-open");
    this.root?.remove();
    this.root = null;
    // idempotent: the engine may already be down (this close often runs
    // BECAUSE the engine told us it closed)
    this.bridge.close().catch(() => {});
    if (active === this) active = null;
    navigate(currentHashForRefresh());
  }
}

/** Small artwork thumbnail that hides itself when the image fails to load
 * (CSP forbids inline onerror handlers, so we use a real listener). */
function posterThumb(path, cls) {
  const img = el("img", { class: cls, alt: "", loading: "lazy", src: artUrl(path, "poster") });
  img.addEventListener("error", () => { img.style.display = "none"; });
  return img;
}

class Player {
  constructor(data, { requestedStart = null } = {}) {
    this.data = data;
    this.media = data.media;
    this.position = requestedStart ?? data.position ?? 0;
    this.lastReported = -1;
    this.reportTimer = null;
    this.idleTimer = null;
    this.closed = false;
    this.rate = 1;
    this.subtitle = null;
    this.subtitleDelay = 0;
    this.failed = false;
    this.sessionId = data.session_id;
    this.lastDirection = 1;
  }

  /* codec facts from the backend's ffprobe, for honest UI decisions */
  get fileCodec() { return this.media.file?.video_codec || ""; }
  get audioStreamCount() { return (this.media.file?.audio_tracks || []).length; }
  get seekStep() {
    const step = Number(store.settings.seek_step_seconds);
    return Number.isFinite(step) && step > 0 && step <= 120 ? step : 10;
  }
  get volumeStep() {
    const step = Number(store.settings.volume_step);
    return Number.isFinite(step) && step > 0 && step <= 50 ? step / 100 : 0.05;
  }

  open() {
    document.body.classList.add("player-open");
    this.root = el("div", { class: "player" });
    this.video = el("video", {
      src: this.data.stream_url,
      autoplay: "autoplay",
      preload: "metadata",
    });
    // default volume from the persisted player_default_volume setting
    // (store.settings mirrors /api/settings), kept per session in localStorage
    const stored = Number(localStorage.getItem("jmdb.volume"));
    const defaultVolume = Number(store.settings.player_default_volume ?? 90);
    this.video.volume = Number.isFinite(stored) && stored >= 0 && stored <= 1
      ? stored
      : Math.min(1, Math.max(0, (Number.isFinite(defaultVolume) ? defaultVolume : 90) / 100));
    this.video.muted = localStorage.getItem("jmdb.muted") === "1";
    this.buildChrome();
    this.root.append(this.video);
    document.getElementById("player-root").append(this.root);

    this.video.addEventListener("loadedmetadata", () => {
      if (this.position > 1 && this.position < (this.video.duration || Infinity) - 2) {
        this.showResumePrompt();
      }
    });
    // Some Chromium builds demux an MKV fine but can't decode the video codec
    // (e.g. HEVC without hardware support): audio plays over a BLACK screen
    // and NO error event fires. The decode monitor catches that silent case.
    // (videoWidth can legitimately stay 0 until the first frame decodes, so
    // only SUSTAINED playback without any frame counts as a failure.)
    this.startDecodeMonitor();
    document.addEventListener("fullscreenchange", this.onFullscreenChange = () => {
      if (this.fullscreenButton) {
        this.fullscreenButton.classList.toggle("active", Boolean(document.fullscreenElement));
      }
    });
    this.autoSelectSubtitle();
    this.video.addEventListener("timeupdate", () => this.onTimeUpdate());
    this.video.addEventListener("progress", () => this.updateBuffer());
    this.video.addEventListener("play", () => this.setPlaying(true));
    this.video.addEventListener("pause", () => {
      this.setPlaying(false);
      this.report(true);
    });
    this.video.addEventListener("ended", () => this.onEnded());
    this.video.addEventListener("error", () => this.onVideoError());
    this.video.addEventListener("volumechange", () => {
      localStorage.setItem("jmdb.volume", String(this.video.volume));
      localStorage.setItem("jmdb.muted", this.video.muted ? "1" : "0");
    });

    // keyboard + mouse
    this.keyHandler = (event) => this.onKey(event);
    document.addEventListener("keydown", this.keyHandler);
    this.root.addEventListener("mousemove", () => this.wake());
    this.root.addEventListener("mouseleave", () => this.setIdle());
    this.video.addEventListener("click", () => this.togglePlay());
    this.video.addEventListener("dblclick", () => this.toggleFullscreen());
    this.wake();

    this.reportTimer = setInterval(() => this.report(false), 5000);
    window.addEventListener("beforeunload", () => this.report(true));
  }

  /* ------------------------------------------------------------- chrome */
  buildChrome() {
    const queueButton = el("button", { class: "pbtn", title: "Queue" });
    queueButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h10M4 18h7"/><path d="M18 15v6M15 18h6"/></svg>`;
    queueButton.addEventListener("click", () => this.toggleQueue());

    const settingsButton = el("button", { class: "pbtn", title: "Settings" });
    settingsButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .33 1.76l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.6 1.6 0 0 0-1.76-.33 1.6 1.6 0 0 0-1 1.47V21a2 2 0 1 1-4 0v-.09a1.6 1.6 0 0 0-1-1.47 1.6 1.6 0 0 0-1.77.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.6 1.6 0 0 0 .33-1.77 1.6 1.6 0 0 0-1.47-1H3a2 2 0 1 1 0-4h.09a1.6 1.6 0 0 0 1.47-1 1.6 1.6 0 0 0-.33-1.77l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.6 1.6 0 0 0 1.76.33h.01a1.6 1.6 0 0 0 1-1.47V3a2 2 0 1 1 4 0v.09a1.6 1.6 0 0 0 1 1.47h.01a1.6 1.6 0 0 0 1.76-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.6 1.6 0 0 0-.33 1.76v.01a1.6 1.6 0 0 0 1.47 1H21a2 2 0 1 1 0 4h-.09a1.6 1.6 0 0 0-1.47 1z"/></svg>`;
    settingsButton.addEventListener("click", () => this.toggleSettings());

    this.top = el("div", { class: "player-top" },
      el("button", { class: "pbtn", title: "Back (Esc)", "aria-label": "Back", onclick: () => this.close() }, icon("chevron-left")),
      this.media.artwork_path ? posterThumb(this.media.artwork_path, "artwork") : null,
      el("div", {},
        el("div", { class: "title" }, this.media.title || "Untitled"),
        el("div", { class: "subtitle" }, this.media.subtitle || this.media.file?.name || "")),
      el("div", { class: "spacer" }),
      queueButton,
      settingsButton,
      el("button", { class: "pbtn", title: "Open externally", onclick: () => this.playExternal() }, icon("external")));

    // seek
    this.playedBar = el("span", { class: "played" });
    this.bufferBar = el("span", { class: "buffer" });
    this.seekThumb = el("span", { class: "thumb" });
    this.seekTrack = el("div", { class: "track" }, this.bufferBar, this.playedBar);
    this.seekBar = el("div", { class: "seek-bar", tabindex: "0" }, this.seekTrack, this.seekThumb);
    this.seekBar.addEventListener("pointerdown", (event) => this.startScrub(event));
    this.seekBar.addEventListener("keydown", (event) => {
      const step = this.video.duration ? this.video.duration / 60 : 10;
      if (event.key === "ArrowLeft") { event.preventDefault(); this.seekBy(-step); }
      if (event.key === "ArrowRight") { event.preventDefault(); this.seekBy(step); }
    });

    this.currentTime = el("span", { class: "time-label" }, "0:00");
    this.durationLabel = el("span", { class: "time-label" }, "0:00");

    // controls
    this.playButton = el("button", { class: "pbtn main", title: "Play/Pause (Space)", onclick: () => this.togglePlay() });
    this.prevButton = el("button", { class: "pbtn", title: "Previous (P)", onclick: () => this.stepQueue(-1) });
    this.prevButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 5v14L9 12z"/><path d="M6 5v14"/></svg>`;
    this.nextButton = el("button", { class: "pbtn", title: "Next (N)", onclick: () => this.stepQueue(1) });
    this.nextButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 5v14l10-7z"/><path d="M18 5v14"/></svg>`;

    this.muteButton = el("button", { class: "pbtn", title: "Mute (M)", onclick: () => this.toggleMute() });
    this.volume = el("input", {
      type: "range", min: "0", max: "1", step: "0.02",
      value: String(this.video.volume), "aria-label": "Volume",
      oninput: () => { this.video.muted = false; this.video.volume = Number(this.volume.value); },
    });

    this.subtitleButton = el("button", { class: "pbtn", title: "Subtitles (C)", onclick: () => this.toggleSubtitleMenu() });
    this.subtitleButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 14h4M13 14h4"/></svg>`;

    const pipButton = el("button", { class: "pbtn", title: "Picture-in-picture (I)", onclick: () => this.togglePip() });
    pipButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="15" rx="2"/><rect x="12" y="11" width="8" height="7" rx="1"/></svg>`;

    this.fullscreenButton = el("button", { class: "pbtn", title: "Fullscreen (F / double-click)", onclick: () => this.toggleFullscreen() });
    this.fullscreenButton.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"/></svg>`;

    this.controls = el("div", { class: "player-controls" },
      this.seekBar,
      el("div", { class: "controls-row" },
        this.playButton,
        this.prevButton,
        this.nextButton,
        this.currentTime, el("span", { style: { opacity: 0.5 } }, "/"), this.durationLabel,
        el("div", { class: "volume-group" }, this.muteButton, this.volume),
        el("div", { class: "spacer" }),
        this.subtitleButton,
        pipButton,
        this.fullscreenButton));

    this.root.append(this.top, this.controls);
  }

  setPlaying(playing) {
    if (!this.playButton) return;
    this.playButton.innerHTML = playing
      ? `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 4.5h3.5v15H7zM13.5 4.5H17v15h-3.5z" fill="currentColor" stroke="none"/></svg>`
      : `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none"/></svg>`;
    this.wake();
  }

  /* ------------------------------------------------------------- idle */
  wake() {
    this.root.classList.remove("idle");
    clearTimeout(this.idleTimer);
    if (this.failed) return; // failure state always shows its controls
    this.idleTimer = setTimeout(() => {
      if (!this.video.paused) this.root.classList.add("idle");
    }, IDLE_TIMEOUT);
  }

  setIdle() {
    if (!this.video.paused) this.root.classList.add("idle");
  }

  /* ------------------------------------------------------------- controls */
  togglePlay() {
    if (this.video.paused) this.video.play().catch(() => {});
    else this.video.pause();
  }

  seekTo(seconds) {
    if (!Number.isFinite(seconds)) return;
    this.video.currentTime = Math.max(0, Math.min(seconds, this.video.duration || seconds));
    this.wake();
  }

  seekBy(delta) {
    this.seekTo((this.video.currentTime || 0) + delta);
  }

  startScrub(event) {
    const scrub = (clientX) => {
      const rect = this.seekBar.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      if (this.video.duration) {
        this.playedBar.style.width = `${ratio * 100}%`;
        this.seekThumb.style.left = `${ratio * 100}%`;
        this.pendingSeek = ratio * this.video.duration;
      }
    };
    scrub(event.clientX);
    const move = (moveEvent) => scrub(moveEvent.clientX);
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (this.pendingSeek !== undefined) {
        this.seekTo(this.pendingSeek);
        this.pendingSeek = undefined;
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  updateBuffer() {
    const video = this.video;
    if (video.buffered.length && video.duration) {
      const end = video.buffered.end(video.buffered.length - 1);
      this.bufferBar.style.width = `${(end / video.duration) * 100}%`;
    }
  }

  onTimeUpdate() {
    const video = this.video;
    if (video.duration && this.pendingSeek === undefined) {
      const pct = (video.currentTime / video.duration) * 100;
      this.playedBar.style.width = `${pct}%`;
      this.seekThumb.style.left = `${pct}%`;
    }
    this.currentTime.textContent = formatClock(video.currentTime);
    this.durationLabel.textContent = formatClock(video.duration);
  }

  toggleMute() {
    this.video.muted = !this.video.muted;
    this.volume.value = this.video.muted ? 0 : this.video.volume;
  }

  async togglePip() {
    try {
      if (document.pictureInPictureElement) await document.exitPictureInPicture();
      else await this.video.requestPictureInPicture();
    } catch {
      toast("Picture-in-picture isn't available for this video", "error");
    }
  }

  toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else this.root.requestFullscreen().catch(() => {});
  }

  setRate(rate) {
    this.rate = rate;
    this.video.playbackRate = rate;
    if (this.settingsPanel) this.renderSpeedPop();
  }

  /* ------------------------------------------------------------- subtitles */
  toggleSubtitleMenu() {
    this.closePanels();
    this.subtitleMenu = el("div", { class: "player-settings subtitle-menu" });
    this.renderSubtitleMenu();
    this.root.append(this.subtitleMenu);
  }

  renderSubtitleMenu() {
    if (!this.subtitleMenu) return;
    const menu = this.subtitleMenu;
    menu.replaceChildren();
    menu.append(el("h4", {}, "Subtitles"));
    const subs = this.data.subtitles || [];
    const off = el("button", { class: this.subtitle ? "" : "on", onclick: () => this.selectSubtitle(null) }, "Off");
    menu.append(off);
    for (const track of subs) {
      menu.append(el("button", {
        class: this.subtitle === track.id ? "on" : "",
        onclick: () => this.selectSubtitle(track.id),
      }, track.label || track.language || "Subtitle"));
    }
    if (!subs.length) menu.append(el("div", { style: { color: "rgba(255,255,255,.5)", fontSize: "12px", padding: "8px 10px" } }, "No external subtitles found for this file"));
    // subtitle delay (real: shifts the active track's cue times)
    const delayRow = el("div", { class: "delay-row" },
      el("span", { class: "delay-label" }, `Delay ${this.subtitleDelay > 0 ? "+" : ""}${this.subtitleDelay.toFixed(2)}s`),
      el("button", { title: "Subtitles earlier (J)", onclick: () => this.applySubtitleDelay(-0.25) }, "−0.25s"),
      el("button", { title: "Subtitles later (Shift+J)", onclick: () => this.applySubtitleDelay(0.25) }, "+0.25s"),
      this.subtitleDelay !== 0 ? el("button", { title: "Reset delay", onclick: () => this.applySubtitleDelay(-this.subtitleDelay) }, "Reset") : null);
    menu.append(delayRow);
  }

  /** Pick the subtitle matching default_subtitle_language (settings) once. */
  autoSelectSubtitle() {
    const language = String(store.settings.default_subtitle_language || "").trim().toLowerCase();
    if (!language || this.subtitle !== null) return;
    const subs = this.data.subtitles || [];
    const match = subs.find((track) => String(track.language || "").toLowerCase() === language)
      || subs.find((track) => String(track.language || "").toLowerCase().startsWith(language));
    if (match) this.selectSubtitle(match.id);
  }

  /** Shift the active external subtitle by `delta` seconds (real cue times). */
  applySubtitleDelay(delta) {
    if (!delta) { this.renderSubtitleMenu(); return; }
    this.subtitleDelay = Math.round((this.subtitleDelay + delta) * 100) / 100;
    const list = this.video.textTracks;
    for (let i = 0; i < list.length; i++) {
      const track = list[i];
      if (track.mode !== "showing" || !track.cues) continue;
      for (let j = 0; j < track.cues.length; j++) {
        track.cues[j].startTime += delta;
        track.cues[j].endTime += delta;
      }
    }
    if (this.subtitleMenu) this.renderSubtitleMenu();
    toast(`Subtitle delay: ${this.subtitleDelay > 0 ? "+" : ""}${this.subtitleDelay.toFixed(2)}s`, "info", 1400);
  }

  selectSubtitle(id) {
    // remove previous track element
    this.video.querySelectorAll("track").forEach((node) => node.remove());
    this.subtitle = id;
    if (id !== null) {
      const track = (this.data.subtitles || []).find((entry) => entry.id === id);
      if (track) {
        const node = el("track", {
          kind: "subtitles", src: track.url, srclang: track.language || "en",
          label: track.label || "Subtitles",
        });
        node.addEventListener("load", () => {
          this.video.textTracks[0].mode = "showing";
          this.applySubtitleDelay(0); // no-op re-render; cues are fresh
        });
        this.video.append(node);
        if (this.video.textTracks[0]) this.video.textTracks[0].mode = "showing";
      }
    }
    this.closePanels();
  }

  /* ------------------------------------------------------------- settings */
  toggleSettings() {
    if (this.settingsPanel) { this.closePanels(); return; }
    this.closePanels();
    const panel = el("div", { class: "player-settings" });
    panel.append(el("h4", {}, "Playback settings"));

    panel.append(el("div", { class: "setting-row" },
      el("div", { class: "labels" },
        el("div", { class: "t" }, "Speed"),
        el("div", { class: "s" }, "Playback rate"))));
    this.speedPop = el("div", { class: "speed-pop" });
    panel.append(this.speedPop);
    this.renderSpeedPop();

    const autoplayLabel = el("div", { class: "labels" },
      el("div", { class: "t" }, "Autoplay next"),
      el("div", { class: "s" }, this.data.autoplay_next ? "On (from settings)" : "Off (from settings)"));
    const toggle = el("input", {
      type: "checkbox", checked: this.data.autoplay_next ? "checked" : null,
      onchange: (event) => { this.data.autoplay_next = event.target.checked; },
    });
    const track = el("span", { class: "track" });
    const thumb = el("span", { class: "thumb" });
    toggle.style.display = "none";
    const switchEl = el("label", { class: "switch" }, toggle, track, thumb);
    switchEl.addEventListener("click", (event) => {
      event.preventDefault();
      toggle.checked = !toggle.checked;
      this.data.autoplay_next = toggle.checked;
      track.style.background = toggle.checked ? "var(--accent)" : "rgba(255,255,255,.2)";
    });
    panel.append(el("div", { class: "setting-row" }, autoplayLabel, switchEl));

    const file = this.media.file || {};
    const audioStreams = file.audio_tracks || [];
    const fileDetail = [
      file.name || "",
      file.mime || "",
      file.video_codec ? `video: ${file.video_codec}` : "",
      file.width ? `${file.width}×${file.height}` : "",
      audioStreams.length > 1
        ? `${audioStreams.length} audio streams (${audioStreams.map((s) => s.language || s.codec || "?").join(", ")})`
        : "",
    ].filter(Boolean).join(" · ");
    panel.append(el("div", { class: "setting-row" },
      el("div", { class: "labels" },
        el("div", { class: "t" }, "File"),
        el("div", { class: "s" }, fileDetail || "unknown"))));

    // Audio tracks: real selection when the platform exposes AudioTrackList,
    // honest information (not a dead control) when it doesn't.
    const audioList = this.video.audioTracks;
    if (audioList && audioList.length > 1) {
      panel.append(el("div", { class: "setting-row" },
        el("div", { class: "labels" },
          el("div", { class: "t" }, "Audio track"),
          el("div", { class: "s" }, "Switch the active audio stream"))));
      const pop = el("div", { class: "speed-pop" });
      for (let i = 0; i < audioList.length; i++) {
        const track = audioList[i];
        pop.append(el("button", {
          class: track.enabled ? "on" : "",
          onclick: () => {
            for (let j = 0; j < audioList.length; j++) audioList[j].enabled = j === i;
            this.toggleSettings(); this.toggleSettings(); // re-render selection
          },
        }, track.label || track.language || `Track ${i + 1}`));
      }
      panel.append(pop);
    } else if (audioStreams.length > 1) {
      panel.append(el("div", { class: "setting-row" },
        el("div", { class: "labels" },
          el("div", { class: "t" }, "Audio track"),
          el("div", { class: "s" }, `${audioStreams.length} streams in this file — the embedded player can't switch tracks; use the external player for that`))));
    }

    // Subtitle delay mirrors the subtitle menu control (real cue shifting)
    panel.append(el("div", { class: "setting-row" },
      el("div", { class: "labels" },
        el("div", { class: "t" }, "Subtitle delay"),
        el("div", { class: "s" }, `Current: ${this.subtitleDelay > 0 ? "+" : ""}${this.subtitleDelay.toFixed(2)}s (J / Shift+J)`)),
      el("div", { class: "delay-row" },
        el("button", { onclick: () => this.applySubtitleDelay(-0.25) }, "−"),
        el("button", { onclick: () => this.applySubtitleDelay(0.25) }, "+"))));

    if (!this.embeddedCodecSupported()) {
      panel.append(el("div", { class: "setting-row codec-warning" },
        el("div", { class: "labels" },
          el("div", { class: "t" }, `Embedded playback may show no video (${file.video_codec || "codec"})`),
          el("div", { class: "s" }, "This system can't decode it inside JMDB (Chromium has no software fallback for it). If the screen stays black, use the external player button in the top bar."))));
    }

    this.settingsPanel = panel;
    this.root.append(panel);
  }

  renderSpeedPop() {
    if (!this.speedPop) return;
    this.speedPop.replaceChildren();
    for (const rate of [0.5, 0.75, 1, 1.25, 1.5, 2]) {
      this.speedPop.append(el("button", {
        class: this.rate === rate ? "on" : "",
        onclick: () => this.setRate(rate),
      }, `${rate}×`));
    }
  }

  toggleQueue() {
    if (this.queuePanel) { this.closePanels(); return; }
    this.closePanels();
    const panel = el("div", { class: "queue-panel" });
    panel.append(el("h4", {}, `Queue (${(this.data.queue || []).length})`));
    for (const entry of this.data.queue || []) {
      panel.append(el("div", {
        class: `queue-item ${entry.current ? "current" : ""}`,
        onclick: () => this.jumpTo(entry),
      },
        entry.artwork_path ? posterThumb(entry.artwork_path, "thumb") : null,
        el("span", { style: { flex: "1", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, entry.title),
        entry.subtitle ? el("span", { style: { opacity: 0.6, fontSize: "11.5px" } }, entry.subtitle) : null));
    }
    if (!(this.data.queue || []).length) panel.append(el("div", { style: { color: "rgba(255,255,255,.5)" } }, "Nothing else in the queue"));
    this.queuePanel = panel;
    this.root.append(panel);
  }

  closePanels() {
    this.queuePanel?.remove();
    this.settingsPanel?.remove();
    this.subtitleMenu?.remove();
    this.queuePanel = this.settingsPanel = this.subtitleMenu = null;
  }

  jumpTo(entry) {
    if (entry.media_type === this.media.type && entry.media_id === this.media.id) {
      this.closePanels();
      return;
    }
    const wasPlaying = !this.video.paused;
    this.close(true); // stop reporting, keep DOM until reopen
    openPlayer({ mediaType: entry.media_type, mediaId: entry.media_id, context: this.data.context || null })
      .then((player) => { if (player && wasPlaying) player.video.play().catch(() => {}); });
  }

  stepQueue(direction) {
    this.lastDirection = direction;
    const queue = this.data.queue || [];
    const index = queue.findIndex((entry) => entry.media_type === this.media.type && entry.media_id === this.media.id);
    const next = queue[index + direction];
    if (next) this.jumpTo(next);
    else toast(direction > 0 ? "End of queue" : "Start of queue", "info", 1500);
  }

  restart() {
    this.seekTo(0);
    this.video.play().catch(() => {});
  }

  /* ------------------------------------------------------------- resume */
  showResumePrompt() {
    if (this.resumePrompt) return;
    const box = el("div", { class: "center-msg" },
      el("h3", {}, `Resume “${this.media.title}”?`),
      el("p", {}, `You stopped at ${formatClock(this.position)}.`),
      el("div", { class: "row" },
        el("button", { class: "btn primary", onclick: () => { this.seekTo(this.position); this.resumePrompt.remove(); this.resumePrompt = null; this.video.play().catch(() => {}); } }, `Resume at ${formatClock(this.position)}`),
        el("button", { class: "btn", onclick: () => { this.position = 0; this.resumePrompt.remove(); this.resumePrompt = null; this.video.play().catch(() => {}); } }, "Start over")));
    this.root.append(box);
    this.resumePrompt = box;
  }

  /* ------------------------------------------------------------- errors */
  /** True when the embedded Chromium can decode this file's video codec.
   * Chromium only plays HEVC with working hardware decode (no software
   * fallback) — ask the platform's own capability API instead of guessing. */
  embeddedCodecSupported() {
    const codec = this.fileCodec.toLowerCase();
    const mime = this.media.file?.mime || "";
    const probe = document.createElement("video");
    const supports = (type) => probe.canPlayType(type) !== "";
    if (codec === "hevc" || codec === "h265") {
      // Chromium plays HEVC only with hardware decode; this is the platform's
      // own capability answer (guaranteed accurate since Chrome 107)
      return supports('video/mp4; codecs="hvc1.1.6.L93.B0"')
        || supports('video/mp4; codecs="hev1.1.6.L93.B0"');
    }
    if (codec === "av1") return supports('video/mp4; codecs="av01.0.05M.08"');
    if (mime && supports(mime) === false && codec) return false;
    return true; // unknown codecs: let the element try, the watchdog catches failures
  }

  /** Black-screen monitor: actively PLAYING (time advancing) yet not a
   * single video frame decoded. Three consecutive 1s samples while playing
   * with videoWidth === 0 → honest failure; anything else (paused, stalled,
   * still buffering the first frame) just resets. A file that decodes at any
   * point stops the monitor for good. */
  startDecodeMonitor() {
    if (this.media.type === "track") return; // audio-only by design
    let lastTime = -1;
    let strikes = 0;
    this.decodeMonitor = setInterval(() => {
      if (this.failed || this.closed) {
        clearInterval(this.decodeMonitor);
        return;
      }
      const video = this.video;
      if (video.videoWidth > 0) { // first frame decoded — healthy forever
        clearInterval(this.decodeMonitor);
        return;
      }
      const advancing = !video.paused && video.currentTime > lastTime + 0.05;
      lastTime = video.currentTime;
      if (advancing && video.readyState >= 2 && video.currentTime > 1.5) {
        strikes += 1;
        if (strikes >= 3) {
          clearInterval(this.decodeMonitor);
          this.showDecodeFailure("Audio plays but no video frame was ever decoded " +
            `on this machine${this.fileCodec ? ` — codec ${this.fileCodec}` : ""}.`);
        }
      } else {
        strikes = 0;
      }
    }, 1000);
  }

  onVideoError() {
    const error = this.video.error;
    const detail = error ? `${error.message || ""} (code ${error.code})` : "unknown error";
    this.showDecodeFailure(detail);
  }

  showDecodeFailure(detail) {
    if (this.failed) return;
    this.failed = true;
    if (this.decodeMonitor) clearInterval(this.decodeMonitor);
    // stop everything: no zombie audio under a dead screen
    try { this.video.pause(); this.video.removeAttribute("src"); this.video.load(); } catch { /* already gone */ }
    this.root.classList.add("failure"); // chrome never auto-hides in a failure
    const codec = this.fileCodec;
    const streams = this.audioStreamCount;
    const box = el("div", { class: "center-msg" },
      el("h3", { class: "video-error" }, "This file can't play in the embedded player"),
      el("p", {}, `${this.media.file?.name || this.media.title} — ${detail}`),
      codec ? el("p", { class: "codec-note" },
        `Codec: ${codec}${this.media.file?.width ? ` · ${this.media.file.width}×${this.media.file.height}` : ""}` +
        `${streams > 1 ? ` · ${streams} audio streams` : ""}. ` +
        (codec === "hevc" || codec === "h265"
          ? "HEVC only plays embedded when this system's GPU provides hardware decoding; VLC/MPV play it in software."
          : "The embedded Chromium player doesn't support this container/codec.")) : null,
      el("div", { class: "row" },
        el("button", { class: "btn primary", onclick: () => this.playExternal() }, "Open in external player"),
        el("button", { class: "btn", onclick: () => this.close() }, "Back")));
    this.root.append(box);
    this.report(true);
  }

  async playExternal() {
    try {
      await api.post(`/api/playback/external`, {
        media_type: this.media.type, media_id: this.media.id,
      });
      this.close();
    } catch (error) {
      toast(error.status === 503 ? "No external player configured on this system" : `External playback failed: ${error.message}`, "error");
    }
  }

  /* ------------------------------------------------------------- events */
  onEnded() {
    this.report(true);
    api.post("/api/playback/finish", {
      session_id: this.sessionId,
      media_type: this.media.type,
      media_id: this.media.id,
      completed: true,
      position: this.video.duration || 0,
      duration: this.video.duration || 0,
    }).then((result) => {
      if (this.closed) return;
      if (this.data.autoplay_next && result && result.next) {
        const next = result.next;
        const hasNext = (this.data.queue || []).some(
          (entry) => entry.media_type === next.media_type && entry.media_id === next.media_id);
        if (hasNext) {
          this.close(true);
          openPlayer({ mediaType: next.media_type, mediaId: next.media_id, context: this.data.context || null, startAt: 0 });
          return;
        }
      }
      const box = el("div", { class: "center-msg" },
        el("h3", {}, "Finished"),
        el("p", {}, "That's the end of this one."),
        el("div", { class: "row" },
          el("button", { class: "btn", onclick: () => { box.remove(); this.restart(); } }, "Watch again"),
          el("button", { class: "btn primary", onclick: () => this.close() }, "Back to library")));
      this.root.append(box);
    }).catch(() => this.close());
  }

  onKey(event) {
    if (event.target && ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
    const key = event.key.toLowerCase();
    let handled = true;
    switch (key) {
      case " ":
      case "k":
        this.togglePlay();
        break;
      // step sizes come from the persisted seek_step_seconds / volume_step
      case "arrowleft": this.seekBy(-this.seekStep); break;
      case "arrowright": this.seekBy(this.seekStep); break;
      case "j":
        if (event.shiftKey) this.applySubtitleDelay(0.25);
        else this.seekBy(-this.seekStep);
        break;
      case "l": this.seekBy(this.seekStep); break;
      case "arrowup":
        this.video.volume = Math.min(1, this.video.volume + this.volumeStep);
        this.volume.value = this.video.volume;
        break;
      case "arrowdown":
        this.video.volume = Math.max(0, this.video.volume - this.volumeStep);
        this.volume.value = this.video.volume;
        break;
      case "m": this.toggleMute(); break;
      case "f": this.toggleFullscreen(); break;
      case "i": this.togglePip(); break;
      case "c": this.toggleSubtitleMenu(); break;
      case "n": this.stepQueue(1); break;
      case "p": this.stepQueue(-1); break;
      case "r": this.restart(); break;
      case "escape":
        if (document.fullscreenElement) document.exitFullscreen();
        else this.close();
        break;
      case ">": this.setRate(Math.min(2, this.rate + 0.25)); break;
      case "<": this.setRate(Math.max(0.5, this.rate - 0.25)); break;
      default: handled = false;
    }
    if (handled) {
      event.preventDefault();
      this.wake();
    }
  }

  /* ------------------------------------------------------------- reporting */
  async report(final) {
    if (this.closed || !this.sessionId) return;
    const position = this.video?.currentTime ?? 0;
    if (!final && Math.abs(position - this.lastReported) < 1) return;
    this.lastReported = position;
    try {
      await api.post("/api/playback/progress", {
        session_id: this.sessionId,
        media_type: this.media.type,
        media_id: this.media.id,
        position: position,
        duration: this.video?.duration || 0,
      });
    } catch {
      /* backend may be shutting down */
    }
  }

  /* ------------------------------------------------------------- teardown */
  close(skipReport = false) {
    if (this.closed) return;
    this.closed = true;
    if (!skipReport) this.report(true);
    clearInterval(this.reportTimer);
    clearTimeout(this.idleTimer);
    if (this.decodeMonitor) clearInterval(this.decodeMonitor);
    if (this.onFullscreenChange) document.removeEventListener("fullscreenchange", this.onFullscreenChange);
    document.removeEventListener("keydown", this.keyHandler);
    document.body.classList.remove("player-open");
    try { this.video.pause(); } catch { /* already gone */ }
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    this.root.remove();
    if (active === this) active = null;
    navigate(currentHashForRefresh());
  }
}

function currentHashForRefresh() {
  return location.hash || "#/home";
}
