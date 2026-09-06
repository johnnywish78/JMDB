/** Full-featured media player overlay.
 *
 * Real controls only: play/pause, seek bar with buffered indicator, volume +
 * mute, speed, subtitles (external srt/vtt served by the backend), PiP,
 * fullscreen, prev/next in queue, restart, resume prompt, autoplay-next,
 * keyboard shortcuts, auto-hiding chrome. Progress is reported to the Python
 * backend, which owns resume/watched/next-episode decisions.
 */
import { api } from "./api.js";
import { el, formatClock, icon, toast } from "./ui.js";
import { navigate } from "./router.js";

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
  active = new Player(data, { requestedStart: startAt });
  active.open();
  return active;
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
    this.sessionId = data.session_id;
    this.lastDirection = 1;
  }

  open() {
    document.body.classList.add("player-open");
    this.root = el("div", { class: "player" });
    this.video = el("video", {
      src: this.data.stream_url,
      autoplay: "autoplay",
      preload: "metadata",
    });
    // default volume from backend setting, persisted locally per session
    const stored = Number(localStorage.getItem("jmdb.volume"));
    this.video.volume = Number.isFinite(stored) && stored >= 0 && stored <= 1
      ? stored
      : Math.min(1, Math.max(0, (this.data.volume ?? 90) / 100));
    this.video.muted = localStorage.getItem("jmdb.muted") === "1";
    this.buildChrome();
    this.root.append(this.video);
    document.getElementById("player-root").append(this.root);

    this.video.addEventListener("loadedmetadata", () => {
      if (this.position > 1 && this.position < (this.video.duration || Infinity) - 2) {
        this.showResumePrompt();
      }
    });
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
      el("button", { class: "pbtn", title: "Back (Esc)", onclick: () => this.close() },
        `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 5l-7 7 7 7"/></svg>`),
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
    const subs = this.data.subtitles || [];
    const menu = el("div", { class: "player-settings subtitle-menu" });
    menu.append(el("h4", {}, "Subtitles"));
    const off = el("button", { class: this.subtitle ? "" : "on", onclick: () => this.selectSubtitle(null) }, "Off");
    menu.append(off);
    for (const track of subs) {
      menu.append(el("button", {
        class: this.subtitle === track.id ? "on" : "",
        onclick: () => this.selectSubtitle(track.id),
      }, track.label || track.language || "Subtitle"));
    }
    if (!subs.length) menu.append(el("div", { style: { color: "rgba(255,255,255,.5)", fontSize: "12px", padding: "8px 10px" } }, "No external subtitles found for this file"));
    this.subtitleMenu = menu;
    this.root.append(menu);
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

    panel.append(el("div", { class: "setting-row" },
      el("div", { class: "labels" },
        el("div", { class: "t" }, "File"),
        el("div", { class: "s" }, `${this.media.file?.name || ""} · ${this.media.file?.mime || ""}`))));

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
  onVideoError() {
    const error = this.video.error;
    const detail = error ? `${error.message || ""} (code ${error.code})` : "unknown error";
    const box = el("div", { class: "center-msg" },
      el("h3", { class: "video-error" }, "This file can't play in the embedded player"),
      el("p", {}, `${this.media.file?.name || this.media.title} — ${detail}. ` +
        "The container or codec isn't supported by the embedded Chromium player. You can still watch it in an external player."),
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
      case "arrowleft": this.seekBy(-10); break;
      case "arrowright": this.seekBy(10); break;
      case "j": this.seekBy(-10); break;
      case "l": this.seekBy(10); break;
      case "arrowup":
        this.video.volume = Math.min(1, this.video.volume + 0.05);
        this.volume.value = this.video.volume;
        break;
      case "arrowdown":
        this.video.volume = Math.max(0, this.video.volume - 0.05);
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
