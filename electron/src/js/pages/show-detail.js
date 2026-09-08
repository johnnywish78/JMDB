import { api, artUrl } from "../api.js";
import { el, icon, formatRuntime, yearOf, toast } from "../ui.js";
import { hero, factBox, personCard, section, posterCard } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";
import { metadataSourceBadge } from "./movie-detail.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const show = await api.get(`/api/shows/${id}`);

  const facts = [];
  if (yearOf(show.first_air_date)) facts.push(el("span", { class: "badge" }, yearOf(show.first_air_date)));
  if (show.status) facts.push(el("span", { class: "badge outline" }, show.status));
  if (show.rating) facts.push(el("span", { class: "badge accent" }, `★ ${(Number(show.rating) || 0).toFixed(1)}`));
  facts.push(el("span", { class: "badge" }, `${show.season_count} season${show.season_count === 1 ? "" : "s"}`));
  facts.push(el("span", { class: "badge" }, `${show.episode_count} episodes`));
  if (show.watched_count) facts.push(el("span", { class: "badge good" }, `${show.watched_count} watched`));

  const actions = [];
  const next = show.next_episode;
  if (next && next.file_path) {
    actions.push(el("button", {
      class: "btn primary play-btn",
      onclick: () => openPlayer({ mediaType: "episode", mediaId: next.id, context: { tv_show_id: show.id } }),
    }, icon("play"), next.position_seconds ? `Resume S${next.season_number}E${next.episode_number}` : `Play S${next.season_number}E${next.episode_number}`));
  }
  actions.push(el("button", {
    class: `mark-btn ${show.is_favorite ? "on" : ""}`,
    onclick: async () => { await api.post(`/api/media/tv_show/${show.id}/favorite`, {}); navigate(`/show/${show.id}`); },
  }, icon("heart"), "Favorite"));
  actions.push(el("button", {
    class: `mark-btn ${show.in_watchlist ? "on" : ""}`,
    onclick: async () => { await api.post(`/api/media/tv_show/${show.id}/watchlist`, {}); navigate(`/show/${show.id}`); },
  }, icon("bookmark"), "Watchlist"));
  actions.push(el("button", {
    class: "mark-btn",
    title: "Mark every episode of this show as watched",
    onclick: async () => {
      await api.post(`/api/media/tv_show/${show.id}/watched`, {});
      toast("Show marked as watched", "success");
      navigate(`/show/${show.id}`);
    },
  }, icon("clock"), "Mark all watched"));

  container.append(hero({
    title: show.title,
    overview: show.overview,
    backdrop_path: show.backdrop_path || show.poster_path,
  }, { facts, actions }));

  const layout = el("div", { class: "detail-layout" });
  const poster = el("div", { class: "detail-poster" });
  if (show.poster_path) {
    const img = el("img", { alt: "", src: artUrl(show.poster_path, "poster") });
    img.addEventListener("error", () => img.remove());
    poster.append(img);
  } else poster.append(icon("tv"));

  const info = el("div", {});
  info.append(el("div", { class: "facts-grid" },
    factBox("First aired", show.first_air_date || "—"),
    factBox("Status", show.status || "—"),
    factBox("Seasons", show.season_count ?? "—"),
    factBox("Episodes", `${show.episode_count ?? 0} (${show.watched_count ?? 0} watched)`),
    factBox("Rating", show.rating ? `${(Number(show.rating) || 0).toFixed(1)} / 10` : "—"),
    factBox("Networks", (show.networks || []).join(", ") || "—")));

  if (show.overview) {
    info.append(el("div", { class: "section" },
      el("div", { class: "section-head" }, el("h2", {}, "Overview")),
      el("p", { style: { color: "var(--text-dim)", lineHeight: "1.7", margin: "0" } }, show.overview)));
  }

  // next up callout
  if (next) {
    info.append(el("div", { class: "section" },
      el("div", { class: "section-head" }, el("h2", {}, "Next up")),
      el("div", { class: "episode-row" },
        el("div", { class: "ep-num" }, next.episode_number),
        el("div", {},
          el("div", { style: { fontWeight: 600 } }, `S${next.season_number} · Episode ${next.episode_number}`),
          el("div", { style: { color: "var(--text-dim)", fontSize: "12.5px" } },
            next.title || "Untitled",
            next.position_seconds ? ` · resume at ${formatRuntime(next.position_seconds)}` : "",
            next.watched ? " · watched" : "")),
        el("div", { class: "ep-side" },
          next.file_path
            ? el("button", { class: "btn small primary", onclick: () => openPlayer({ mediaType: "episode", mediaId: next.id, context: { tv_show_id: show.id } }) }, "Play")
            : el("span", { class: "badge outline" }, "No file")))));
  }

  // seasons
  const seasons = show.seasons || [];
  const seasonCards = seasons.map((season) => {
    const card = posterCard({
      title: season.title || `Season ${season.season_number}`,
      year: season.air_date ? String(season.air_date).slice(0, 4) : "",
      poster_path: season.poster_path || show.poster_path,
    }, { onOpen: () => navigate(`/season/${season.id}`) });
    return card;
  });
  info.append(section("Seasons", seasonCards, { emptyLabel: "No seasons found" }));

  if ((show.credits || []).length) {
    info.append(section("Cast", show.credits.map((credit) =>
      personCard(credit, { onOpen: () => navigate(`/person/${credit.person_id}`) }))));
  }

  info.append(el("div", { class: "chip-row", style: { marginTop: "8px" } },
    el("button", {
      class: "btn small", onclick: async () => {
        toast("Refreshing metadata…", "info");
        try {
          await api.post(`/api/media/tv_show/${show.id}/metadata/refresh`, {});
        } catch (error) {
          toast(`Refresh failed: ${error.message}`, "error");
        }
      },
    }, icon("refresh"), "Refresh metadata"),
    metadataSourceBadge(show)));

  layout.append(poster, info);
  container.append(layout);
}
