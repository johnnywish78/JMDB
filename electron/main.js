const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');

let mainWindow = null;

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

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// IPC Handlers
ipcMain.handle('get-backend-port', () => process.env.JMDB_BACKEND_PORT || '8765');

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

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
