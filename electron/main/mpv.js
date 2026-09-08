"use strict";
/** Embedded mpv engine — the multi-codec player backend for the desktop app.
 *
 * mpv is spawned with `--wid=<native window id>` so its video renders INSIDE
 * the app window (above Chromium's own content), and is driven over its JSON
 * IPC protocol through a unix socket. A transparent overlay BrowserWindow
 * (child of the main window) carries the VLC-style control bar, so controls
 * float above the video without any web-content trickery.
 *
 * Everything here is honest about failure: if mpv is missing, the socket
 * never appears, or the process dies, `open()` returns {ok:false, reason}
 * and the renderer falls back to the built-in Chromium player.
 *
 * Pure/testable parts (MpvIpcClient protocol, keymap, arg building, state
 * reduction) are exported for the node test suite; they are tested against
 * a REAL fake-mpv process that speaks the JSON IPC protocol over a socket.
 */
// Outside a real Electron main process (node --test), require("electron")
// resolves to the binary path string; the destructured symbols are then
// undefined. The engine guards every use, so the protocol client and the
// pure helpers run — and are tested — without a window manager.
const electronApi = require("electron");
const { BrowserWindow, screen } =
  electronApi && typeof electronApi === "object" ? electronApi : {};
const net = require("node:net");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

/* ---------------------------------------------------------------------------
 * mpv binary detection (real spawn, cached)
 * ------------------------------------------------------------------------- */

function mpvCandidates() {
  return [
    process.env.JMDB_MPV_PATH,
    "/usr/bin/mpv",
    "/usr/local/bin/mpv",
    "/snap/bin/mpv",
    path.join(os.homedir(), ".local/bin/mpv"),
  ].filter(Boolean);
}

let detectionCache = null;

async function detectMpv() {
  if (detectionCache) return detectionCache;
  const candidates = mpvCandidates();
  for (const candidate of candidates) {
    if (!fs.existsSync(candidate)) continue;
    const info = await probeMpvBinary(candidate);
    if (info) {
      detectionCache = { available: true, path: candidate, version: info.version, source: info.source };
      return detectionCache;
    }
  }
  detectionCache = { available: false, reason: "mpv is not installed (tried: " + candidates.join(", ") + "). Install it with your package manager, e.g. sudo apt install mpv" };
  return detectionCache;
}

function probeMpvBinary(binary) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(binary, ["--version"], { stdio: ["ignore", "pipe", "ignore"] });
    } catch {
      resolve(null);
      return;
    }
    let out = "";
    const timer = setTimeout(() => { try { child.kill(); } catch {} resolve(null); }, 3000);
    child.stdout.on("data", (chunk) => { out += String(chunk); });
    child.on("error", () => { clearTimeout(timer); resolve(null); });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0 && code !== null) return resolve(null);
      const match = /mpv\s+(\d+\.\d+(?:\.\d+)?)/.exec(out);
      resolve(match ? { version: match[1], source: binary } : null);
    });
  });
}

/* ---------------------------------------------------------------------------
 * JSON IPC client (line-delimited JSON over a unix socket)
 * ------------------------------------------------------------------------- */

class MpvIpcClient {
  constructor(socketPath) {
    this.socketPath = socketPath;
    this.buffer = "";
    this.nextId = 1;
    this.pending = new Map(); // request id -> {resolve, reject}
    this.listeners = new Map(); // event name -> Set(fn)
    this.socket = null;
    this.dead = false;
  }

  connect(timeoutMs = 4000) {
    return new Promise((resolve, reject) => {
      const socket = net.createConnection(this.socketPath);
      this.socket = socket;
      const timer = setTimeout(() => {
        socket.destroy();
        reject(new Error(`mpv IPC socket timeout: ${this.socketPath}`));
      }, timeoutMs);
      socket.on("connect", () => { clearTimeout(timer); resolve(); });
      socket.on("error", (error) => {
        clearTimeout(timer);
        this.dead = true;
        for (const { reject: rej } of this.pending.values()) rej(error);
        this.pending.clear();
        reject(error);
      });
      socket.on("data", (chunk) => this._feed(String(chunk)));
      socket.on("close", () => {
        this.dead = true;
        const error = new Error("mpv IPC socket closed");
        for (const { reject: rej } of this.pending.values()) rej(error);
        this.pending.clear();
        this._emit("__disconnected", error);
      });
    });
  }

  _feed(text) {
    this.buffer += text;
    let index;
    while ((index = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, index).trim();
      this.buffer = this.buffer.slice(index + 1);
      if (!line) continue;
      let message;
      try {
        message = JSON.parse(line);
      } catch {
        continue; // mpv should only send valid JSON lines
      }
      this._dispatch(message);
    }
  }

  _dispatch(message) {
    if (message.request_id !== undefined && this.pending.has(message.request_id)) {
      const waiter = this.pending.get(message.request_id);
      this.pending.delete(message.request_id);
      if (message.error === "success") waiter.resolve(message.data);
      else waiter.reject(new Error(message.error || "mpv command failed"));
      return;
    }
    if (message.event) this._emit(message.event, message);
    else this._emit("message", message);
  }

  _emit(name, payload) {
    const set = this.listeners.get(name);
    if (set) for (const fn of [...set]) fn(payload);
  }

  on(event, handler) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(handler);
    return () => this.listeners.get(event)?.delete(handler);
  }

  /** Run an mpv command; resolves with the command's data field. */
  command(...args) {
    if (this.dead) return Promise.reject(new Error("mpv IPC client is dead"));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.write(JSON.stringify({ command: args, request_id: id }) + "\n");
    });
  }

  observe(property, observeId) {
    this.socket.write(JSON.stringify({ command: ["observe_property", observeId, property], request_id: this.nextId++ }) + "\n");
  }

  close() {
    this.dead = true;
    try { this.socket?.destroy(); } catch { /* already closed */ }
  }
}

/* ---------------------------------------------------------------------------
 * Pure helpers (unit-tested)
 * ------------------------------------------------------------------------- */

/** Build mpv's command line for an embedded playback session. The media
 * itself is NOT on argv: it is loaded over the IPC socket after connect, so
 * a bad file returns a real error we can show instead of mpv dying quietly. */
function buildMpvArgs({ socketPath, windowId, volume = 100, subtitlePaths = [], title = "" }) {
  const args = [
    "--no-terminal",
    "--idle=yes",
    "--force-window=immediate",
    `--input-ipc-server=${socketPath}`,
    // the app owns ALL input; mpv is a pure render surface
    "--input-default-bindings=no",
    "--input-cursor=no",
    "--input-vo-keyboard=no",
    "--no-osc",
    "--no-osd-bar",
    "--cursor-autohide=always",
    "--keep-open=always",
    `--volume=${Math.round(volume)}`,
    "--sub-auto=fuzzy",
  ];
  if (windowId) args.push(`--wid=${windowId}`);
  if (title) args.push(`--title=${title}`);
  for (const sub of subtitlePaths) args.push(`--sub-file=${sub}`);
  return args;
}

/** Map a keyboard input (Electron before-input-event style) to an mpv
 * control action. Pure — tested in isolation. Returns null when unmapped. */
function mapPlayerKey({ key, control, shift, alt }) {
  if (alt) return null;
  const k = (key || "").toLowerCase();
  if (k === " " || k === "spacebar" || k === "k") return control ? null : "toggle-play";
  if (k === "arrowleft") return shift ? { action: "seek", delta: -1 } : { action: "seek", delta: -10 };
  if (k === "arrowright") return shift ? { action: "seek", delta: 1 } : { action: "seek", delta: 10 };
  if (k === "arrowup") return { action: "volume", delta: 5 };
  if (k === "arrowdown") return { action: "volume", delta: -5 };
  if (k === "m") return "toggle-mute";
  if (k === "f") return "toggle-fullscreen";
  if (k === "j") return { action: "sub-delay", delta: -0.25 };
  if (k === "l") return { action: "sub-delay", delta: 0.25 };
  if (k === "escape") return "escape";
  if (k === "n") return "next";
  if (k === "p") return "prev";
  return null;
}

/** Reduce an observed-property event into the player state shape the
 * overlay consumes. Pure. */
function reducePlayerState(state, message) {
  const next = { ...state };
  switch (message.name) {
    case "pause": next.paused = message.data; break;
    case "time-pos": next.position = Math.max(0, message.data || 0); break;
    case "duration": next.duration = message.data || 0; break;
    case "volume": next.volume = message.data; break;
    case "mute": next.muted = message.data; break;
    case "speed": next.speed = message.data; break;
    case "eof-reached": next.eof = Boolean(message.data); break;
    case "seeking": next.seeking = Boolean(message.data); break;
    case "demuxer-cache-time": next.buffered = (next.position || 0) + (message.data || 0); break;
    case "sid": next.sid = message.data === false ? 0 : message.data; break;
    case "aid": next.aid = message.data === false ? 0 : message.data; break;
    case "sub-delay": next.subDelay = message.data || 0; break;
    case "audio-delay": next.audioDelay = message.data || 0;
  }
  return next;
}

/** mpv track-list entries → UI track menus (audio / subtitle). Pure. */
function trackMenus(trackList) {
  const audio = [{ id: 0, label: "Off" }];
  const subs = [{ id: 0, label: "Off" }];
  for (const track of trackList || []) {
    if (track.type !== "audio" && track.type !== "sub") continue;
    const bits = [];
    if (track.title) bits.push(track.title);
    if (track.lang) bits.push(track.lang);
    if (track.codec) bits.push(track.codec);
    if (track.type === "audio" && track["demux-channel-count"]) bits.push(`${track["demux-channel-count"]}ch`);
    const label = bits.join(" · ") || `Track ${track.id}`;
    const entry = { id: track.id, label, selected: Boolean(track.selected), forced: track.forced || false, default: track.default || false };
    if (track.type === "audio") audio.push(entry);
    else subs.push(entry);
  }
  return { audio, subs };
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

/* ---------------------------------------------------------------------------
 * The engine itself
 * ------------------------------------------------------------------------- */

class MpvEngine {
  constructor({ getWindow, backendInfo, sendToRenderer }) {
    this.getWindow = getWindow; // () => BrowserWindow | null
    this.backendInfo = backendInfo; // () => { url, token } | null
    this.sendToRenderer = sendToRenderer; // (channel, payload) => void
    this.client = null;
    this.child = null;
    this.overlay = null;
    this.socketPath = null;
    this.state = null;
    this.session = null; // { sessionId, mediaType, mediaId, position, finished }
    this.trackList = [];
    this.inputHook = null;
    this.cursorTimer = null;
    this.lastPointer = null;
    this.idleTimer = null;
    this.reportTimer = null;
    this.windowSync = null;
    this.active = false;
    this.controlsPinned = false;
    this.lastReported = -1;
    this.overlayState = null;
    this.finishedSession = false;
  }

  async status() {
    return detectMpv();
  }

  get window() { return this.getWindow(); }

  /** Open a playback session. Resolves {ok:true} or {ok:false, error}. */
  async open(payload) {
    const detection = await detectMpv();
    if (!detection.available) return { ok: false, error: detection.reason };

    const win = this.window;
    if (!win || win.isDestroyed()) return { ok: false, error: "no main window" };

    let windowId = 0;
    try {
      const handle = win.getNativeWindowHandle();
      // X11: a 4-byte little-endian window id (XID). Zero/empty → no X window
      // (e.g. native Wayland) → mpv cannot embed; fail honestly.
      if (handle && handle.length >= 4) windowId = handle.readUInt32LE(0);
    } catch { /* leave 0 */ }
    if (!windowId) {
      return { ok: false, error: "no X11 window handle — mpv embedding needs X11/XWayland (run without native Wayland)" };
    }

    // one engine session at a time
    await this.closeInternal("replaced", { skipReport: true });

    const mediaPath = payload.path && payload.fileExists !== false ? payload.path : null;
    const mediaUrl = payload.url ? new URL(payload.url, this.backendInfo()?.url || "http://127.0.0.1").toString() : null;
    if (!mediaPath && !mediaUrl) return { ok: false, error: "no media path or stream URL" };

    this.socketPath = path.join(os.tmpdir(), `jmdb-mpv-${process.pid}-${Date.now()}.sock`);
    const args = buildMpvArgs({
      socketPath: this.socketPath,
      windowId,
      volume: payload.volume != null ? payload.volume : 100,
      subtitlePaths: (payload.subtitles || []).map((s) => s.path).filter(Boolean).slice(0, 8),
      title: payload.title || "JMDB",
    });

    try {
      this.child = spawn(detection.path, args, { stdio: ["ignore", "ignore", "pipe"] });
    } catch (error) {
      return { ok: false, error: `couldn't start mpv: ${error.message}` };
    }

    let stderrTail = "";
    this.child.stderr?.on("data", (chunk) => {
      stderrTail = (stderrTail + String(chunk)).slice(-600);
    });

    // the socket file appears once mpv is up; then we connect
    const waited = await waitForFile(this.socketPath, 4000);
    if (!waited) {
      const why = this.child.exitCode !== null ? `mpv exited (code ${this.child.exitCode})${stderrTail ? `: ${stderrTail.trim().split("\n").pop()}` : ""}` : "mpv didn't create its IPC socket in time";
      await this.closeInternal("spawn-failed", { skipReport: true });
      return { ok: false, error: why };
    }

    this.client = new MpvIpcClient(this.socketPath);
    try {
      await this.client.connect(3000);
    } catch (error) {
      await this.closeInternal("spawn-failed", { skipReport: true });
      return { ok: false, error: `couldn't talk to mpv: ${error.message}` };
    }

    // load the media over IPC: mpv answers with a real success/failure
    const loadOptions = {};
    if ((payload.start || 0) > 3) loadOptions["start"] = `+${Math.floor(payload.start)}`;
    const loaded = await this.client
      .command("loadfile", mediaPath || mediaUrl, "replace", loadOptions)
      .catch((error) => ({ __error: String(error.message || error) }));
    if (loaded && loaded.__error) {
      await this.closeInternal("open-failed", { skipReport: true });
      return { ok: false, error: `mpv refused the file: ${loaded.__error}${stderrTail ? ` (${stderrTail.trim().split("\n").pop()})` : ""}` };
    }

    if (payload.subtitleLanguage) {
      await this.client.command("set", "slang", payload.subtitleLanguage).catch(() => {});
    }

    this.session = {
      sessionId: payload.sessionId || null,
      mediaType: payload.mediaType || null,
      mediaId: payload.mediaId || null,
      position: payload.start || 0,
      finished: false,
      title: payload.title || "",
      queue: payload.queue || [],
      autoplayNext: Boolean(payload.autoplayNext),
      backendNext: null,
    };
    this.state = {
      paused: false, position: payload.start || 0, duration: payload.duration || 0,
      volume: payload.volume != null ? payload.volume : 100, muted: false, speed: 1,
      eof: false, seeking: false, buffered: 0, sid: 0, aid: 0, subDelay: 0, audioDelay: 0,
      title: payload.title || "", finished: false, next: null, autoplayNext: Boolean(payload.autoplayNext),
    };
    this.active = true;

    // property observation → state → overlay
    let observeId = 1;
    for (const property of ["pause", "time-pos", "duration", "volume", "mute", "speed", "eof-reached", "seeking", "demuxer-cache-time", "sid", "aid", "sub-delay", "audio-delay", "track-list"]) {
      this.client.observe(property, observeId++);
    }
    this.client.on("property-change", (message) => {
      if (message.name === "track-list") {
        this.trackList = message.data || [];
        this.pushState({ tracks: trackMenus(this.trackList) });
        return;
      }
      this.state = reducePlayerState(this.state, message);
      if (message.name === "time-pos" && this.session) this.session.position = this.state.position;
      if (message.name === "eof-reached" && message.data) this.handleEof();
      this.pushState();
    });

    await this.buildOverlay(payload);

    // if the window goes away mid-playback, tear down honestly
    const onWindowClosed = () => { if (this.active) this.closeInternal("window-closed", {}); };
    win.once("closed", onWindowClosed);

    // keyboard lands on the main window (the overlay is click-only): hook
    // before-input-event while the engine is active
    this.installInputHook();

    // pointer polling wakes the controls (the overlay can't see the mouse
    // over the mpv surface because mpv owns that region)
    this.startCursorWatch();

    // progress reporting to the backend (same contract as the HTML player)
    this.reportTimer = setInterval(() => this.report(false), 5000);

    this.child.once("exit", () => {
      if (this.active) this.closeInternal("mpv-exited", {});
    });
    this.client.on("__disconnected", () => {
      if (this.active) this.closeInternal("mpv-exited", {});
    });

    return { ok: true, engine: "mpv", version: detection.version };
  }

  async buildOverlay(payload) {
    if (typeof BrowserWindow !== "function") return; // node test context
    const win = this.window;
    if (!win || win.isDestroyed()) return;
    this.overlay = new BrowserWindow({
      parent: win,
      show: false,
      frame: false,
      transparent: true,
      resizable: false,
      movable: false,
      skipTaskbar: true,
      hasShadow: false,
      focusable: false,
      webPreferences: {
        preload: path.join(__dirname, "overlay", "preload.js"),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });
    this.overlay.setMenu(null);
    await this.overlay.loadFile(path.join(__dirname, "overlay", "overlay.html"));
    this.syncOverlayBounds();
    this.overlay.showInactive();

    // click-to-pause on the video area is handled by the overlay's transparent
    // center region (the overlay covers the window, so mpv never sees input)
    const sync = () => this.syncOverlayBounds();
    this.windowSync = () => { if (this.overlay && !this.overlay.isDestroyed()) sync(); };
    for (const event of ["resize", "move", "maximize", "unmaximize", "enter-full-screen", "leave-full-screen", "restore"]) {
      win.on(event, this.windowSync);
    }

    // initial state + queue for the overlay UI
    this.pushState({
      tracks: trackMenus(this.trackList),
      queue: this.session.queue,
      seekStep: payload.seekStep || 10,
      volumeStep: payload.volumeStep || 5,
      canNext: this.hasNext(),
      finished: false,
    });
  }

  syncOverlayBounds() {
    if (!this.overlay || this.overlay.isDestroyed() || !this.window || this.window.isDestroyed()) return;
    try {
      const bounds = this.window.getContentBounds();
      this.overlay.setBounds(bounds);
    } catch { /* window mid-teardown */ }
  }

  /** Overlay → engine commands. Returns a result object for the overlay. */
  async command(name, arg) {
    if (!this.client || this.client.dead) return { ok: false, error: "mpv is not running" };
    try {
      switch (name) {
        case "toggle-play":
          await this.client.command("cycle", "pause");
          return { ok: true };
        case "play": await this.client.command("set", "pause", false); return { ok: true };
        case "pause": await this.client.command("set", "pause", true); return { ok: true };
        case "seek":
          await this.client.command("seek", Math.max(0, Number(arg) || 0), "absolute");
          return { ok: true };
        case "seek-relative":
          await this.client.command("seek", Number(arg) || 0, "relative");
          return { ok: true };
        case "set-volume":
          await this.client.command("set", "volume", Math.min(130, Math.max(0, Number(arg) || 0)));
          return { ok: true };
        case "toggle-mute":
          await this.client.command("cycle", "mute");
          return { ok: true };
        case "set-speed":
          await this.client.command("set", "speed", Math.min(4, Math.max(0.25, Number(arg) || 1)));
          return { ok: true };
        case "set-audio-track": {
          const id = Number(arg) || 0;
          await this.client.command("set", "aid", id === 0 ? "no" : id);
          return { ok: true };
        }
        case "set-subtitle-track": {
          const id = Number(arg) || 0;
          await this.client.command("set", "sid", id === 0 ? "no" : id);
          return { ok: true };
        }
        case "sub-delay":
          await this.client.command("add", "sub-delay", Number(arg) || 0.25);
          return { ok: true };
        case "audio-delay":
          await this.client.command("add", "audio-delay", Number(arg) || 0.25);
          return { ok: true };
        case "cycle-fullscreen":
          this.toggleFullscreen();
          return { ok: true };
        case "show-controls":
          this.wakeControls();
          return { ok: true };
        case "hide-controls":
          this.hideControls();
          return { ok: true };
        case "set-pinned":
          this.controlsPinned = Boolean(arg);
          if (this.controlsPinned) this.wakeControls();
          return { ok: true };
        case "replay":
          await this.client.command("seek", 0, "absolute");
          await this.client.command("set", "pause", false);
          this.state = { ...this.state, eof: false, finished: false, next: null };
          this.pushState();
          return { ok: true };
        case "close":
          await this.closeInternal("user", {});
          return { ok: true };
        case "next":
          await this.playNext();
          return { ok: true };
        case "prev":
          await this.playPrev();
          return { ok: true };
        default:
          return { ok: false, error: `unknown command: ${name}` };
      }
    } catch (error) {
      return { ok: false, error: error.message };
    }
  }

  toggleFullscreen() {
    const win = this.window;
    if (!win || win.isDestroyed()) return;
    if (win.isFullScreen()) win.setFullScreen(false);
    else win.setFullScreen(true);
  }

  hasNext() {
    const queue = this.session?.queue || [];
    const index = queue.findIndex((e) => e.current);
    return index >= 0 && index < queue.length - 1 ? queue[index + 1] : null;
  }
  hasPrev() {
    const queue = this.session?.queue || [];
    const index = queue.findIndex((e) => e.current);
    return index > 0 ? queue[index - 1] : null;
  }

  async playNext() {
    const next = this.hasNext();
    if (!next) return;
    await this.closeInternal("next", {}); // still reports the final position
    this.sendToRenderer("mpv:next", { mediaType: next.media_type, mediaId: next.media_id });
  }
  async playPrev() {
    const prev = this.hasPrev();
    if (!prev) return;
    await this.closeInternal("prev", {});
    this.sendToRenderer("mpv:prev", { mediaType: prev.media_type, mediaId: prev.media_id });
  }

  /** End-of-file: mark finished, decide autoplay, tell the overlay. */
  async handleEof() {
    if (!this.active || this.state.finished) return;
    let next = null;
    try {
      const result = await this.postFinish(this.session);
      next = result?.next || null;
    } catch { /* honest: no autoplay info */ }
    this.session.backendNext = next;
    this.state = { ...this.state, finished: true, next, autoplayNext: this.session.autoplayNext };
    this.pushState();
  }

  installInputHook() {
    const win = this.window;
    if (!win || win.isDestroyed()) return;
    this.inputHook = (event, input) => {
      if (!this.active) return;
      const mapped = mapPlayerKey({ key: input.key, control: input.control, shift: input.shift, alt: input.alt });
      if (!mapped) return;
      // let Escape through when NOT fullscreen so the renderer page exits too
      if (mapped === "escape") {
        const w = this.window;
        if (w && !w.isDestroyed() && w.isFullScreen()) {
          event.preventDefault();
          this.toggleFullscreen();
        } else {
          this.closeInternal("user", {});
        }
        return;
      }
      event.preventDefault();
      if (mapped === "toggle-play") this.command("toggle-play");
      else if (mapped === "toggle-mute") this.command("toggle-mute");
      else if (mapped === "toggle-fullscreen") this.toggleFullscreen();
      else if (mapped === "next") this.playNext();
      else if (mapped === "prev") this.playPrev();
      else if (mapped.action === "seek") {
        const step = (this.overlayState?.seekStep || 10);
        this.command("seek-relative", mapped.delta < 0 ? -step : step);
      } else if (mapped.action === "volume") {
        const step = (this.overlayState?.volumeStep || 5);
        this.command("set-volume", (this.state.volume || 100) + (mapped.delta < 0 ? -step : step));
      } else if (mapped.action === "sub-delay") this.command("sub-delay", mapped.delta);
    };
    win.webContents.on("before-input-event", this.inputHook);
  }

  startCursorWatch() {
    this.stopCursorWatch();
    this.cursorTimer = setInterval(() => {
      if (!this.active || !this.overlay || this.overlay.isDestroyed()) return;
      const win = this.window;
      if (!win || win.isDestroyed()) return;
      if (typeof screen?.getCursorScreenPoint !== "function") return;
      try {
        const point = screen.getCursorScreenPoint();
        const bounds = win.getContentBounds();
        const inside = point.x >= bounds.x && point.x <= bounds.x + bounds.width
          && point.y >= bounds.y && point.y <= bounds.y + bounds.height;
        const moved = !this.lastPointer || Math.abs(point.x - this.lastPointer.x) > 2 || Math.abs(point.y - this.lastPointer.y) > 2;
        this.lastPointer = point;
        if (inside && moved) this.wakeControls();
      } catch { /* screen API unavailable */ }
    }, 250);
  }
  stopCursorWatch() {
    if (this.cursorTimer) clearInterval(this.cursorTimer);
    this.cursorTimer = null;
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = null;
  }

  wakeControls() {
    if (!this.overlay || this.overlay.isDestroyed()) return;
    if (!this.overlay.isVisible()) {
      try { this.overlay.showInactive(); } catch { /* gone */ }
    }
    this.overlay.webContents.send("ov:controls-visible", true);
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => this.hideControls(), 3000);
  }
  hideControls() {
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = null;
    this.overlay?.webContents?.send?.("ov:controls-visible", false);
    setTimeout(() => {
      if (this.active && this.overlay && !this.overlay.isDestroyed() && !this.controlsPinned) {
        try { this.overlay.hide(); } catch { /* gone */ }
      }
    }, 250);
  }

  pushState(extra = {}) {
    if (!this.overlay || this.overlay.isDestroyed()) return;
    this.overlayState = { ...(this.overlayState || {}), ...extra };
    const payload = {
      ...this.state,
      ...extra,
      canNext: Boolean(this.hasNext()),
      canPrev: Boolean(this.hasPrev()),
      engine: "mpv",
    };
    try {
      this.overlay.webContents.send("ov:state", payload);
    } catch { /* overlay mid-teardown */ }
  }

  /* -------- backend session reporting (same contract as the HTML player) */

  async report(final) {
    if (!this.session || !this.session.sessionId) return;
    const info = this.backendInfo();
    if (!info || !info.url) return;
    const position = this.state?.position || 0;
    const duration = this.state?.duration || 0;
    if (!final && Math.abs(position - (this.lastReported || -1)) < 1) return;
    this.lastReported = position;
    try {
      await fetch(new URL("/api/playback/progress", info.url), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${info.token}` },
        body: JSON.stringify({
          session_id: this.session.sessionId,
          media_type: this.session.mediaType,
          media_id: this.session.mediaId,
          position,
          duration,
        }),
      });
    } catch { /* backend may be shutting down */ }
  }

  /** POST /api/playback/finish for a session (marks watched, returns next). */
  async postFinish(session) {
    if (!session || !session.sessionId) return null;
    const info = this.backendInfo();
    if (!info || !info.url) return null;
    const duration = this.state?.duration || 0;
    const response = await fetch(new URL("/api/playback/finish", info.url), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${info.token}` },
      body: JSON.stringify({
        session_id: session.sessionId,
        media_type: session.mediaType,
        media_id: session.mediaId,
        completed: true,
        position: duration,
        duration,
      }),
    });
    return response.ok ? response.json() : null;
  }

  /** Full teardown. reason: user | next | prev | mpv-exited | replaced | … */
  async closeInternal(reason, { skipReport = false } = {}) {
    if (!this.active && !this.client && !this.child && !this.overlay) return;
    this.active = false;
    const session = this.session;
    this.session = null;

    if (this.reportTimer) clearInterval(this.reportTimer);
    this.reportTimer = null;
    this.stopCursorWatch();

    if (!skipReport && session && this.state) {
      if (this.state.eof || this.state.finished) {
        this.finishedSession = true;
        await this.postFinish(session).catch(() => {});
      } else {
        await this.reportWith(session, this.state, true).catch(() => {});
      }
    }

    if (this.inputHook && this.window && !this.window.isDestroyed()) {
      this.window.webContents.removeListener("before-input-event", this.inputHook);
    }
    this.inputHook = null;

    if (this.windowSync && this.window && !this.window.isDestroyed()) {
      for (const event of ["resize", "move", "maximize", "unmaximize", "enter-full-screen", "leave-full-screen", "restore"]) {
        this.window.removeListener(event, this.windowSync);
      }
    }
    this.windowSync = null;

    this.client?.close();
    this.client = null;
    if (this.child && this.child.exitCode === null) {
      try { this.child.kill("SIGTERM"); } catch { /* already gone */ }
      const child = this.child;
      setTimeout(() => { try { child.kill("SIGKILL"); } catch {} }, 1500).unref?.();
    }
    this.child = null;

    if (this.overlay && !this.overlay.isDestroyed()) {
      try { this.overlay.destroy(); } catch { /* gone */ }
    }
    this.overlay = null;
    this.state = null;
    this.trackList = [];
    this.lastReported = -1;
    this.overlayState = null;
    this.controlsPinned = false;

    if (reason !== "replaced" && reason !== "next" && reason !== "prev") {
      this.sendToRenderer("mpv:closed", {
        reason,
        finished: Boolean(session && this.finishedSession),
      });
    }
    this.finishedSession = false;
  }

  async reportWith(session, state, final) {
    const info = this.backendInfo();
    if (!info || !info.url || !session.sessionId) return;
    await fetch(new URL("/api/playback/progress", info.url), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${info.token}` },
      body: JSON.stringify({
        session_id: session.sessionId,
        media_type: session.mediaType,
        media_id: session.mediaId,
        position: state.position || 0,
        duration: state.duration || 0,
      }),
    });
  }

  /** Renderer-requested close (player page navigating away). */
  async close() {
    await this.closeInternal("user", {});
  }
}

function waitForFile(filePath, timeoutMs) {
  return new Promise((resolve) => {
    const started = Date.now();
    const timer = setInterval(() => {
      try {
        if (fs.existsSync(filePath)) { clearInterval(timer); resolve(true); }
        else if (Date.now() - started > timeoutMs) { clearInterval(timer); resolve(false); }
      } catch {
        clearInterval(timer);
        resolve(false);
      }
    }, 60);
  });
}

module.exports = {
  MpvEngine,
  MpvIpcClient,
  _resetDetectionCacheForTests() { detectionCache = null; },
  detectMpv,
  buildMpvArgs,
  mapPlayerKey,
  reducePlayerState,
  trackMenus,
  formatTime,
};
