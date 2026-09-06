/** App state: settings cache, theme, WebSocket events with reconnect. */
import { api } from "./api.js";

export const store = {
  settings: {},
  appInfo: null,
  listeners: new Map(), // topic -> Set<fn>
  ws: null,
  wsState: "connecting",
};

export function on(topic, callback) {
  if (!store.listeners.has(topic)) store.listeners.set(topic, new Set());
  store.listeners.get(topic).add(callback);
  return () => store.listeners.get(topic).delete(callback);
}

export function emit(topic, payload) {
  const set = store.listeners.get(topic);
  if (set) for (const callback of set) callback(payload);
}

export async function loadSettings() {
  const data = await api.get("/api/settings");
  store.settings = data.values || {};
  applyTheme(store.settings.theme || "system");
  return store.settings;
}

export async function saveSettings(patch) {
  const data = await api.patch("/api/settings", patch);
  store.settings = data.values || {};
  applyTheme(store.settings.theme || "system");
  return store.settings;
}

function systemPrefersDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(theme) {
  const resolved = theme === "system" ? (systemPrefersDark() ? "dark" : "light") : theme;
  document.documentElement.dataset.theme = resolved;
  emit("theme", { theme, resolved });
}

export function toggleTheme() {
  const current = document.documentElement.dataset.theme === "light" ? "light" : "dark";
  const next = current === "dark" ? "light" : "dark";
  saveSettings({ theme: next }).catch(() => applyTheme(next));
}

if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if ((store.settings.theme || "system") === "system") applyTheme("system");
  });
}

/* ------------------------------------------------------------------ WS */
let reconnectDelay = 500;

export function connectEvents() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);
  store.ws = socket;

  socket.onopen = () => {
    store.wsState = "open";
    reconnectDelay = 500;
    emit("ws-state", "open");
  };
  socket.onmessage = (message) => {
    try {
      const payload = JSON.parse(message.data);
      emit("event", payload);
      if (payload && payload.type) emit(payload.type, payload.data || {});
    } catch {
      /* malformed frame */
    }
  };
  socket.onclose = () => {
    store.wsState = "closed";
    emit("ws-state", "closed");
    setTimeout(() => {
      if (store.ws === socket) connectEvents();
    }, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 10000);
  };
  socket.onerror = () => socket.close();
}
