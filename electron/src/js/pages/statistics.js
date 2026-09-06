import { api } from "../api.js";
import { el, formatRuntime } from "../ui.js";
import { factBox } from "../components.js";

export default async function render(container) {
  const data = await api.get("/api/statistics");
  const overview = data.overview || {};

  container.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Statistics"),
      el("div", { class: "sub" }, "Your library at a glance"))));

  const cards = [
    ["Movies", overview.movies],
    ["TV shows", overview.tv_shows],
    ["Episodes", overview.episodes],
    ["Artists", overview.artists],
    ["Albums", overview.albums],
    ["Tracks", overview.tracks],
    ["People", overview.people],
    ["Files", overview.files],
    ["Watch time", formatRuntime(overview.watch_seconds || 0)],
    ["Watched movies", overview.watched_movies],
    ["Watched episodes", overview.watched_episodes],
    ["Favorites", overview.favorite_count],
    ["Watchlist", overview.watchlist_count],
    ["Sessions", overview.playback_sessions],
    ["Missing files", overview.missing_files],
    ["Artwork cached", overview.artwork_cached],
  ];
  const grid = el("div", { class: "stat-grid" });
  for (const [label, value] of cards) grid.append(factBox(label, value ?? "—"));
  container.append(grid);

  const barsSection = (title, rows, unitFormatter = (v) => v) => {
    if (!rows || !rows.length) return null;
    const max = Math.max(...rows.map((row) => Number(row[1]) || 0), 1);
    const section = el("div", { class: "section" }, el("div", { class: "section-head" }, el("h2", {}, title)));
    const bars = el("div", { class: "bars" });
    for (const [label, value] of rows) {
      bars.append(el("div", { class: "bar-row" },
        el("span", {}, String(label)),
        el("div", { class: "bar" }, el("span", { style: { width: `${((Number(value) || 0) / max) * 100}%` } })),
        el("span", { style: { textAlign: "right", color: "var(--text-dim)" } }, String(unitFormatter(value)))));
    }
    section.append(bars);
    return section;
  };

  container.append(
    barsSection("Top genres", data.top_genres) || el("div"),
    barsSection("Most seen actors", data.top_actors) || el("div"),
    barsSection("Top directors", data.top_directors) || el("div"),
    barsSection("Watch time by month", data.watch_time_by_month, (value) => formatRuntime(value)) || el("div"));
}
