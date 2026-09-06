import { api, artUrl } from "../api.js";
import { el, icon, formatRuntime, toast } from "../ui.js";
import { hero, factBox } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const episode = await api.get(`/api/episodes/${id}`);

  const playable = Boolean(episode.file_path);
  const facts = [
    el("span", { class: "badge" }, `S${episode.season_number} · E${episode.episode_number}`),
    episode.runtime_seconds ? el("span", { class: "badge outline" }, formatRuntime(episode.runtime_seconds)) : null,
    episode.watched ? el("span", { class: "badge good" }, "Watched") : null,
  ].filter(Boolean);

  const actions = [];
  if (playable) {
    actions.push(el("button", {
      class: "btn primary play-btn",
      onclick: () => openPlayer({ mediaType: "episode", mediaId: episode.id, context: { tv_show_id: episode.tv_show_id, season_id: episode.season_id } }),
    }, icon("play"), episode.position_seconds ? `Resume ${formatRuntime(episode.position_seconds)}` : "Play"));
  }
  actions.push(el("button", {
    class: `mark-btn ${episode.watched ? "on" : ""}`,
    onclick: async () => { await api.post(`/api/media/episode/${episode.id}/watched`, {}); navigate(`/episode/${episode.id}`); },
  }, icon("clock"), episode.watched ? "Watched" : "Mark watched"));

  container.append(hero({
    title: episode.title && episode.title.trim() ? episode.title : `Episode ${episode.episode_number}`,
    overview: episode.overview,
    backdrop_path: episode.still_path || episode.show_poster_path,
  }, { facts, actions }));

  const layout = el("div", { class: "detail-layout" });
  const poster = el("div", { class: "detail-poster" });
  if (episode.still_path || episode.show_poster_path) {
    const img = el("img", { alt: "", src: artUrl(episode.still_path || episode.show_poster_path, "still") });
    img.addEventListener("error", () => img.remove());
    poster.style.aspectRatio = "16 / 9";
    poster.append(img);
  } else poster.append(icon("tv"));

  const info = el("div", {});
  info.append(el("div", { class: "facts-grid" },
    factBox("Show", episode.show_title || "—"),
    factBox("Season", episode.season_title || episode.season_number || "—"),
    factBox("Episode", episode.episode_number ?? "—"),
    factBox("Air date", episode.air_date || "—"),
    factBox("Runtime", episode.runtime_seconds ? formatRuntime(episode.runtime_seconds) : "—"),
    factBox("Position", episode.position_seconds ? `${formatRuntime(episode.position_seconds)} / ${formatRuntime(episode.duration_seconds)}` : "—")));

  if (episode.overview) {
    info.append(el("div", { class: "section" },
      el("div", { class: "section-head" }, el("h2", {}, "Overview")),
      el("p", { style: { color: "var(--text-dim)", lineHeight: "1.7", margin: "0" } }, episode.overview)));
  }

  if ((episode.guest_cast || []).length) {
    const { personCard, section } = await import("../components.js");
    info.append(section("Guest cast", episode.guest_cast.map((credit) =>
      personCard(credit, { onOpen: () => navigate(`/person/${credit.person_id}`) }))));
  }

  const filesBox = el("div", { class: "section" },
    el("div", { class: "section-head" }, el("h2", {}, `Files (${(episode.files || []).length})`)));
  for (const file of episode.files || []) {
    filesBox.append(el("div", { class: "file-row" }, el("span", { class: "name", title: file.path }, file.path)));
  }
  if (!(episode.files || []).length) filesBox.append(el("div", { class: "file-row" }, "No playable file."));
  info.append(filesBox);

  info.append(el("div", { class: "chip-row" },
    el("button", { class: "btn small", onclick: () => navigate(`/season/${episode.season_id}`) }, "Open season"),
    el("button", { class: "btn small", onclick: () => navigate(`/show/${episode.tv_show_id}`) }, "Open show")));

  layout.append(poster, info);
  container.append(layout);
}
