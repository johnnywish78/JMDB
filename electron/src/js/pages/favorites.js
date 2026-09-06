import { api } from "../api.js";
import { el, emptyState } from "../ui.js";
import { posterCard } from "../components.js";
import { navigate } from "../router.js";

function routeFor(row) {
  if (row.media_type === "tv_show") return `/show/${row.media_id}`;
  if (row.media_type === "episode") return `/episode/${row.media_id}`;
  if (row.media_type === "track") return `/album/${row.media_id}`;
  if (row.media_type === "album") return `/album/${row.media_id}`;
  if (row.media_type === "person") return `/person/${row.media_id}`;
  return `/movie/${row.media_id}`;
}

export default async function render(container) {
  const data = await api.get("/api/favorites");
  const items = data.items || [];

  container.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Favorites"),
      el("div", { class: "sub" }, `${items.length} item${items.length === 1 ? "" : "s"}`))));

  if (!items.length) {
    container.append(emptyState({
      title: "No favorites yet",
      body: "Tap the heart on any poster to keep your most-loved movies and shows here.",
      iconName: "heart",
    }));
    return;
  }

  const grid = el("div", { class: "grid" });
  for (const row of items) {
    grid.append(posterCard(row, {
      onOpen: () => navigate(routeFor(row)),
      favorite: async () => {
        await api.post(`/api/media/${row.media_type}/${row.media_id}/favorite`, {});
        navigate("/favorites");
      },
    }));
  }
  container.append(grid);
}
