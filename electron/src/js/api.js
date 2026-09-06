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
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
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
