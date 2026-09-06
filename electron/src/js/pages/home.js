import { api, artUrl } from "../api.js";
import { el, formatClock, icon, formatRuntime, yearOf, emptyState } from "../ui.js";
import { posterCard, albumCard, section, hero, continueCard, factBox } from "../components.js";
import { navigate } from "../router.js";
import { openPlayer } from "../player.js";

export default async function render(container) {
  const data = await api.get("/api/home");
  const hasAnything = (data.recently_added || []).length || (data.recent_episodes || []).length || (data.recent_albums || []).length;

  if (!hasAnything) {
    container.append(emptyState({
      title: "Your library is empty",
      body: "Add a media folder in Settings → Library, then scan it. Movies, TV shows and music will appear here automatically.",
      iconName: "home",
      action: el("button", { class: "btn primary", onclick: () => navigate("/settings") }, "Open settings"),
    }));
    return;
  }

  // hero: first hero row with backdrop, else the best recently added movie
  const heroRow = (data.hero || [])[0]
    || (data.recently_added || []).filter((movie) => movie.poster_path)[0];
  if (heroRow) {
    const isMovie = heroRow.media_type !== "tv_show";
    const heroData = {
      title: heroRow.title,
      overview: heroRow.overview || "",
      backdrop_path: heroRow.backdrop_path || heroRow.poster_path,
    };
    const facts = [];
    if (yearOf(heroRow.year)) facts.push(el("span", { class: "badge" }, yearOf(heroRow.year)));
    if (heroRow.rating) facts.push(el("span", { class: "badge accent" }, `★ ${(Number(heroRow.rating) || 0).toFixed(1)}`));
    facts.push(el("span", { class: "badge outline" }, isMovie ? "Movie" : "TV series"));
    const actions = [];
    if (isMovie) {
      actions.push(el("button", { class: "btn primary play-btn", onclick: () => openPlayer({ mediaType: "movie", mediaId: heroRow.id }) }, icon("play"), "Play"));
      actions.push(el("button", { class: "btn", onclick: () => navigate(`/movie/${heroRow.id}`) }, "Details"));
    } else {
      actions.push(el("button", { class: "btn primary play-btn", onclick: () => navigate(`/show/${heroRow.id}`) }, "Open series"));
    }
    container.append(hero(heroData, { facts, actions }));
  }

  // continue watching
  if ((data.continue_watching || []).length) {
    container.append(section("Continue watching",
      data.continue_watching.map((row) => continueCard(row, {
        onOpen: () => openPlayer({ mediaType: row.media_type, mediaId: row.media_id }),
      }))));
  }

  // recently added movies
  if ((data.recently_added || []).length) {
    container.append(section("Recently added movies",
      data.recently_added.map((movie) => posterCard(movie, {
        onOpen: () => navigate(`/movie/${movie.id}`),
        onPlay: () => openPlayer({ mediaType: "movie", mediaId: movie.id }),
        favorite: () => toggleList("movie", movie.id, "favorite", container),
        watchlist: () => toggleList("movie", movie.id, "watchlist", container),
        progress: null,
      })),
      { seeAll: "#/movies" }));
  }

  // recent episodes
  if ((data.recent_episodes || []).length) {
    container.append(section("New episodes",
      data.recent_episodes.map((episode) => {
        const card = posterCard({
          title: `${episode.show_title} · S${episode.season_number}E${episode.episode_number}`,
          poster_path: episode.still_path || episode.poster_path,
        }, { onOpen: () => navigate(`/episode/${episode.id}`) });
        card.querySelector(".art").style.aspectRatio = "16 / 9";
        return card;
      })));
  }

  // recommended
  if ((data.recommended || []).length) {
    container.append(section("Recommended for you",
      data.recommended.map((movie) => posterCard(movie, {
        onOpen: () => navigate(`/movie/${movie.id}`),
        onPlay: () => openPlayer({ mediaType: "movie", mediaId: movie.id }),
      })),
      { seeAll: "#/recommendations" }));
  }

  // favorites row
  if ((data.favorites || []).length) {
    container.append(section("Favorites",
      data.favorites.map((row) => posterCard(row, {
        onOpen: () => navigate(`/${row.media_type === "tv_show" ? "show" : row.media_type === "episode" ? "episode" : row.media_type === "track" ? "album" : "movie"}/${row.media_id}`),
      })),
      { seeAll: "#/favorites" }));
  }

  // recent albums
  if ((data.recent_albums || []).length) {
    container.append(section("Recent albums",
      data.recent_albums.map((album) => albumCard(album, {
        onOpen: () => navigate(`/album/${album.id}`),
      })),
      { seeAll: "#/music" }));
  }

  // quick stats strip
  const stats = data.stats || {};
  const strip = el("div", { class: "stat-grid", style: { marginTop: "8px" } },
    factBox("Movies", stats.movies ?? "—"),
    factBox("TV episodes", stats.episodes ?? "—"),
    factBox("Albums", stats.albums ?? "—"),
    factBox("Watch time", formatRuntime(stats.watch_seconds || 0)));
  container.append(strip);
}

async function toggleList(mediaType, mediaId, kind, container) {
  try {
    await api.post(`/api/media/${mediaType}/${mediaId}/${kind}`, {});
    const route = { favorite: "favorite", watchlist: "watchlist" }[kind];
    // re-render current page (cheap refresh)
    const current = location.hash || "#/home";
    navigate(current);
  } catch (error) {
    import("../ui.js").then(({ toast }) => toast(`Couldn't update: ${error.message}`, "error"));
  }
}
