import { api, artUrl } from "../api.js";
import { metadataSourceBadge } from "./movie-detail.js";
import { el, icon } from "../ui.js";
import { factBox } from "../components.js";
import { trackRow } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const album = await api.get(`/api/music/albums/${id}`);

  container.append(el("div", { class: "page-head" },
    el("button", { class: "btn small", onclick: () => navigate(`/artist/${album.artist_id}`) }, `← ${album.artist_name}`),
    el("div", {},
      el("h1", {}, album.title || "Unknown album"),
      el("div", { class: "sub" }, `${album.artist_name || ""}${album.year ? ` · ${album.year}` : ""} · ${album.track_count} tracks`)),
    el("div", { class: "spacer" }),
    el("button", {
      class: "btn primary",
      onclick: () => openPlayer({ mediaType: "track", mediaId: (album.tracks || [])[0]?.id, context: { album_id: album.id } }),
      disabled: (album.tracks || []).length ? null : "disabled",
    }, icon("play"), "Play album")));

  const layout = el("div", { class: "detail-layout" });
  const cover = el("div", { class: "detail-poster", style: { aspectRatio: "1 / 1" } });
  if (album.cover_path) {
    const img = el("img", { alt: "", src: artUrl(album.cover_path, "poster") });
    img.addEventListener("error", () => img.remove());
    cover.append(img);
  } else cover.append(icon("music"));

  const info = el("div", {});
  info.append(el("div", { class: "facts-grid" },
    factBox("Artist", album.artist_name || "—"),
    factBox("Released", album.year || "—"),
    factBox("Tracks", album.track_count ?? "—"),
    factBox("Genres", (album.genres || []).join(", ") || "—")));

  const list = el("div", { style: { display: "flex", flexDirection: "column", gap: "6px", marginTop: "10px" } });
  (album.tracks || []).forEach((track, index) => {
    list.append(trackRow(track, {
      index: index + 1,
      onPlay: () => openPlayer({ mediaType: "track", mediaId: track.id, context: { album_id: album.id } }),
    }));
  });
  if (!(album.tracks || []).length) list.append(el("div", { class: "empty" }, icon("music"), el("h3", {}, "No tracks"), el("p", {}, "Scan the music folder to index this album's files.")));
  info.append(list);
  info.append(el("div", { class: "chip-row", style: { marginTop: "8px" } }, metadataSourceBadge(album)));

  layout.append(cover, info);
  container.append(layout);
}
