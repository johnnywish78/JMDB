/** Tiny hash router. Routes are registered by app.js. */

const listeners = new Set();

export function navigate(hash) {
  if (location.hash === hash) {
    route(); // re-render same route
  } else {
    location.hash = hash;
  }
}

export function currentRoute() {
  return parse(location.hash);
}

export function parse(hash) {
  const raw = (hash || "").replace(/^#/, "");
  const [pathPart, queryPart] = raw.split("?");
  const params = new URLSearchParams(queryPart || "");
  const segments = pathPart.split("/").filter(Boolean);
  return { path: "/" + segments.join("/"), segments, params, raw };
}

export function onChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

let lastRaw = null;

export function route() {
  const parsed = parse(location.hash);
  if (parsed.raw === lastRaw) return;
  lastRaw = parsed.raw;
  for (const callback of listeners) callback(parsed);
}

window.addEventListener("hashchange", route);
