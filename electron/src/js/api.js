/** API client — same-origin fetch against the local backend (cookie auth). */

export class ApiError extends Error {
  constructor(status, detail, url) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
    this.url = url;
  }
}

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = sessionStorage.getItem("jmdb_token");
  if (token && !path.startsWith("/app/")) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  // Tell the backend which frontend is asking, so capabilities like "can
  // this service open embedded?" resolve for THIS client (the Electron
  // Browser Hub always exists here and never depends on PyQt6-WebEngine).
  if (window.jmdb?.platform === "electron") {
    headers["X-JMDB-Frontend"] = "electron";
  }
  const response = await fetch(path, { ...options, headers, body: options.body !== undefined ? JSON.stringify(options.body) : undefined });
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = data.detail || data.message || "";
    } catch {
      /* non-json error body */
    }
    throw new ApiError(response.status, detail, path);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body = {}) => request(path, { method: "POST", body }),
  put: (path, body = {}) => request(path, { method: "PUT", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  del: (path) => request(path, { method: "DELETE" }),
};

/** Build an <img src> for a local artwork path served by /api/artwork. */
export function artUrl(path, kind = "poster") {
  if (!path) return null;
  return `/api/artwork?path=${encodeURIComponent(path)}&kind=${encodeURIComponent(kind)}`;
}

export function streamUrl(fileId) {
  return `/api/stream/${fileId}`;
}
