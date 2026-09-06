"use strict";
/** Python backend lifecycle: spawn (or attach), wait for health, shut down.
 *
 * Modes:
 *  - JMDB_BACKEND_URL set  → attach to an externally started backend
 *    (run.py does this: it runs uvicorn in-process). Token comes from
 *    JMDB_BACKEND_TOKEN.
 *  - JMDB_BACKEND_CMD set  → run that command (packaged builds: the
 *    PyInstaller'd backend executable + args).
 *  - otherwise              → spawn `python -m app.api` from the repo root
 *    (development), with a free port and a token file.
 */
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const START_TIMEOUT_MS = 45000;
const STOP_TIMEOUT_MS = 8000;

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

function fetchJson(url) {
  return fetch(url).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
}

class BackendProcess {
  constructor() {
    this.url = null;
    this.token = null;
    this.child = null;
    this.tokenFile = null;
  }

  async start() {
    if (process.env.JMDB_BACKEND_URL) {
      this.url = process.env.JMDB_BACKEND_URL.replace(/\/$/, "");
      this.token = process.env.JMDB_BACKEND_TOKEN || "";
      await this.waitForHealth();
      return { url: this.url, token: this.token };
    }

    const port = await freePort();
    this.tokenFile = path.join(os.tmpdir(), `jmdb-token-${port}.json`);

    let command, args, cwd;
    if (process.env.JMDB_BACKEND_CMD) {
      // packaged: full command line, {port} and {token_file} substituted
      const template = process.env.JMDB_BACKEND_CMD.split(" ");
      command = template[0];
      args = template
        .slice(1)
        .map((part) =>
          part
            .replace("{port}", String(port))
            .replace("{token_file}", this.tokenFile)
        );
      cwd = process.env.JMDB_BACKEND_CWD || process.cwd();
    } else {
      command = process.env.JMDB_PYTHON || "python3";
      args = ["-m", "app.api", "--port", String(port), "--token-file", this.tokenFile];
      cwd = REPO_ROOT;
    }

    this.child = spawn(command, args, {
      cwd,
      env: { ...process.env, JMDB_ELECTRON: "1" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    this.child.stdout.on("data", (chunk) => process.stdout.write(`[backend] ${chunk}`));
    this.child.stderr.on("data", (chunk) => process.stderr.write(`[backend] ${chunk}`));
    this.child.on("exit", (code, signal) => {
      if (this.child && !this._stopping) {
        process.stderr.write(`[backend] exited unexpectedly code=${code} signal=${signal}\n`);
      }
      this.child = null;
    });

    this.url = `http://127.0.0.1:${port}`;
    await this.waitForHealth();
    this.token = this.readTokenFile();
    return { url: this.url, token: this.token };
  }

  async waitForHealth() {
    const deadline = Date.now() + START_TIMEOUT_MS;
    let lastError = null;
    while (Date.now() < deadline) {
      if (this.child && this.child.exitCode !== null && !process.env.JMDB_BACKEND_URL) {
        throw new Error(`backend process exited with code ${this.child.exitCode}`);
      }
      try {
        await fetchJson(`${this.url}/api/health`);
        return;
      } catch (error) {
        lastError = error;
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
    }
    throw new Error(`backend did not become healthy: ${lastError}`);
  }

  readTokenFile() {
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
      try {
        const data = JSON.parse(fs.readFileSync(this.tokenFile, "utf-8"));
        if (data.token) return data.token;
      } catch {
        /* not written yet */
      }
      // eslint-disable-next-line no-await-in-loop
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
    }
    throw new Error("backend never wrote its token file");
  }

  async stop() {
    this._stopping = true;
    if (!this.child) return;
    const child = this.child;
    await new Promise((resolve) => {
      const timer = setTimeout(() => {
        child.kill("SIGKILL");
        resolve();
      }, STOP_TIMEOUT_MS);
      child.once("exit", () => {
        clearTimeout(timer);
        resolve();
      });
      child.kill("SIGTERM");
    });
    this.child = null;
  }

  kill() {
    if (this.child) {
      this._stopping = true;
      this.child.kill("SIGKILL");
      this.child = null;
    }
  }
}

module.exports = { BackendProcess, freePort };
