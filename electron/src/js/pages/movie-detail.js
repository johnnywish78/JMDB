import { api, artUrl } from "../api.js";
import { el, icon, formatRuntime, yearOf, toast, confirmDialog, relativeTime } from "../ui.js";
import { hero, factBox, personCard, section } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const movie = await api.get(`/api/movies/${id}`);
  const state = await api.get(`/api/playback/state/${id}?media_type=movie`).catch(() => null);

  const facts = [];
  if (yearOf(movie.year)) facts.push(el("span", { class: "badge" }, yearOf(movie.year)));
  if (movie.runtime_seconds) facts.push(el("span", { class: "badge outline" }, formatRuntime(movie.runtime_seconds)));
  if (movie.rating) facts.push(el("span", { class: "badge accent" }, `★ ${(Number(movie.rating) || 0).toFixed(1)}`));
  if (movie.certification) facts.push(el("span", { class: "badge outline" }, movie.certification));
  for (const genre of movie.genres || []) facts.push(el("span", { class: "badge" }, genre));

  const actions = [];
  const playable = (movie.files || []).length > 0;
  if (playable) {
    actions.push(el("button", { class: "btn primary play-btn", onclick: () => openPlayer({ mediaType: "movie", mediaId: movie.id }) },
      icon("play"), state && state.position > 10 ? `Resume ${formatRuntime(state.position)}` : "Play"));
  }
  actions.push(el("button", {
    class: `mark-btn ${movie.is_favorite ? "on" : ""}`,
    title: "Favorite",
    onclick: async () => { await api.post(`/api/media/movie/${movie.id}/favorite`, {}); navigate(`/movie/${movie.id}`); },
  }, icon("heart"), "Favorite"));
  actions.push(el("button", {
    class: `mark-btn ${movie.in_watchlist ? "on" : ""}`,
    title: "Watchlist",
    onclick: async () => { await api.post(`/api/media/movie/${movie.id}/watchlist`, {}); navigate(`/movie/${movie.id}`); },
  }, icon("bookmark"), "Watchlist"));
  actions.push(el("button", {
    class: `mark-btn ${movie.watched ? "on" : ""}`,
    onclick: async () => { await api.post(`/api/media/movie/${movie.id}/watched`, {}); navigate(`/movie/${movie.id}`); },
  }, icon("clock"), movie.watched ? "Watched" : "Mark watched"));

  container.append(hero({
    title: movie.title,
    overview: movie.tagline ? `${movie.tagline} — ${movie.overview || ""}` : movie.overview,
    backdrop_path: movie.backdrop_path || movie.poster_path,
  }, { facts, actions }));

  const layout = el("div", { class: "detail-layout" });
  const poster = el("div", { class: "detail-poster" });
  if (movie.poster_path) {
    const img = el("img", { alt: "", src: artUrl(movie.poster_path, "poster") });
    img.addEventListener("error", () => img.remove());
    poster.append(img);
  } else poster.append(icon("film"));

  const info = el("div", {});
  const factsGrid = el("div", { class: "facts-grid" },
    factBox("Released", movie.release_date || yearOf(movie.year)),
    factBox("Runtime", movie.runtime_seconds ? formatRuntime(movie.runtime_seconds) : "—"),
    factBox("Rating", movie.rating ? `${(Number(movie.rating) || 0).toFixed(1)} / 10${movie.vote_count ? ` (${movie.vote_count} votes)` : ""}` : "—"),
    factBox("Languages", movie.languages || "—"),
    factBox("Countries", movie.countries || "—"),
    factBox("Studios", (movie.studios || []).join(", ") || "—"),
    factBox("Your rating", movie.user_rating ? `${movie.user_rating} / 10` : "Not rated"),
    factBox("Added", movie.added_at ? relativeTime(movie.added_at) : "—"));
  info.append(factsGrid);

  if (movie.overview) {
    info.append(el("div", { class: "section" },
      el("div", { class: "section-head" }, el("h2", {}, "Overview")),
      el("p", { style: { color: "var(--text-dim)", lineHeight: "1.7", margin: "0" } }, movie.overview)));
  }

  // files
  const filesBox = el("div", { class: "section" },
    el("div", { class: "section-head" }, el("h2", {}, `Files (${(movie.files || []).length})`)));
  const filesList = el("div", { class: "files-list" });
  for (const file of movie.files || []) {
    filesList.append(el("div", { class: "file-row" },
      el("span", { class: "name", title: file.path }, file.path),
      el("span", { class: "badge outline" }, file.container || ""),
      el("span", { style: { marginLeft: "auto" } }, `${((Number(file.size_bytes) || 0) / 1024 / 1024 / 1024).toFixed(2)} GB`)));
  }
  if (!(movie.files || []).length) {
    filesList.append(el("div", { class: "file-row" }, "No playable file found — check your library location."));
  }
  filesBox.append(filesList);
  info.append(filesBox);

  // credits
  if ((movie.credits || []).length) {
    const cast = movie.credits.filter((credit) => credit.role === "actor");
    const crew = movie.credits.filter((credit) => credit.role !== "actor");
    if (cast.length) {
      info.append(section("Cast", cast.map((credit) =>
        personCard(credit, { onOpen: () => navigate(`/person/${credit.person_id}`) }))));
    }
    if (crew.length) {
      info.append(section("Crew", crew.map((credit) =>
        personCard({ ...credit, name: credit.name, character: credit.job || credit.role }, { onOpen: () => navigate(`/person/${credit.person_id}`) }))));
    }
  }

  // metadata actions
  info.append(el("div", { class: "chip-row", style: { marginTop: "8px" } },
    el("button", {
      class: "btn small", onclick: async () => {
        toast("Refreshing metadata…", "info");
        try {
          await api.post(`/api/media/movie/${movie.id}/metadata/refresh`, {});
        } catch (error) {
          toast(`Refresh failed: ${error.message}`, "error");
        }
      },
    }, icon("refresh"), "Refresh metadata"),
    (movie.trailer_url || "") ? el("a", { class: "btn small", href: movie.trailer_url, target: "_blank", rel: "noreferrer" }, icon("external"), "Trailer") : null));

  layout.append(poster, info);
  container.append(layout);
}
