const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

// Check if we're running inside Electron
const isElectron = typeof process !== 'undefined' && 
                   process.versions && 
                   process.versions.electron;

let app, BrowserWindow, ipcMain, dialog, shell;

if (isElectron) {
  const electron = require('electron');
  app = electron.app;
  BrowserWindow = electron.BrowserWindow;
  ipcMain = electron.ipcMain;
  dialog = electron.dialog;
  shell = electron.shell;
} else {
  console.error('NOT RUNNING IN ELECTRON - this should not happen');
  process.exit(1);
}

let mainWindow = null;
let mpvProcess = null;
let mpvSocket = null;
let mpvConnection = null;
let mpvBuffer = '';
let mpvRequestId = 0;
const mpvPendingRequests = new Map();

function getMpvSocketPath() {
  return path.join(
    os.tmpdir(),
    `jmdb-mpv-${process.pid}.sock`
  );
}

function cleanupMpvSocket() {
  if (mpvConnection) {
    try {
      mpvConnection.destroy();
    } catch (error) {
      console.error('Failed to destroy MPV IPC connection:', error);
    }
    mpvConnection = null;
  }

  mpvBuffer = '';

  for (const pending of mpvPendingRequests.values()) {
    pending.reject(new Error('MPV IPC connection closed'));
  }
  mpvPendingRequests.clear();

  if (mpvSocket) {
    try {
      if (fs.existsSync(mpvSocket)) {
        fs.unlinkSync(mpvSocket);
      }
    } catch (error) {
      console.error('Failed to remove MPV IPC socket:', error);
    }
    mpvSocket = null;
  }
}

function emitMpvEvent(message) {
  if (
    mainWindow &&
    !mainWindow.isDestroyed() &&
    message &&
    message.event
  ) {
    mainWindow.webContents.send('player:event', message);
  }
}

function handleMpvMessage(message) {
  if (message && message.request_id !== undefined) {
    const pending = mpvPendingRequests.get(message.request_id);

    if (pending) {
      mpvPendingRequests.delete(message.request_id);

      if (message.error && message.error !== 'success') {
        pending.reject(
          new Error(`MPV IPC error: ${message.error}`)
        );
      } else {
        pending.resolve(message);
      }

      return;
    }
  }

  emitMpvEvent(message);
}

function processMpvBuffer() {
  while (true) {
    const newlineIndex = mpvBuffer.indexOf('\n');

    if (newlineIndex === -1) {
      break;
    }

    const line = mpvBuffer.slice(0, newlineIndex).trim();
    mpvBuffer = mpvBuffer.slice(newlineIndex + 1);

    if (!line) {
      continue;
    }

    try {
      const message = JSON.parse(line);
      handleMpvMessage(message);
    } catch (error) {
      console.error('Failed to parse MPV IPC message:', error, line);
    }
  }
}

function connectMpvIpc() {
  if (!mpvSocket) {
    throw new Error('MPV IPC socket is not configured');
  }

  if (mpvConnection && !mpvConnection.destroyed) {
    return Promise.resolve();
  }

  const net = require('net');

  return new Promise((resolve, reject) => {
    const socket = net.createConnection(mpvSocket);

    let settled = false;

    const fail = (error) => {
      if (!settled) {
        settled = true;
        reject(error);
      }
    };

    socket.setEncoding('utf8');

    socket.on('connect', () => {
      mpvConnection = socket;
      mpvBuffer = '';

      if (!settled) {
        settled = true;
        resolve();
      }
    });

    socket.on('data', (data) => {
      mpvBuffer += data;
      processMpvBuffer();
    });

    socket.on('error', (error) => {
      console.error('MPV IPC socket error:', error);

      if (!settled) {
        fail(error);
      }
    });

    socket.on('close', () => {
      if (mpvConnection === socket) {
        mpvConnection = null;
      }

      mpvBuffer = '';

      for (const pending of mpvPendingRequests.values()) {
        pending.reject(new Error('MPV IPC socket closed'));
      }
      mpvPendingRequests.clear();
    });
  });
}

async function waitForMpvSocket(timeoutMs = 5000) {
  const started = Date.now();

  while (Date.now() - started < timeoutMs) {
    if (mpvSocket && fs.existsSync(mpvSocket)) {
      return;
    }

    if (!mpvProcess) {
      throw new Error('MPV process exited before IPC socket became ready');
    }

    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  throw new Error('Timed out waiting for MPV IPC socket');
}

async function stopMpv() {
  cleanupMpvSocket();

  if (mpvProcess) {
    const processToStop = mpvProcess;
    mpvProcess = null;

    try {
      processToStop.kill('SIGTERM');
    } catch (error) {
      console.error('Failed to stop MPV:', error);
    }
  }

  if (mpvSocket) {
    cleanupMpvSocket();
  }
}

async function startMpv(filePath, options = {}) {
  await stopMpv();

  if (!filePath) {
    throw new Error('No media file path supplied');
  }

  const mpvPath = options.mpvPath || '/usr/bin/mpv';

  if (!fs.existsSync(mpvPath)) {
    throw new Error(`MPV executable not found: ${mpvPath}`);
  }

  if (!fs.existsSync(filePath)) {
    throw new Error(`Media file not found: ${filePath}`);
  }

  mpvSocket = getMpvSocketPath();

  const args = [
    '--idle=yes',
    '--force-window=yes',
    '--hwdec=no',
    `--input-ipc-server=${mpvSocket}`,
    '--keep-open=no',
    filePath
  ];

  mpvProcess = spawn(mpvPath, args, {
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  mpvProcess.stdout.on('data', (data) => {
    console.log('[MPV]', data.toString().trim());
  });

  mpvProcess.stderr.on('data', (data) => {
    console.error('[MPV]', data.toString().trim());
  });

  mpvProcess.on('error', (error) => {
    console.error('MPV process error:', error);
    mpvProcess = null;
    cleanupMpvSocket();
  });

  mpvProcess.on('exit', (code, signal) => {
    console.log(`MPV exited: code=${code}, signal=${signal}`);

    mpvProcess = null;
    cleanupMpvSocket();

    if (
      mainWindow &&
      !mainWindow.isDestroyed()
    ) {
      mainWindow.webContents.send('player:event', {
        event: 'end-file',
        reason: signal || (code === 0 ? 'eof' : 'error')
      });
    }
  });

  await waitForMpvSocket();
  await connectMpvIpc();

  return {
    pid: mpvProcess.pid,
    socket: mpvSocket,
    backend: 'mpv'
  };
}

async function sendMpvCommand(command) {
  if (!mpvProcess || !mpvSocket) {
    throw new Error('MPV is not running');
  }

  await connectMpvIpc();

  const requestId = ++mpvRequestId;

  return new Promise((resolve, reject) => {
    mpvPendingRequests.set(requestId, {
      resolve,
      reject
    });

    try {
      mpvConnection.write(
        JSON.stringify({
          command,
          request_id: requestId
        }) + '\n'
      );
    } catch (error) {
      mpvPendingRequests.delete(requestId);
      reject(error);
    }
  });
}

async function getMpvProperty(property) {
  return sendMpvCommand([
    'get_property',
    property
  ]);
}

async function setMpvProperty(property, value) {
  return sendMpvCommand([
    'set_property',
    property,
    value
  ]);
}

async function observeMpvProperty(property, observeId) {
  return sendMpvCommand([
    'observe_property',
    observeId,
    property
  ]);
}

async function unobserveMpvProperty(observeId) {
  return sendMpvCommand([
    'unobserve_property',
    observeId
  ]);
}


function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    title: "JMDB - Johnny's Media Database",
    backgroundColor: "#0a0e17",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webviewTag: true
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  try {
    const nativeHandle = mainWindow.getNativeWindowHandle();
    console.log('[JMDB NATIVE HANDLE]', {
      length: nativeHandle.length,
      hex: nativeHandle.toString('hex')
    });
  } catch (error) {
    console.error('[JMDB NATIVE HANDLE ERROR]', error);
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// IPC Handlers
ipcMain.handle('get-backend-port', () => process.env.JMDB_BACKEND_PORT || '8765');

ipcMain.handle('player:start', async (event, filePath, options = {}) => {
  return startMpv(filePath, options);
});

ipcMain.handle('player:command', async (event, command) => {
  return sendMpvCommand(command);
});

ipcMain.handle('player:get-property', async (event, property) => {
  return getMpvProperty(property);
});

ipcMain.handle('player:set-property', async (event, property, value) => {
  return setMpvProperty(property, value);
});

ipcMain.handle('player:observe-property', async (event, property, observeId) => {
  return observeMpvProperty(property, observeId);
});

ipcMain.handle('player:unobserve-property', async (event, observeId) => {
  return unobserveMpvProperty(observeId);
});

ipcMain.handle('player:stop', async () => {
  await stopMpv();
  return { ok: true };
});

ipcMain.handle('player:status', async () => ({
  running: Boolean(mpvProcess),
  pid: mpvProcess ? mpvProcess.pid : null,
  socket: mpvSocket,
  connected: Boolean(
    mpvConnection &&
    !mpvConnection.destroyed
  ),
  backend: mpvProcess ? 'mpv' : null
}));

ipcMain.handle('get-app-version', () => ({
  electron: process.versions.electron,
  chromium: process.versions.chrome,
  node: process.versions.node
}));

// Handler for opening directory dialog (Add Library)
ipcMain.handle('open-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Media Folder'
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

// Handler for opening file dialog (e.g., for settings or specific files)
ipcMain.handle('open-file', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options || {
    properties: ['openFile'],
    filters: [{ name: 'All Files', extensions: ['*'] }]
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

app.whenReady().then(createWindow);

app.on('before-quit', () => {
  stopMpv();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
