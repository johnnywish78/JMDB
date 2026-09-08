"use strict";
/** Control-bar overlay for the embedded mpv engine.
 *
 * Renders the VLC-style chrome (seek bar, transport, volume, speed, audio and
 * subtitle menus with REAL track lists from mpv, subtitle delay, fullscreen,
 * next/prev in the queue, finished state with autoplay countdown). All state
 * is pushed from the engine (mpv property observation); every control issues
 * a real command — nothing here is decorative.
 */
(function () {
  const $ = (id) => document.getElementById(id);

  const state = {
    paused: false, position: 0, duration: 0, volume: 100, muted: false, speed: 1,
    eof: false, seeking: false, buffered: 0, sid: 0, aid: 0, subDelay: 0, audioDelay: 0,
    title: "", finished: false, tracks: { audio: [], subs: [] }, queue: [],
    seekStep: 10, volumeStep: 5, canNext: false, canPrev: false,
    next: null, autoplayNext: false,
  };
  let controlsVisible = true;
  let countdownTimer = null;
  let seekDragging = false;

  function fmt(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
    const total = Math.floor(seconds);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return h > 0 ? h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0")
      : m + ":" + String(s).padStart(2, "0");
  }

  const cmd = (name, arg) => window.ov.command(name, arg).catch(() => {});

  /* ------------------------------------------------------------- rendering */
  function render() {
    $("title").textContent = state.title || "";
    $("cur").textContent = fmt(state.position);
    $("dur").textContent = fmt(state.duration);

    const pct = state.duration ? Math.min(100, (state.position / state.duration) * 100) : 0;
    $("fill").style.width = pct + "%";
    $("knob").style.left = pct + "%";
    const bufPct = state.duration ? Math.min(100, (state.buffered / state.duration) * 100) : 0;
    $("buffered").style.width = Math.max(pct, bufPct) + "%";

    // play/pause icon
    $("playicon").innerHTML = state.paused
      ? '<path d="M8 5v14l11-7z"/>'
      : '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>';
    $("play").title = state.paused ? "Play (Space)" : "Pause (Space)";

    // volume
    $("volume").value = String(Math.round(state.volume));
    $("volume").disabled = state.muted;
    $("volwave").style.opacity = state.muted ? "0" : "1";
    $("mute").title = state.muted ? "Unmute (M)" : "Mute (M)";

    $("speedbtn").textContent = Number(state.speed).toFixed(2).replace(/0$/, "") + "×";
    $("subdelay").textContent = `subs ${state.subDelay >= 0 ? "+" : ""}${Number(state.subDelay).toFixed(2)}s`;

    $("prev").disabled = !state.canPrev;
    $("next").disabled = !state.canNext;

    $("loading").classList.toggle("show", !state.duration && !state.finished);
    $("loading").textContent = state.seeking ? "Seeking…" : !state.duration ? "Opening…" : "Loading…";

    renderMenu($("audiomenu"), state.tracks.audio || [], state.aid, "set-audio-track", "No audio track info yet");
    renderMenu($("submenu"), state.tracks.subs || [], state.sid, "set-subtitle-track", "No subtitle track info yet");

    $("finished").classList.toggle("show", Boolean(state.finished));
    $("nextend").style.display = state.next ? "" : "none";
  }

  function renderMenu(menu, entries, activeId, command, emptyText) {
    menu.textContent = "";
    if (!entries.length) {
      const note = document.createElement("button");
      note.disabled = true;
      note.textContent = emptyText;
      menu.appendChild(note);
      return;
    }
    for (const entry of entries) {
      const button = document.createElement("button");
      const label = document.createElement("span");
      label.textContent = entry.label;
      button.appendChild(label);
      const hint = document.createElement("span");
      hint.className = "hint";
      hint.textContent = entry.id === activeId ? "●" : (entry.default ? "default" : "");
      button.appendChild(hint);
      if (entry.id === activeId) button.classList.add("active");
      button.addEventListener("click", () => {
        cmd(command, entry.id);
        closeMenus();
      });
      menu.appendChild(button);
    }
  }

  /* ------------------------------------------------------------- menus */
  function closeMenus() {
    for (const id of ["audiomenu", "submenu", "speedmenu"]) {
      $(id)?.classList.remove("open");
    }
    cmd("set-pinned", false);
  }
  function toggleMenu(id) {
    const menu = $(id);
    const willOpen = !menu.classList.contains("open");
    closeMenus();
    if (willOpen) {
      menu.classList.add("open");
      cmd("set-pinned", true); // keep the chrome from auto-hiding mid-choice
    }
  }

  function buildSpeedMenu() {
    let menu = $("speedmenu");
    if (!menu) {
      menu = document.createElement("div");
      menu.className = "menu";
      menu.id = "speedmenu";
      $("speedbtn").parentElement.appendChild(menu);
      for (const speed of [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]) {
        const button = document.createElement("button");
        const label = document.createElement("span");
        label.textContent = speed.toFixed(2).replace(/0$/, "") + "×";
        button.appendChild(label);
        button.addEventListener("click", () => { cmd("set-speed", speed); closeMenus(); });
        menu.appendChild(button);
      }
    }
    for (const child of menu.children) {
      child.classList.toggle("active", Math.abs(Number(child.firstChild.textContent) - state.speed) < 0.01);
    }
  }

  /* ------------------------------------------------------------- wiring */
  $("play").addEventListener("click", () => cmd("toggle-play"));
  $("prev").addEventListener("click", () => cmd("prev"));
  $("next").addEventListener("click", () => cmd("next"));
  $("back").addEventListener("click", () => cmd("close"));
  $("close").addEventListener("click", () => cmd("close"));
  $("fs").addEventListener("click", () => cmd("cycle-fullscreen"));
  $("mute").addEventListener("click", () => cmd("toggle-mute"));
  $("replay").addEventListener("click", () => { stopCountdown(); cmd("replay"); });
  $("backend").addEventListener("click", () => { stopCountdown(); cmd("close"); });
  $("nextend").addEventListener("click", () => { stopCountdown(); cmd("next"); });

  $("volume").addEventListener("input", () => cmd("set-volume", Number($("volume").value)));

  $("speedbtn").addEventListener("click", () => { buildSpeedMenu(); toggleMenu("speedmenu"); });
  $("audiobtn").addEventListener("click", () => toggleMenu("audiomenu"));
  $("subbtn").addEventListener("click", () => toggleMenu("submenu"));

  // subtitle delay: two hidden actions exposed through the badge (also J / L)
  $("subdelay").style.cursor = "pointer";
  $("subdelay").title = "Subtitle delay — click: +0.25s, right-click: −0.25s (J / L)";
  $("subdelay").addEventListener("click", () => cmd("sub-delay", 0.25));
  $("subdelay").addEventListener("contextmenu", (event) => {
    event.preventDefault();
    cmd("sub-delay", -0.25);
  });

  /* seek bar: click + drag = REAL absolute seeks */
  const seek = $("seek");
  function seekFromEvent(event) {
    const rect = seek.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    if (state.duration) cmd("seek", ratio * state.duration);
  }
  seek.addEventListener("mousedown", (event) => { seekDragging = true; seekFromEvent(event); });
  window.addEventListener("mousemove", (event) => { if (seekDragging) seekFromEvent(event); });
  window.addEventListener("mouseup", () => { seekDragging = false; });

  /* the transparent surface over the video: click = play/pause,
     double-click = fullscreen, wheel = volume */
  const clickSurface = $("surface");
  let clickTimer = null;
  clickSurface.addEventListener("click", () => {
    if (clickTimer) return; // waiting to see if it's a double-click
    clickTimer = setTimeout(() => { clickTimer = null; cmd("toggle-play"); }, 220);
  });
  clickSurface.addEventListener("dblclick", () => {
    if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
    cmd("cycle-fullscreen");
  });
  clickSurface.addEventListener("wheel", (event) => {
    event.preventDefault();
    const step = state.volumeStep || 5;
    const target = Math.min(130, Math.max(0, (state.volume || 0) + (event.deltaY < 0 ? step : -step)));
    cmd("set-volume", target);
  }, { passive: false });

  // any interaction wakes the chrome; idle fades it (engine hides us)
  for (const eventName of ["mousemove", "mousedown", "keydown"]) {
    window.addEventListener(eventName, () => cmd("show-controls"), { passive: true });
  }

  /* ------------------------------------------------------------- state in */
  window.ov.onState((payload) => {
    // `next`/`autoplayNext` only arrive with the finished push; keep the
    // last value when later updates omit them (position ticks, pause, …)
    const keepNext = state.next;
    Object.assign(state, payload);
    if (payload.next === undefined) state.next = keepNext;
    if (state.finished && state.next && state.autoplayNext) startCountdown();
    if (!state.finished) stopCountdown();
    render();
  });
  window.ov.onControlsVisible((visible) => {
    controlsVisible = visible;
    $("chrome").classList.toggle("hidden", !visible);
    if (!visible) closeMenus();
  });

  /* autoplay-next countdown (8s, cancellable by pausing or any button) */
  function startCountdown() {
    if (countdownTimer) return;
    let remaining = 8;
    const label = $("countdown");
    const tick = () => {
      label.textContent = `Playing next in ${remaining}s…`;
      if (remaining <= 0) {
        stopCountdown();
        cmd("next");
      } else remaining -= 1;
    };
    tick();
    countdownTimer = setInterval(tick, 1000);
  }
  function stopCountdown() {
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = null;
    $("countdown").textContent = "";
  }

  render();
})();
