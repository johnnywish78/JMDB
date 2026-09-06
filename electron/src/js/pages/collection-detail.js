import { api } from "../api.js";
import { el, emptyState, toast, promptDialog, confirmDialog } from "../ui.js";
import { posterCard } from "../components.js";
import { navigate } from "../router.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const [collection, moviesData] = await Promise.all([
    api.get(`/api/collections/${id}`),
    api.get(`/api/library/movies?per_page=200&collection_id=${id}`),
  ]);

  const items = moviesData.items || [];

  container.append(el("div", { class: "page-head" },
    el("button", { class: "btn small", onclick: () => navigate("/collections") }, "← Collections"),
    el("div", {},
      el("h1", {}, collection.name || "Collection"),
      el("div", { class: "sub" }, `${items.length} item${items.length === 1 ? "" : "s"}${collection.description ? ` · ${collection.description}` : ""}`)),
    el("div", { class: "spacer" }),
    el("button", {
      class: "btn small", onclick: async () => {
        const query = await promptDialog({ title: "Add movies", body: "Search your movie library by title:", placeholder: "Title…" });
        if (!query) return;
        const results = await api.get(`/api/library/movies?query=${encodeURIComponent(query)}&per_page=20`);
        const target = (results.items || []).find((movie) => !items.some((item) => item.id === movie.id));
        if (!target) { toast("No un-added movie matched", "info"); return; }
        await api.post(`/api/collections/${id}/items`, { media_type: "movie", media_id: target.id });
        navigate(`/collections/${id}`);
      },
    }, "Add movies"),
    el("button", {
      class: "btn small danger", onclick: async () => {
        const sure = await confirmDialog({
          title: `Delete “${collection.name}”?`,
          body: "The collection is removed. Movies stay in your library.",
          confirmLabel: "Delete", danger: true,
        });
        if (sure) { await api.del(`/api/collections/${id}`); navigate("/collections"); }
      },
    }, "Delete")));

  if (!items.length) {
    container.append(emptyState({
      title: "Empty collection",
      body: "Use “Add movies” to search your library and put items into this collection.",
      iconName: "folder",
    }));
    return;
  }

  const grid = el("div", { class: "grid" });
  for (const movie of items) {
    grid.append(posterCard(movie, {
      onOpen: () => navigate(`/movie/${movie.id}`),
      watchlist: async () => {
        await api.post(`/api/media/movie/${movie.id}/watchlist`, {});
        navigate(`/collections/${id}`);
      },
    }));
  }
  container.append(grid);
}
