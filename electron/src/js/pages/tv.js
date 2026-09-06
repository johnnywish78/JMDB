import { api } from "../api.js";
import { el, icon } from "../ui.js";
import { posterCard } from "../components.js";
import { navigate } from "../router.js";

export default async function render(container, route) {
  const params = route.params;
  const state = {
    page: Number(params.get("page") || 0),
    sort: params.get("sort") || "title",
    query: params.get("q") || "",
    unwatched: params.get("unwatched") === "1",
    favorites: params.get("favorites") === "1",
  };

  const [listData, genreData] = await Promise.all([
    api.get(`/api/library/tv?${queryString(state)}`),
    api.get("/api/genres"),
  ]);

  const head = el("div", { class: "page-head" },
    el("div", {},
      el("h1", {}, "TV Shows"),
      el("div", { class: "sub" }, `${listData.total} show${listData.total === 1 ? "" : "s"}`)),
    el("div", { class: "spacer" }));

  const searchInput = el("input", { class: "input", type: "search", placeholder: "Filter by title…", value: state.query, style: { width: "200px" } });
  searchInput.addEventListener("input", debounceFn(() => { state.query = searchInput.value; state.page = 0; reload(); }));

  const sortSelect = el("select", { class: "select" },
    el("option", { value: "title" }, "Title"),
    el("option", { value: "year", selected: state.sort === "year" ? "selected" : null }, "First aired"),
    el("option", { value: "rating", selected: state.sort === "rating" ? "selected" : null }, "Rating"),
    el("option", { value: "added", selected: state.sort === "added" ? "selected" : null }, "Recently added"));
  sortSelect.addEventListener("change", () => { state.sort = sortSelect.value; state.page = 0; reload(); });

  const unwatchedChip = el("button", { class: `chip ${state.unwatched ? "active" : ""}` }, "Unwatched only");
  unwatchedChip.addEventListener("click", () => { state.unwatched = !state.unwatched; unwatchedChip.classList.toggle("active", state.unwatched); state.page = 0; reload(); });
  const favoritesChip = el("button", { class: `chip ${state.favorites ? "active" : ""}` }, "Favorites");
  favoritesChip.addEventListener("click", () => { state.favorites = !state.favorites; favoritesChip.classList.toggle("active", state.favorites); state.page = 0; reload(); });

  head.append(searchInput, sortSelect, unwatchedChip, favoritesChip);
  container.append(head);

  const grid = el("div", { class: "grid" });
  container.append(grid);

  function renderRows(data) {
    grid.replaceChildren();
    for (const show of data.items || []) {
      grid.append(posterCard(show, {
        onOpen: () => navigate(`/show/${show.id}`),
        favorite: async () => {
          await api.post(`/api/media/tv_show/${show.id}/favorite`, {});
          reload();
        },
        watchlist: async () => {
          await api.post(`/api/media/tv_show/${show.id}/watchlist`, {});
          reload();
        },
      }));
    }
    if (!grid.children.length) {
      grid.append(el("div", { class: "empty", style: { gridColumn: "1 / -1" } },
        icon("tv"), el("h3", {}, "No shows match"), el("p", {}, "Try clearing the filters, or add more media locations and scan again.")));
    }
    const totalPages = Math.max(1, Math.ceil(data.total / data.per_page));
    if (totalPages > 1) {
      container.append(el("div", { class: "pager" },
        el("button", { class: "btn small", disabled: state.page === 0 ? "disabled" : null, onclick: () => { state.page -= 1; reload(); } }, "Previous"),
        el("span", { class: "info" }, `Page ${state.page + 1} of ${totalPages}`),
        el("button", { class: "btn small", disabled: state.page >= totalPages - 1 ? "disabled" : null, onclick: () => { state.page += 1; reload(); } }, "Next")));
    }
  }

  async function reload() {
    const data = await api.get(`/api/library/tv?${queryString(state)}`);
    history.replaceState(null, "", `#/tv?${queryString(state)}`);
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
