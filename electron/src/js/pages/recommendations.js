import { api } from "../api.js";
import { el, emptyState } from "../ui.js";
import { posterCard } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

export default async function render(container) {
  const data = await api.get("/api/recommendations");
  const items = data.items || [];

  container.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Recommended"),
      el("div", { class: "sub" }, "Based on what you watch, rate and favorite"))));

  if (!items.length) {
    container.append(emptyState({
      title: "No recommendations yet",
      body: "Watch a few movies and episodes, mark favorites — recommendations appear as your history grows.",
      iconName: "sparkles",
    }));
    return;
  }

  const grid = el("div", { class: "grid" });
  for (const movie of items) {
    grid.append(posterCard(movie, {
      onOpen: () => navigate(`/movie/${movie.id}`),
      onPlay: () => openPlayer({ mediaType: "movie", mediaId: movie.id }),
    }));
  }
  container.append(grid);
}
