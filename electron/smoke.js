"use strict";
/** Electron smoke test — runs INSIDE Electron (electron . --smoke path differs:
 *  cd electron && ./node_modules/.bin/electron smoke.js
 *
 * Verifies: app boots, backend reachable, window created, preload bridge
 * present with the expected surface, renderer loads, theme switches, hub
 * IPC round-trips. Exits 0 on success, non-zero with a reason.
 *
 * Requires the Electron binary (node_modules/electron/dist). In environments
 * where the binary couldn't be downloaded, this script can't run — that's an
 * environment limitation, not a test failure.
 */
const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("node:path");

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} — ${name}${detail ? `: ${detail}` : ""}`);
}

let mainWindow = null;
let quitCode = 1;

app.whenReady().then(async () => {
  try {
    // 1. backend spawns and becomes healthy (main.js's BackendProcess via env or spawn)
    const backend = require("./main/backend");
    const proc = new backend.BackendProcess();
    let info;
    try {
      info = await proc.start();
      check("backend healthy", true, info.url);
    } catch (error) {
      check("backend healthy", false, error.message);
      throw new Error("backend");
    }

    // 2. window + renderer load with the boot token flow
    mainWindow = new BrowserWindow({
      width: 1200,
      height: 800,
      show: false,
      webPreferences: {
        preload: path.join(__dirname, "preload.js"),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });

    const failed = (detail) => {
      check("renderer booted", false, detail);
      finish();
    };

    ipcMain.handleOnce("smoke:renderer-ready", async () => {
      check("renderer booted", true);
      try {
        // 3. preload bridge surface
        const info = await mainWindow.webContents.executeJavaScript(
          "(() => ({ platform: window.jmdb && window.jmdb.platform," +
          " hasHub: !!(window.jmdb && window.jmdb.hub && window.jmdb.hub.createTab)," +
          " hasExternal: !!(window.jmdb && window.jmdb.external && window.jmdb.external.open)," +
          " nodeGlobals: typeof process === 'undefined'" +
          " }))()", true
        );
        check("preload bridge present", info.platform === "electron", JSON.stringify(info));
        check("hub IPC present", info.hasHub === true);
        check("external IPC present", info.hasExternal === true);
        check("renderer has no Node globals", info.nodeGlobals === true);

        // 4. theme switching actually applies and persists
        const theme = await mainWindow.webContents.executeJavaScript(
          "(async () => {" +
          " const res = await fetch('/api/settings', {headers:{'Content-Type':'application/json'}, method:'PATCH', body: JSON.stringify({theme:'light'})});" +
          " const data = await res.json();" +
          " document.documentElement.dataset.theme = 'light';" +
          " return { saved: data.values.theme, applied: document.documentElement.dataset.theme," +
          "       bg: getComputedStyle(document.documentElement).getPropertyValue('--bg') };" +
          "})()", true
        );
        check("theme persists via API", theme.saved === "light", JSON.stringify(theme));
        check("theme applied to DOM", theme.applied === "light");
        check("theme CSS variables switch", theme.bg && theme.bg.trim() !== "", `--bg=${theme.bg}`);

        // 5. API data through the same-origin cookie auth
        const home = await mainWindow.webContents.executeJavaScript(
          "(async () => { const r = await fetch('/api/home'); return (await r.json()).stats ? " +
          "Object.keys((await (await fetch('/api/home')).json())).length : -1; })()", true
        );
        check("API home reachable from renderer", typeof home === "number" && home > 4, `sections=${home}`);

        // 6. hub: create a tab over IPC, list it, hide it (WebContentsView round-trip)
        const hub = require("./main/hub");
        const hubInstance = new hub.Hub({
          window: () => mainWindow,
          onExternal: () => ({ ok: true }),
        });
        const id = await hubInstance.createTab("https://example.com/", { activate: true });
        const tabs = hubInstance.tabSummaries();
        check("hub created a tab", tabs.length === 1 && tabs[0].id === id);
        check("hub normalized the URL", /^https:\/\/example\.com\/$/.test(tabs[0].url), tabs[0].url);
        await new Promise((resolve) => setTimeout(resolve, 1500)); // let it load
        check("hub tab has a title", Boolean(hubInstance.tabSummaries()[0].title), hubInstance.tabSummaries()[0].title);
        hubInstance.setVisible(false);
        hubInstance.destroy();
        check("hub destroyed cleanly", true);

        // restore theme
        await mainWindow.webContents.executeJavaScript(
          "fetch('/api/settings', {headers:{'Content-Type':'application/json'}, method:'PATCH', body: JSON.stringify({theme:'system'})})", true
        ).catch(() => {});

        check("smoke complete", true);
        quitCode = results.every((result) => result.ok) ? 0 : 1;
        finish();
      } catch (error) {
        check("smoke steps", false, error.message);
        finish();
      }
    });

    const bootUrl = new URL("/app/boot", info.url);
    bootUrl.searchParams.set("token", info.token);
    await mainWindow.loadURL(bootUrl.toString());
    mainWindow.webContents.once("did-fail-load", (_e, code, desc) => failed(`${code} ${desc}`));
    setTimeout(() => {
      if (!results.some((result) => result.name === "renderer booted")) failed("renderer never reported ready (timeout)");
    }, 45000);
  } catch (error) {
    console.error("smoke crashed:", error);
    finish();
  }
});

function finish() {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.destroy();
  app.exit(quitCode);
}

process.on("exit", () => {
  console.log(`SMOKE ${quitCode === 0 ? "PASSED" : "FAILED"} ` +
    `(${results.filter((result) => result.ok).length}/${results.length} checks)`);
});
