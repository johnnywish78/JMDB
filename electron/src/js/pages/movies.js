import { api } from "../api.js";
import { el, icon } from "../ui.js";
import { posterCard } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

const SORTS = [
  ["title", "Title"],
  ["year", "Year"],
  ["rating", "Rating"],
  ["added", "Recently added"],
];

export default async function render(container, route) {
  const params = route.params;
  const state = {
    page: Number(params.get("page") || 0),
    sort: params.get("sort") || "title",
    genre: params.get("genre") || "",
    query: params.get("q") || "",
    year_from: params.get("year_from") || "",
    year_to: params.get("year_to") || "",
    min_rating: params.get("min_rating") || "",
    unwatched: params.get("unwatched") === "1",
    favorites: params.get("favorites") === "1",
  };

  const [listData, genreData] = await Promise.all([
    api.get(`/api/library/movies?${queryString(state)}`),
    api.get("/api/genres"),
  ]);

  const head = el("div", { class: "page-head" },
    el("div", {},
      el("h1", {}, "Movies"),
      el("div", { class: "sub" }, `${listData.total} movie${listData.total === 1 ? "" : "s"}`)),
    el("div", { class: "spacer" }));

  // toolbar
  const searchInput = el("input", {
    class: "input", type: "search", placeholder: "Filter by title…", value: state.query,
    style: { width: "200px" },
  });
  searchInput.addEventListener("input", debounceFn(() => {
    state.query = searchInput.value;
    state.page = 0;
    reload();
  }));

  const sortSelect = el("select", { class: "select" },
    ...SORTS.map(([value, label]) => el("option", { value, selected: value === state.sort ? "selected" : null }, label)));
  sortSelect.addEventListener("change", () => { state.sort = sortSelect.value; state.page = 0; reload(); });

  const genreSelect = el("select", { class: "select" },
    el("option", { value: "" }, "All genres"),
    ...(genreData.genres || []).map((genre) =>
      el("option", { value: genre, selected: genre === state.genre ? "selected" : null }, genre)));
  genreSelect.addEventListener("change", () => { state.genre = genreSelect.value; state.page = 0; reload(); });

  const unwatchedChip = el("button", { class: `chip ${state.unwatched ? "active" : ""}` }, "Unwatched only");
  unwatchedChip.addEventListener("click", () => {
    state.unwatched = !state.unwatched;
    unwatchedChip.classList.toggle("active", state.unwatched);
    state.page = 0;
    reload();
  });
  const favoritesChip = el("button", { class: `chip ${state.favorites ? "active" : ""}` }, "Favorites");
  favoritesChip.addEventListener("click", () => {
    state.favorites = !state.favorites;
    favoritesChip.classList.toggle("active", state.favorites);
    state.page = 0;
    reload();
  });

  head.append(searchInput, sortSelect, genreSelect, unwatchedChip, favoritesChip);
  container.append(head);

  const grid = el("div", { class: "grid" });
  container.append(grid);

  function renderRows(data) {
    grid.replaceChildren();
    for (const movie of data.items || []) {
      grid.append(posterCard(movie, {
        onOpen: () => navigate(`/movie/${movie.id}`),
        onPlay: () => openPlayer({ mediaType: "movie", mediaId: movie.id }),
        favorite: async () => {
          await api.post(`/api/media/movie/${movie.id}/favorite`, {});
          reload();
        },
        watchlist: async () => {
          await api.post(`/api/media/movie/${movie.id}/watchlist`, {});
          reload();
        },
        watched: true,
      }));
    }
    if (!grid.children.length) {
      grid.append(el("div", { class: "empty", style: { gridColumn: "1 / -1" } },
        icon("film"), el("h3", {}, "No movies match"), el("p", {}, "Try clearing the filters, or add more media locations and scan again.")));
    }

    // pager
    const totalPages = Math.max(1, Math.ceil(data.total / data.per_page));
    if (totalPages > 1) {
      const pager = el("div", { class: "pager" },
        el("button", { class: "btn small", disabled: state.page === 0 ? "disabled" : null, onclick: () => { state.page -= 1; reload(); } }, "Previous"),
        el("span", { class: "info" }, `Page ${state.page + 1} of ${totalPages}`),
        el("button", { class: "btn small", disabled: state.page >= totalPages - 1 ? "disabled" : null, onclick: () => { state.page += 1; reload(); } }, "Next"));
      container.append(pager);
    }
  }

  async function reload() {
    const data = await api.get(`/api/library/movies?${queryString(state)}`);
    // keep filters visible: update the address bar without re-rendering everything
    history.replaceState(null, "", `#/movies?${queryString(state)}`);
    renderRows(data);
  }

  renderRows(listData);
}

function queryString(state) {
  const params = new URLSearchParams();
  params.set("page", String(state.page));
  params.set("per_page", "60");
  if (state.sort) params.set("sort", state.sort);
  if (state.query) params.set("query", state.query);
  if (state.genre) params.set("genre", state.genre);
  if (state.year_from) params.set("year_from", state.year_from);
  if (state.year_to) params.set("year_to", state.year_to);
  if (state.min_rating) params.set("min_rating", state.min_rating);
  if (state.unwatched) params.set("unwatched_only", "true");
  if (state.favorites) params.set("favorites_only", "true");
  return params.toString();
}

function debounceFn(fn, wait = 300) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}
