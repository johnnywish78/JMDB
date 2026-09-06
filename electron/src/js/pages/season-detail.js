import { api, artUrl } from "../api.js";
import { el, icon, toast, confirmDialog } from "../ui.js";
import { episodeRow, factBox } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const season = await api.get(`/api/seasons/${id}`);
  const episodes = season.episodes || [];

  container.append(el("div", { class: "page-head" },
    el("button", { class: "btn small", onclick: () => navigate(`/show/${season.show_id}`) }, `← ${season.show_title}`),
    el("div", {},
      el("h1", {}, season.title || `Season ${season.season_number}`),
      el("div", { class: "sub" }, `${episodes.length} episode${episodes.length === 1 ? "" : "s"}`)),
    el("div", { class: "spacer" }),
    el("button", {
      class: "btn small",
      onclick: async () => {
        const sure = await confirmDialog({
          title: "Mark the whole season as watched?",
          body: "Every episode in this season will be marked watched.",
          confirmLabel: "Mark watched",
        });
        if (sure) {
          await api.post(`/api/media/season/${season.id}/watched`, {});
          toast("Season marked as watched", "success");
          navigate(`/season/${id}`);
        }
      },
    }, icon("clock"), "Mark season watched")));

  container.append(el("div", { class: "facts-grid" },
    factBox("Show", season.show_title || "—"),
    factBox("Season", season.season_number ?? "—"),
    factBox("Air date", season.air_date || "—")));

  const list = el("div", { style: { display: "flex", flexDirection: "column", gap: "6px", marginTop: "14px" } });
  for (const episode of episodes) {
    list.append(episodeRow(episode, {
      onOpen: () => navigate(`/episode/${episode.id}`),
      onPlay: () => openPlayer({ mediaType: "episode", mediaId: episode.id, context: { season_id: season.id, tv_show_id: season.show_id } }),
    }));
  }
  if (!episodes.length) {
    list.append(el("div", { class: "empty" }, icon("tv"), el("h3", {}, "No episodes"), el("p", {}, "Scan the folder containing this season to index its files.")));
  }
  container.append(list);
}
