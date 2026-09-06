import { api } from "../api.js";
import { el, icon } from "../ui.js";
import { albumCard, personCard } from "../components.js";
import { navigate } from "../router.js";

export default async function render(container, route) {
  const state = {
    type: route.params.get("type") || "albums",
    page: 0,
    query: "",
  };

  const head = el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Music")),
    el("div", { class: "spacer" }));

  const tabs = el("div", { class: "chip-row" });
  for (const [value, label] of [["albums", "Albums"], ["artists", "Artists"], ["tracks", "Tracks"]]) {
    const chip = el("button", { class: `chip ${state.type === value ? "active" : ""}` }, label);
    chip.addEventListener("click", () => {
      state.type = value;
      state.page = 0;
      tabs.querySelectorAll(".chip").forEach((node) => node.classList.remove("active"));
      chip.classList.add("active");
      reload();
    });
    tabs.append(chip);
  }
  const searchInput = el("input", { class: "input", type: "search", placeholder: "Search music…", style: { width: "200px" } });
  searchInput.addEventListener("input", debounceFn(() => { state.query = searchInput.value; state.page = 0; reload(); }));

  head.append(tabs, searchInput);
  container.append(head);

  const grid = el("div", { class: "grid" });
  const list = el("div", { style: { display: "flex", flexDirection: "column", gap: "6px" } });
  container.append(grid, list);

  async function reload() {
    const params = new URLSearchParams({ page: String(state.page), per_page: "60" });
    if (state.query) params.set("query", state.query);
    const data = await api.get(`/api/library/music?type=${state.type}&${params}`);
    grid.replaceChildren();
    list.replaceChildren();
    if (state.type === "albums") {
      for (const album of data.items || []) {
        grid.append(albumCard(album, { onOpen: () => navigate(`/album/${album.id}`) }));
      }
      if (!grid.children.length) list.append(emptyNote("No albums found"));
    } else if (state.type === "artists") {
      for (const artist of data.items || []) {
        grid.append(personCard({ name: artist.name, photo_path: artist.photo_path || "" }, { onOpen: () => navigate(`/artist/${artist.id}`) }));
      }
      if (!grid.children.length) list.append(emptyNote("No artists found"));
    } else {
      const { trackRow } = await import("../components.js");
      const { openPlayer } = await import("../player.js");
      let index = state.page * 60;
      for (const track of data.items || []) {
        index += 1;
        list.append(trackRow(track, {
          index,
          onPlay: () => openPlayer({ mediaType: "track", mediaId: track.id, context: { album_id: track.album_id } }),
        }));
      }
      if (!list.children.length) list.append(emptyNote("No tracks found"));
    }
  }

  function emptyNote(text) {
    return el("div", { class: "empty" }, icon("music"), el("h3", {}, text), el("p", {}, "Scan a Music folder to fill your library."));
  }

  await reload();
}

function debounceFn(fn, wait = 300) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}
