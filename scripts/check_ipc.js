/**
 * Verifies that every IPC channel the renderer preload uses is registered by
 * the Electron main process (and vice-versa for the reverse channel).
 * Pure static analysis — no Electron runtime required.
 *
 * Usage: node scripts/check_ipc.js
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const mainSrc = fs.readFileSync(path.join(root, 'electron', 'main.js'), 'utf8');
const preloadSrc = fs.readFileSync(path.join(root, 'electron', 'preload.js'), 'utf8');

// Channels registered in main
const mainOn = [...mainSrc.matchAll(/ipcMain\.on\(\s*['"]([^'"]+)['"]/g)].map(m => m[1]);
const mainHandle = [...mainSrc.matchAll(/ipcMain\.handle\(\s*['"]([^'"]+)['"]/g)].map(m => m[1]);
const mainChannels = new Set([...mainOn, ...mainHandle]);

// Channels used by preload
const preloadSend = [...preloadSrc.matchAll(/ipcRenderer\.send\(\s*['"]([^'"]+)['"]/g)].map(m => m[1]);
const preloadInvoke = [...preloadSrc.matchAll(/ipcRenderer\.invoke\(\s*['"]([^'"]+)['"]/g)].map(m => m[1]);
const preloadOn = [...preloadSrc.matchAll(/ipcRenderer\.on\(\s*['"]([^'"]+)['"]/g)].map(m => m[1]);

let ok = true;
for (const ch of new Set([...preloadSend, ...preloadInvoke])) {
  if (!mainChannels.has(ch)) { console.log(`MISSING in main: ${ch}`); ok = false; }
}
// main -> renderer channels (webContents.send) must be listened in preload
const mainSend = [...mainSrc.matchAll(/webContents\.send\(\s*['"]([^'"]+)['"]/g)].map(m => m[1]);
for (const ch of mainSend) {
  if (!preloadOn.includes(ch)) { console.log(`NOTE: main sends '${ch}' but preload has no listener`); }
}

console.log('main channels:', [...mainChannels].sort().join(', '));
console.log('preload uses :', [...new Set([...preloadSend, ...preloadInvoke])].sort().join(', '));
console.log(ok ? 'IPC CHECK: PASS' : 'IPC CHECK: FAIL');
process.exit(ok ? 0 : 1);
