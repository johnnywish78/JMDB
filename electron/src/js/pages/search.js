import { api } from "../api.js";
import { el, icon, emptyState } from "../ui.js";
import { posterCard, personCard, albumCard } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

const TYPE_LABELS = {
  movie: "Movies",
  tv_show: "TV shows",
  season: "Seasons",
  episode: "Episodes",
  person: "People",
  artist: "Artists",
  album: "Albums",
  track: "Tracks",
};

function routeFor(row) {
  switch (row.entity_type || row.type) {
    case "movie": return `/movie/${row.id}`;
    case "tv_show": return `/show/${row.id}`;
    case "season": return `/season/${row.id}`;
    case "episode": return `/episode/${row.id}`;
    case "person": return `/person/${row.id}`;
    case "artist": return `/artist/${row.id}`;
    case "album": return `/album/${row.id}`;
    default: return null;
  }
}

export default async function render(container, route) {
  const query = (route.params.get("q") || "").trim();

  const head = el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, query ? `Results for “${query}”` : "Search"),
      el("div", { class: "sub" }, "Movies, TV, people and music in your library")));
  container.append(head);

  if (!query) {
    container.append(emptyState({
      title: "Search your library",
      body: "Type in the search box above (Ctrl+K) and press Enter.",
      iconName: "search",
    }));
    return;
  }

  const data = await api.get(`/api/search?q=${encodeURIComponent(query)}&limit_per_type=24`);
  const total = data.total || 0;
  head.append(el("span", { class: "badge" }, `${total} result${total === 1 ? "" : "s"}`));

  if (!total) {
    container.append(emptyState({
      title: "Nothing found",
      body: `No movies, shows, people or music matched “${query}”. Scanning more folders or refreshing metadata can improve coverage.`,
      iconName: "search",
    }));
    return;
  }

  for (const [type, rows] of Object.entries(data.results || {})) {
    if (!rows || !rows.length) continue;
    const sectionEl = el("div", { class: "section" },
      el("div", { class: "section-head" }, el("h2", {}, TYPE_LABELS[type] || type), el("span", { class: "badge" }, String(rows.length))));
    const grid = el("div", { class: "grid" });
    for (const row of rows) {
      const target = routeFor(row);
      if (type === "person") {
        grid.append(personCard(row, { onOpen: () => navigate(`/person/${row.id}`) }));
      } else if (type === "album") {
        grid.append(albumCard(row, { onOpen: () => navigate(`/album/${row.id}`) }));
      } else if (type === "track") {
        grid.append(el("div", { class: "setting-row", style: { cursor: "pointer" }, onclick: () => openPlayer({ mediaType: "track", mediaId: row.id }) },
          icon("music"),
          el("div", {},
            el("div", { style: { fontWeight: 600 } }, row.title),
            el("div", { style: { color: "var(--text-dim)", fontSize: "12px" } }, row.artist_name || row.album_title || ""))));
      } else {
        grid.append(posterCard(row, {
          onOpen: () => target && navigate(target),
          onPlay: row.entity_type === "movie" ? () => openPlayer({ mediaType: "movie", mediaId: row.id }) : null,
        }));
      }
    }
    sectionEl.append(grid);
    container.append(sectionEl);
  }
}
