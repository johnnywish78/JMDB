/**
 * JMDB — API Client
 * Thin wrapper around window.jmdb.api for the renderer.
 */
const API = {
  base: '', // set by app state

  async get(endpoint) {
    const r = await jmdb.api.get(this.base + endpoint);
    if (!r.ok) throw new Error(`API ${endpoint}: ${r.status || r.error}`);
    return r.data;
  },

  async post(endpoint, body) {
    const r = await jmdb.api.post(this.base + endpoint, body);
    if (!r.ok) throw new Error(`API ${endpoint}: ${r.status || r.error}`);
    return r.data;
  },

  async patch(endpoint, body) {
    const r = await jmdb.api.patch(this.base + endpoint, body);
    if (!r.ok) throw new Error(`API ${endpoint}: ${r.status || r.error}`);
    return r.data;
  },

  async delete(endpoint) {
    const r = await jmdb.api.delete(this.base + endpoint);
    if (!r.ok) throw new Error(`API ${endpoint}: ${r.status || r.error}`);
    return r.data;
  },
};

// Artwork helper
async function getArtwork(kind, key) {
  try {
    const r = await API.get(`/api/artwork/${kind}/${encodeURIComponent(key)}`);
    return r.path ? `file://${r.path}` : null;
  } catch { return null; }
}

// Poster URL → local file or placeholder
async function resolvePoster(item) {
  const url = item.poster_path || item.poster_url;
  if (!url) return null;
  if (url.startsWith('http')) {
    // Use TMDB image CDN directly (Electron allows it)
    return url.replace('/w500/', '/w342/');
  }
  if (url.startsWith('file://')) return url;
  return null;
}

async function resolveBackdrop(item) {
  const url = item.backdrop_path || item.backdrop_url;
  if (!url) return null;
  if (url.startsWith('http')) {
    return url.replace('/w780/', '/w1280/');
  }
  if (url.startsWith('file://')) return url;
  return null;
}
