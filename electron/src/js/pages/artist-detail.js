import { api } from "../api.js";
import { el, icon } from "../ui.js";
import { factBox } from "../components.js";
import { albumCard, section } from "../components.js";
import { navigate } from "../router.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const artist = await api.get(`/api/music/artists/${id}`);

  container.append(el("div", { class: "page-head" },
    el("div", {},
      el("h1", {}, artist.name || "Unknown artist"),
      el("div", { class: "sub" }, artist.disambiguation || ""))));

  const layout = el("div", { class: "detail-layout" });
  const photo = el("div", { class: "detail-poster", style: { aspectRatio: "1 / 1", borderRadius: "50%" } });
  if (artist.photo_path) {
    const img = el("img", { alt: "", src: `/api/artwork?path=${encodeURIComponent(artist.photo_path)}&kind=profile` });
    img.addEventListener("error", () => img.remove());
    photo.append(img);
  } else photo.append(icon("music"));

  const info = el("div", {});
  info.append(el("div", { class: "facts-grid" },
    factBox("Albums", artist.album_count ?? "—"),
    factBox("Genres", (artist.genres || []).join(", ") || "—")));

  if (artist.biography) {
    info.append(el("div", { class: "section" },
      el("div", { class: "section-head" }, el("h2", {}, "About")),
      el("p", { style: { color: "var(--text-dim)", lineHeight: "1.7", margin: "0" } }, artist.biography)));
  }

  info.append(section("Albums", (artist.albums || []).map((album) =>
    albumCard(album, { onOpen: () => navigate(`/album/${album.id}`) }))));

  layout.append(photo, info);
  container.append(layout);
}
