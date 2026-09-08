"use strict";
/** Tests for the embedded mpv engine.
 *
 * The JSON IPC client is tested against a REAL unix-socket server that
 * speaks the mpv protocol (a fake mpv process — no mocks of the code under
 * test), and the engine itself is exercised end-to-end with that fake mpv:
 * spawn → socket → loadfile → property observation → commands → honest
 * teardown. Pure helpers (args, keymap, state reduction, track menus) are
 * tested directly. Everything runs in plain node — no Electron, no display.
 */
const test = require("node:test");
const assert = require("node:assert");
const net = require("node:net");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Module = require("node:module");

// the engine runs headless here: BrowserWindow/screen are absent, and every
// use of them is guarded in the code under test (same stub pattern as the
// other main-process tests)
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "electron") return {};
  return origLoad.apply(this, arguments);
};

const {
  MpvIpcClient,
  MpvEngine,
  detectMpv,
  buildMpvArgs,
  mapPlayerKey,
  reducePlayerState,
  trackMenus,
  _resetDetectionCacheForTests,
} = require("../main/mpv.js");

/* ---------------------------------------------------------------- helpers */

function tmpSock() {
  return path.join(os.tmpdir(), `jmdb-test-mpv-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}.sock`);
}

/** A real fake-mpv server: unix socket, mpv JSON IPC protocol. Records every
 * command; can push property-change events on demand. */
class FakeMpvServer {
  constructor() {
    this.socketPath = tmpSock();
    this.commands = [];
    this.observed = [];
    this.server = null;
    this.clients = new Set();
    this.handlers = new Map(); // command name -> fn(args) => data | {error}
  }
  start() {
    return new Promise((resolve) => {
      this.server = net.createServer((socket) => {
        this.clients.add(socket);
        socket.setEncoding("utf8");
        let buffer = "";
        socket.on("data", (chunk) => {
          buffer += chunk;
          let index;
          while ((index = buffer.indexOf("\n")) >= 0) {
            const line = buffer.slice(0, index).trim();
            buffer = buffer.slice(index + 1);
            if (!line) continue;
            this.handle(JSON.parse(line), socket);
          }
        });
      });
      this.server.listen(this.socketPath, () => resolve());
    });
  }
  handle(message, socket) {
    if (Array.isArray(message.command)) {
      this.handleCommand(message, socket);
    }
  }
  async handleCommand(message, socket) {
    {
      const [name, ...args] = message.command;
      this.commands.push({ name, args });
      const handler = this.handlers.get(name);
      const reply = handler ? await handler(args) : null;
      if (reply && reply.__error) {
        socket.write(JSON.stringify({ request_id: message.request_id, error: reply.__error }) + "\n");
      } else {
        socket.write(JSON.stringify({ request_id: message.request_id, error: "success", data: reply && reply.__data !== undefined ? reply.__data : null }) + "\n");
      }
    }
  }
  push(event) {
    for (const socket of this.clients) socket.write(JSON.stringify(event) + "\n");
  }
  stop() {
    return new Promise((resolve) => {
      for (const socket of this.clients) socket.destroy();
      this.server?.close(() => {
        try { fs.unlinkSync(this.socketPath); } catch {}
        resolve();
      });
    });
  }
}

/* ------------------------------------------------------------- pure tests */

test("buildMpvArgs embeds the window, the socket, and disables mpv input", () => {
  const args = buildMpvArgs({
    socketPath: "/tmp/x.sock", windowId: 12345,
    volume: 90,
    subtitlePaths: ["/a.srt", "/b.vtt"], title: "Movie",
  });
  assert.ok(args.includes("--wid=12345"), "embeds the X window id");
  assert.ok(args.includes("--input-ipc-server=/tmp/x.sock"));
  assert.ok(args.includes("--input-default-bindings=no"), "the app owns input");
  assert.ok(args.includes("--input-cursor=no"));
  assert.ok(args.includes("--input-vo-keyboard=no"));
  assert.ok(args.includes("--keep-open=always"), "finished state keeps the last frame");
  assert.ok(args.includes("--volume=90"));
  assert.ok(args.includes("--sub-file=/a.srt"));
  assert.ok(args.includes("--sub-file=/b.vtt"));
  assert.ok(args.includes("--title=Movie"));
  assert.ok(!args.includes("--start=42"), "start is applied via loadfile options, not argv");
  assert.ok(!args.some((a) => typeof a !== "string"), "no media on argv — loaded over IPC for honest errors");
});

test("mapPlayerKey maps VLC-style shortcuts and rejects alt-combos", () => {
  assert.strictEqual(mapPlayerKey({ key: " ", control: false, shift: false, alt: false }), "toggle-play");
  assert.strictEqual(mapPlayerKey({ key: "k", control: false, shift: false, alt: false }), "toggle-play");
  assert.deepStrictEqual(mapPlayerKey({ key: "ArrowLeft", control: false, shift: false, alt: false }), { action: "seek", delta: -10 });
  assert.deepStrictEqual(mapPlayerKey({ key: "ArrowRight", control: false, shift: true, alt: false }), { action: "seek", delta: 1 });
  assert.deepStrictEqual(mapPlayerKey({ key: "ArrowUp", control: false, shift: false, alt: false }), { action: "volume", delta: 5 });
  assert.strictEqual(mapPlayerKey({ key: "m", control: false, shift: false, alt: false }), "toggle-mute");
  assert.strictEqual(mapPlayerKey({ key: "f", control: false, shift: false, alt: false }), "toggle-fullscreen");
  assert.deepStrictEqual(mapPlayerKey({ key: "j", control: false, shift: false, alt: false }), { action: "sub-delay", delta: -0.25 });
  assert.deepStrictEqual(mapPlayerKey({ key: "l", control: false, shift: false, alt: false }), { action: "sub-delay", delta: 0.25 });
  assert.strictEqual(mapPlayerKey({ key: "Escape", control: false, shift: false, alt: false }), "escape");
  assert.strictEqual(mapPlayerKey({ key: "n", control: false, shift: false, alt: false }), "next");
  assert.strictEqual(mapPlayerKey({ key: "p", control: false, shift: false, alt: false }), "prev");
  assert.strictEqual(mapPlayerKey({ key: "ArrowLeft", control: false, shift: false, alt: true }), null, "Alt is the window manager's");
  assert.strictEqual(mapPlayerKey({ key: "x", control: false, shift: false, alt: false }), null);
});

test("reducePlayerState maps observed properties into overlay state", () => {
  let state = { position: 0, duration: 0 };
  state = reducePlayerState(state, { name: "time-pos", data: 12.5 });
  assert.strictEqual(state.position, 12.5);
  state = reducePlayerState(state, { name: "duration", data: 5400 });
  assert.strictEqual(state.duration, 5400);
  state = reducePlayerState(state, { name: "pause", data: true });
  assert.strictEqual(state.paused, true);
  state = reducePlayerState(state, { name: "sid", data: false });
  assert.strictEqual(state.sid, 0, "sid=false (no subtitle) becomes track id 0");
  state = reducePlayerState(state, { name: "sid", data: 3 });
  assert.strictEqual(state.sid, 3);
  state = reducePlayerState(state, { name: "eof-reached", data: true });
  assert.strictEqual(state.eof, true);
  state = reducePlayerState(state, { name: "time-pos", data: -1 });
  assert.strictEqual(state.position, 0, "negative positions clamp to zero");
});

test("trackMenus splits mpv's track-list into audio/subtitle menus with Off", () => {
  const menus = trackMenus([
    { id: 1, type: "video", selected: true, codec: "hevc" },
    { id: 2, type: "audio", title: "Surround 5.1", lang: "eng", codec: "eac3", selected: true, "demux-channel-count": 6 },
    { id: 3, type: "audio", title: "Stereo", lang: "ger", codec: "aac" },
    { id: 4, type: "sub", lang: "eng", codec: "subrip", default: true },
    { id: 5, type: "sub", title: "Forced", lang: "eng", forced: true },
  ]);
  assert.strictEqual(menus.audio[0].label, "Off");
  assert.strictEqual(menus.audio.length, 3);
  assert.ok(menus.audio[1].label.includes("Surround 5.1"));
  assert.ok(menus.audio[1].label.includes("6ch"));
  assert.strictEqual(menus.audio[1].selected, true);
  assert.strictEqual(menus.subs.length, 3);
  assert.ok(menus.subs[1].default);
  assert.ok(menus.subs[2].forced);
});

/* ------------------------------------------------ protocol client (real socket) */

test("MpvIpcClient: command/response correlation and event dispatch", async () => {
  const server = new FakeMpvServer();
  server.handlers.set("get_property", () => ({ __data: 42 }));
  server.handlers.set("fail", () => ({ __error: "invalid parameter" }));
  await server.start();

  const client = new MpvIpcClient(server.socketPath);
  await client.connect();

  const events = [];
  client.on("property-change", (message) => events.push(message));

  const value = await client.command("get_property", "volume");
  assert.strictEqual(value, 42, "resolves the command's data field");

  await assert.rejects(() => client.command("fail"), /invalid parameter/);

  client.command("cycle", "pause"); // no handler needed; server logs it
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.deepStrictEqual(server.commands[server.commands.length - 1], { name: "cycle", args: ["pause"] });

  server.push({ event: "property-change", id: 1, name: "pause", data: true });
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].data, true);

  client.close();
  await server.stop();
});

test("MpvIpcClient: socket close rejects pending commands and signals disconnect", async () => {
  const server = new FakeMpvServer();
  server.handlers.set("slow", () => new Promise(() => {})); // never answers
  await server.start();
  const client = new MpvIpcClient(server.socketPath);
  await client.connect();

  let disconnected = null;
  client.on("__disconnected", (error) => { disconnected = error; });

  const pending = client.command("slow");
  await new Promise((resolve) => setTimeout(resolve, 30));
  await server.stop(); // kills the connections
  await assert.rejects(() => pending, /closed/);
  assert.ok(disconnected, "engine learns about mpv dying");
});

/* ------------------------------------------------------- binary detection */

test("detectMpv: finds and versions a real (fake) mpv binary", async () => {
  _resetDetectionCacheForTests();
  const fake = path.join(os.tmpdir(), `fake-mpv-${Date.now()}`);
  fs.writeFileSync(fake, "#!/bin/sh\necho 'mpv 0.38.0 (C) 2000-2025 mpv/MPlayer'\n", { mode: 0o755 });
  process.env.JMDB_MPV_PATH = fake;
  try {
    _resetDetectionCacheForTests();
    const status = await detectMpv();
    assert.strictEqual(status.available, true);
    assert.strictEqual(status.version, "0.38.0");
    assert.strictEqual(status.path, fake);
  } finally {
    delete process.env.JMDB_MPV_PATH;
    fs.unlinkSync(fake);
    _resetDetectionCacheForTests();
  }
});

test("detectMpv: honest unavailable status when mpv is missing", async () => {
  _resetDetectionCacheForTests();
  process.env.JMDB_MPV_PATH = "/nonexistent/jmdb-mpv-test";
  try {
    const status = await detectMpv();
    assert.strictEqual(status.available, false);
    assert.ok(/mpv is not installed/.test(status.reason), "the reason explains the fix");
  } finally {
    delete process.env.JMDB_MPV_PATH;
    _resetDetectionCacheForTests();
  }
});

/* ------------------------------------------------------ engine end-to-end */
/* A fake mpv BINARY: creates the --input-ipc-server socket and proxies the
 * JSON IPC protocol to the test's FakeMpvServer. The engine under test
 * spawns it exactly like real mpv. */
function makeBridge(server) {
  const bridge = path.join(os.tmpdir(), `fake-mpv-${Date.now()}-${Math.random().toString(36).slice(2, 6)}.cjs`);
  fs.writeFileSync(bridge, `#!/usr/bin/env node
"use strict";
const net = require("node:net");
const args = process.argv.slice(2);
if (args.includes("--version")) { console.log("mpv 0.38.0 (C) 2000-2025 mpv/MPlayer"); process.exit(0); }
const sockArg = args.find((a) => a.startsWith("--input-ipc-server="));
if (!sockArg) process.exit(3);
const sockPath = sockArg.slice("--input-ipc-server=".length);
const upstream = net.createConnection(${JSON.stringify(server.socketPath)});
upstream.setNoDelay(true);
const server = net.createServer((down) => {
  down.setEncoding("utf8");
  let buf = "";
  down.on("data", (c) => { buf += c; let i; while ((i = buf.indexOf("\\n")) >= 0) { const l = buf.slice(0, i); buf = buf.slice(i + 1); if (l.trim()) upstream.write(l + "\\n"); } });
  upstream.on("data", (c) => down.write(c));
  upstream.on("close", () => { down.end(); setTimeout(() => process.exit(0), 100); });
});
server.listen(sockPath);
`);
  fs.chmodSync(bridge, 0o755);
  return bridge;
}


test("MpvEngine: open → observe → command → honest close, with a fake mpv", async () => {
  const server = new FakeMpvServer();
  server.handlers.set("loadfile", () => ({}));
  await server.start();

  const sent = [];
  const inputEvents = [];
  const fakeWindow = {
    isDestroyed: () => false,
    getNativeWindowHandle: () => Buffer.from([0x11, 0x22, 0x33, 0x00]),
    once: () => {},
    on: (name, fn) => inputEvents.push([name, fn]),
    removeListener: () => {},
    webContents: { on: (name, fn) => inputEvents.push(["wc:" + name, fn]), removeListener: () => {} },
  };
  const engine = new MpvEngine({
    getWindow: () => fakeWindow,
    backendInfo: () => null, // no backend: reporting must no-op, not crash
    sendToRenderer: (channel, payload) => sent.push({ channel, payload }),
  });

  const bridge = makeBridge(server);
  process.env.JMDB_MPV_PATH = bridge;
  _resetDetectionCacheForTests();

  try {
    const opened = await engine.open({
      path: "/tmp/movie.mkv",
      fileExists: true,
      url: "/api/stream/1",
      start: 0,
      duration: 600,
      volume: 80,
      title: "Night Runner",
      sessionId: null, // no backend session → reporting no-ops
      mediaType: "movie",
      mediaId: 1,
      subtitles: [{ path: "/tmp/movie.srt", label: "English" }],
      subtitleLanguage: "",
      queue: [
        { media_type: "movie", media_id: 1, title: "Night Runner", current: true },
        { media_type: "movie", media_id: 2, title: "Cosmic Drift" },
      ],
      autoplayNext: false,
      seekStep: 10,
      volumeStep: 5,
    });

    assert.strictEqual(opened.ok, true, `engine started: ${opened.error || ""}`);
    assert.strictEqual(engine.state.title, "Night Runner");
    assert.strictEqual(engine.state.volume, 80);

    // commands reach mpv
    await engine.command("toggle-play");
    await engine.command("seek", 120);
    await new Promise((resolve) => setTimeout(resolve, 80));
    const names = server.commands.map((c) => c.name);
    assert.ok(names.includes("loadfile"), "media loaded over IPC");
    assert.ok(names.includes("cycle"), "toggle-play cycles pause");
    assert.ok(names.includes("seek"), "absolute seek issued");
    assert.ok(names.includes("observe_property"), "properties observed");

    // property events update state
    server.push({ event: "property-change", id: 1, name: "pause", data: true });
    server.push({ event: "property-change", id: 2, name: "time-pos", data: 42.5 });
    server.push({ event: "property-change", id: 4, name: "duration", data: 600 });
    server.push({
      event: "property-change", id: 99, name: "track-list", data: [
        { id: 1, type: "audio", title: "5.1", lang: "eng", selected: true },
        { id: 2, type: "sub", lang: "eng" },
      ],
    });
    await new Promise((resolve) => setTimeout(resolve, 120));
    assert.strictEqual(engine.state.paused, true);
    assert.strictEqual(engine.state.position, 42.5);
    assert.strictEqual(engine.state.duration, 600);
    assert.strictEqual(engine.trackList.length, 2);

    // queue navigation is real
    assert.strictEqual(engine.hasNext().title, "Cosmic Drift");
    assert.strictEqual(engine.hasPrev(), null);

    await engine.command("set-subtitle-track", 2);
    const setSid = server.commands.find((c) => c.name === "set" && c.args[0] === "sid");
    assert.ok(setSid, "subtitle selection issues a real set sid");
    assert.strictEqual(setSid.args[1], 2);
    await engine.command("set-audio-track", 0);
    const setAid = server.commands.filter((c) => c.name === "set" && c.args[0] === "aid").pop();
    assert.strictEqual(setAid.args[1], "no", "audio 'Off' maps to aid=no");

    // teardown tells the renderer and stops cleanly
    await engine.command("close");
    assert.ok(sent.some((s) => s.channel === "mpv:closed"), "renderer learns the player closed");
    assert.strictEqual(engine.active, false);
    assert.strictEqual(engine.child, null);
    assert.strictEqual(engine.client, null);
  } finally {
    await engine.closeInternal("test-done", { skipReport: true }).catch(() => {});
    fs.unlinkSync(bridge);
    delete process.env.JMDB_MPV_PATH;
    _resetDetectionCacheForTests();
    await server.stop();
  }
});

test("MpvEngine: a file mpv refuses reports the real error, not a hang", async () => {
  const server = new FakeMpvServer();
  server.handlers.set("loadfile", () => ({ __error: "error: failed to open file" }));
  await server.start();

  const bridge = makeBridge(server);
  process.env.JMDB_MPV_PATH = bridge;
  _resetDetectionCacheForTests();

  const engine = new MpvEngine({
    getWindow: () => ({ isDestroyed: () => false, getNativeWindowHandle: () => Buffer.from([1, 0, 0, 0]) }),
    backendInfo: () => null,
    sendToRenderer: () => {},
  });
  try {
    const opened = await engine.open({ path: "/tmp/broken.mkv", fileExists: true, start: 0, volume: 100, title: "Broken" });
    assert.strictEqual(opened.ok, false);
    assert.match(opened.error, /refused the file/);
  } finally {
    await engine.closeInternal("test-done", { skipReport: true }).catch(() => {});
    fs.unlinkSync(bridge);
    delete process.env.JMDB_MPV_PATH;
    _resetDetectionCacheForTests();
    await server.stop();
  }
});
