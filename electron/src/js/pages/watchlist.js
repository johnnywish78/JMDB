import { api } from "../api.js";
import { el, emptyState } from "../ui.js";
import { posterCard } from "../components.js";
import { navigate } from "../router.js";

function routeFor(row) {
  if (row.media_type === "tv_show") return `/show/${row.media_id}`;
  if (row.media_type === "episode") return `/episode/${row.media_id}`;
  return `/movie/${row.media_id}`;
}

export default async function render(container) {
  const data = await api.get("/api/watchlist");
  const items = data.items || [];

  container.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Watchlist"),
      el("div", { class: "sub" }, `${items.length} item${items.length === 1 ? "" : "s"} to watch`))));

  if (!items.length) {
    container.append(emptyState({
      title: "Watchlist is empty",
      body: "Add movies and shows to your watchlist with the bookmark button so you remember what to watch next.",
      iconName: "bookmark",
    }));
    return;
  }

  const grid = el("div", { class: "grid" });
  for (const row of items) {
    grid.append(posterCard(row, {
      onOpen: () => navigate(routeFor(row)),
      watchlist: async () => {
        await api.post(`/api/media/${row.media_type}/${row.media_id}/watchlist`, {});
        navigate("/watchlist");
      },
    }));
  }
  container.append(grid);
}
