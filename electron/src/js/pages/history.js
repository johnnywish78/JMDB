import { api } from "../api.js";
import { el, emptyState, formatClock, formatDate } from "../ui.js";
import { navigate } from "../router.js";

function routeFor(entry) {
  if (entry.media_type === "episode") return `/episode/${entry.media_id}`;
  if (entry.media_type === "track") return `/album/${entry.media_id}`;
  return `/movie/${entry.media_id}`;
}

export default async function render(container, route) {
  const page = Number(route.params.get("page") || 0);
  const data = await api.get(`/api/history?page=${page}&per_page=50`);
  const items = data.items || [];

  container.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "History"),
      el("div", { class: "sub" }, `${data.total || 0} playback session${(data.total || 0) === 1 ? "" : "s"}`))));

  if (!items.length) {
    container.append(emptyState({
      title: "Nothing played yet",
      body: "Your playback history will show up here once you watch or listen to something.",
      iconName: "history",
    }));
    return;
  }

  const list = el("div", { style: { display: "flex", flexDirection: "column", gap: "6px" } });
  for (const entry of items) {
    list.append(el("div", { class: "episode-row", style: { cursor: "pointer" }, onclick: () => navigate(routeFor(entry)) },
      el("span", { class: "badge outline" }, entry.media_type),
      el("div", {},
        el("div", { style: { fontWeight: 600 } }, entry.title || "Untitled"),
        el("div", { style: { color: "var(--text-dim)", fontSize: "12px" } },
          `${entry.show_title ? entry.show_title + " · " : ""}${formatDate(entry.started_at)} · ` +
          `${formatClock(entry.position_seconds || 0)}${entry.completed ? " · completed" : ""}`)),
      entry.completed ? el("span", { class: "badge good", style: { marginLeft: "auto" } }, "Watched") : el("span", { class: "badge outline", style: { marginLeft: "auto" } }, "Partial")));
  }
  container.append(list);

  const totalPages = Math.max(1, Math.ceil((data.total || 0) / 50));
  if (totalPages > 1) {
    container.append(el("div", { class: "pager" },
      el("button", { class: "btn small", disabled: page === 0 ? "disabled" : null, onclick: () => navigate(`/history?page=${page - 1}`) }, "Previous"),
      el("span", { class: "info" }, `Page ${page + 1} of ${totalPages}`),
      el("button", { class: "btn small", disabled: page >= totalPages - 1 ? "disabled" : null, onclick: () => navigate(`/history?page=${page + 1}`) }, "Next")));
  }
}
