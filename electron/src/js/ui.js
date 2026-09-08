/** DOM helpers, formatting, toasts, modals. No frameworks. */

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  for (const child of children.flat(9)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const clear = (node) => {
  while (node && node.firstChild) node.removeChild(node.firstChild);
  return node;
};

/* ------------------------------------------------------------ formatting */
export function formatRuntime(seconds) {
  const total = Math.round(Number(seconds) || 0);
  if (!total) return "—";
  const hours = Math.floor(total / 3600);
  const minutes = Math.round((total % 3600) / 60);
  if (hours) return `${hours}h ${minutes.toString().padStart(2, "0")}m`;
  return `${minutes}m`;
}

export function formatClock(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = Math.floor(total % 60);
  const mm = minutes.toString().padStart(2, "0");
  const ss = secs.toString().padStart(2, "0");
  return hours ? `${hours}:${mm}:${ss}` : `${minutes}:${ss}`;
}

export function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

export function yearOf(value) {
  if (!value) return "";
  const match = String(value).match(/\d{4}/);
  return match ? match[0] : "";
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function relativeTime(value) {
  if (!value) return "";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return "";
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return formatDate(value);
}

export function ratingText(rating) {
  if (rating === null || rating === undefined || rating === 0) return "";
  return (Number(rating) || 0).toFixed(1);
}

export const debounce = (fn, wait = 250) => {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
};

/* ------------------------------------------------------------ toasts */
const TOAST_ICON = {
  info: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M12 12v4"/></svg>`,
  success: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>`,
  error: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>`,
};

export function toast(message, kind = "info", durationMs = 3800) {
  const host = document.getElementById("toasts");
  if (!host) return;
  const node = el("div", { class: `toast ${kind}` });
  node.innerHTML = `${TOAST_ICON[kind] || TOAST_ICON.info}<span></span>`;
  node.lastElementChild.textContent = message;
  host.append(node);
  setTimeout(() => node.remove(), durationMs);
}

/* ------------------------------------------------------------ modals */
export function confirmDialog({ title, body, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const root = document.getElementById("modal-root");
    const close = (result) => {
      backdrop.remove();
      resolve(result);
    };
    const backdrop = el(
      "div",
      { class: "modal-backdrop", onclick: (event) => { if (event.target === backdrop) close(false); } },
      el(
        "div",
        { class: "modal", role: "dialog", "aria-modal": "true" },
        el("h3", {}, title),
        el("p", {}, body),
        el(
          "div",
          { class: "row" },
          el("button", { class: "btn", onclick: () => close(false) }, "Cancel"),
          el("button", { class: `btn ${danger ? "danger" : "primary"}`, onclick: () => close(true) }, confirmLabel)
        )
      )
    );
    root.append(backdrop);
  });
}

export function promptDialog({ title, body, value = "", placeholder = "", confirmLabel = "OK" }) {
  return new Promise((resolve) => {
    const root = document.getElementById("modal-root");
    const input = el("input", { class: "input", value, placeholder, style: { width: "100%", marginBottom: "16px" } });
    const close = (result) => {
      backdrop.remove();
      resolve(result);
    };
    const backdrop = el(
      "div",
      { class: "modal-backdrop", onclick: (event) => { if (event.target === backdrop) close(null); } },
      el(
        "div",
        { class: "modal", role: "dialog", "aria-modal": "true" },
        el("h3", {}, title),
        el("p", {}, body),
        input,
        el(
          "div",
          { class: "row" },
          el("button", { class: "btn", onclick: () => close(null) }, "Cancel"),
          el("button", { class: "btn primary", onclick: () => close(input.value) }, confirmLabel)
        )
      )
    );
    root.append(backdrop);
    input.focus();
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") close(input.value);
    });
  });
}

export const ICONS = {
  home: `<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>`,
  film: `<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>`,
  tv: `<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M8 3l4 3 4-3"/>`,
  music: `<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>`,
  users: `<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M17.5 13.5a6.5 6.5 0 0 1 4 6.5"/>`,
  star: `<path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z"/>`,
  heart: `<path d="M12 20.5S3.5 15 3.5 9a4.7 4.7 0 0 1 8.5-2.8A4.7 4.7 0 0 1 20.5 9c0 6-8.5 11.5-8.5 11.5z"/>`,
  clock: `<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>`,
  folder: `<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>`,
  sparkles: `<path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>`,
  chart: `<path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/>`,
  globe: `<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/>`,
  settings: `<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .33 1.76l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.6 1.6 0 0 0-1.76-.33 1.6 1.6 0 0 0-1 1.47V21a2 2 0 1 1-4 0v-.09a1.6 1.6 0 0 0-1-1.47 1.6 1.6 0 0 0-1.77.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.6 1.6 0 0 0 .33-1.77 1.6 1.6 0 0 0-1.47-1H3a2 2 0 1 1 0-4h.09a1.6 1.6 0 0 0 1.47-1 1.6 1.6 0 0 0-.33-1.77l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.6 1.6 0 0 0 1.76.33h.01a1.6 1.6 0 0 0 1-1.47V3a2 2 0 1 1 4 0v.09a1.6 1.6 0 0 0 1 1.47h.01a1.6 1.6 0 0 0 1.76-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.6 1.6 0 0 0-.33 1.76v.01a1.6 1.6 0 0 0 1.47 1H21a2 2 0 1 1 0 4h-.09a1.6 1.6 0 0 0-1.47 1z"/>`,
  play: `<path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none"/>`,
  pause: `<path d="M7 4.5h3.5v15H7zM13.5 4.5H17v15h-3.5z" fill="currentColor" stroke="none"/>`,
  bookmark: `<path d="M6 3.5h12V21l-6-4.2L6 21z"/>`,
  search: `<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>`,
  history: `<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/><path d="M12 7v5l3.5 2"/>`,
  download: `<path d="M12 3v12m0 0l-4.5-4.5M12 15l4.5-4.5"/><path d="M4 20h16"/>`,
  external: `<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M19 13v6a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6"/>`,
  refresh: `<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 3v6h-6"/>`,
  plus: `<path d="M12 5v14M5 12h14"/>`,
  "chevron-left": `<path d="M15 5l-7 7 7 7"/>`,
};

export function icon(name, cls = "icon") {
  const span = el("span", { class: cls });
  span.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
  return span;
}

export function spinner(label = "Loading…") {
  return el("div", { class: "spinner-wrap" },
    el("div", { class: "spinner" }),
    el("div", { style: { marginTop: "12px", color: "var(--text-dim)" } }, label));
}

export function emptyState({ title, body, action = null, iconName = "folder" }) {
  const children = [icon(iconName), el("h3", {}, title), el("p", {}, body)];
  if (action) children.push(action);
  return el("div", { class: "empty" }, ...children);
}
