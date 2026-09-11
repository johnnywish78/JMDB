const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = 18932;

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,

    backgroundColor: "#111111",

    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.loadFile(
    path.join(__dirname, "src", "index.html")
  );
}

ipcMain.handle("jmdb:backend-url", () => {
  return `http://${BACKEND_HOST}:${BACKEND_PORT}`;
});

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
