import { api } from "../api.js";
import { el, icon, emptyState } from "../ui.js";
import { personCard } from "../components.js";
import { navigate } from "../router.js";

export default async function render(container, route) {
  const query = route.params.get("q") || "";
  const page = Number(route.params.get("page") || 0);

  const head = el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "People"),
      el("div", { class: "sub" }, "Cast and crew in your library")),
    el("div", { class: "spacer" }));
  const search = el("input", { class: "input", type: "search", placeholder: "Search people…", value: query, style: { width: "220px" } });
  let timer = null;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => navigate(`/people?q=${encodeURIComponent(search.value)}`), 300);
  });
  head.append(search);
  container.append(head);

  const params = new URLSearchParams({ page: String(page), per_page: "60" });
  if (query) params.set("query", query);
  const data = await api.get(`/api/people?${params}`);

  const grid = el("div", { class: "grid" });
  for (const person of data.items || []) {
    grid.append(personCard(person, { onOpen: () => navigate(`/person/${person.id}`) }));
  }
  if (!grid.children.length) {
    container.append(emptyState({
      title: "No people yet",
      body: "People appear here once your library has metadata with cast and crew. Refresh metadata from a movie or show page to pull credits.",
      iconName: "users",
    }));
    return;
  }
  container.append(grid);

  const totalPages = Math.max(1, Math.ceil(data.total / data.per_page));
  if (totalPages > 1) {
    container.append(el("div", { class: "pager" },
      el("button", { class: "btn small", disabled: page === 0 ? "disabled" : null, onclick: () => navigate(`/people?page=${page - 1}${query ? `&q=${encodeURIComponent(query)}` : ""}`) }, "Previous"),
      el("span", { class: "info" }, `Page ${page + 1} of ${totalPages}`),
      el("button", { class: "btn small", disabled: page >= totalPages - 1 ? "disabled" : null, onclick: () => navigate(`/people?page=${page + 1}${query ? `&q=${encodeURIComponent(query)}` : ""}`) }, "Next")));
  }
}
