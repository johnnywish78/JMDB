/** Reusable presentational components (cards, rows, hero, detail blocks). */
import { el, formatRuntime, yearOf, ratingText, icon, relativeTime } from "./ui.js";
import { artUrl } from "./api.js";

const FALLBACK_POSTER_TEXT = "No artwork yet";

function posterArt(path, kind, fallbackText) {
  const url = artUrl(path, kind);
  const art = el("div", { class: "art" });
  if (url) {
    const img = el("img", { alt: "", loading: "lazy", src: url });
    img.addEventListener("error", () => img.replaceWith(el("div", { class: "title-fallback" }, fallbackText)));
    art.append(img);
  } else {
    art.append(el("div", { class: "title-fallback" }, fallbackText));
  }
  return art;
}

function ratingLine(rating) {
  const text = ratingText(rating);
  return text ? el("span", { class: "rating-star" }, `★ ${text}`) : null;
}

/** Poster card for movie / show (list rows). */
export function posterCard(row, { onOpen, onPlay, favorite, watchlist, watched, progress } = {}) {
  const card = el("article", { class: "poster-card", tabindex: "0", role: "link" });
  const art = posterArt(row.poster_path, "poster", row.title);

  const meta = el("div", { class: "meta" },
    el("div", { class: "t" }, row.title || "Untitled"),
    el("div", { class: "s" },
      yearOf(row.year || row.first_air_date) || "",
      ratingLine(row.rating)));

  const hover = el("div", { class: "hover-actions" });
  if (onPlay) {
    const play = el("button", { class: "mini-btn", title: "Play", onclick: (event) => { event.stopPropagation(); onPlay(); } });
    play.append(icon("play"));
    hover.append(play);
  }
  if (favorite) {
    const heart = el("button", {
      class: `mini-btn ${row.is_favorite ? "on" : ""}`, title: "Favorite",
      onclick: (event) => { event.stopPropagation(); favorite(); },
    });
    heart.append(icon("heart"));
    hover.append(heart);
  }
  if (watchlist) {
    const mark = el("button", {
      class: `mini-btn ${row.in_watchlist ? "on" : ""}`, title: "Watchlist",
      onclick: (event) => { event.stopPropagation(); watchlist(); },
    });
    mark.append(icon("bookmark"));
    hover.append(mark);
  }
  art.append(hover);

  const pct = progress && progress.total > 0 ? Math.min(100, (progress.position / progress.total) * 100) : 0;
  if (pct > 0) art.append(el("div", { class: "progress-bar" }, el("span", { style: { width: `${pct}%` } })));
  if (watched && row.watched) art.append(el("div", { class: "watched-tick", title: "Watched" }));

  card.append(art, meta);
  card.addEventListener("click", () => onOpen && onOpen());
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter") onOpen && onOpen();
  });
  return card;
}

/** Wide card for albums. */
export function albumCard(row, { onOpen } = {}) {
  const card = el("article", { class: "poster-card", tabindex: "0" });
  const art = posterArt(row.cover_path, "poster", row.title);
  art.style.aspectRatio = "1 / 1";
  card.append(
    art,
    el("div", { class: "meta" },
      el("div", { class: "t" }, row.title || "Unknown album"),
      el("div", { class: "s" }, row.artist_name || yearOf(row.year) || "")));
  card.addEventListener("click", () => onOpen && onOpen());
  card.addEventListener("keydown", (event) => { if (event.key === "Enter") onOpen(); });
  return card;
}

export function personCard(person, { onOpen } = {}) {
  const card = el("article", { class: "person-card", tabindex: "0" });
  const art = el("div", { class: "art" });
  const photo = artUrl(person.photo_path, "profile");
  if (photo) {
    const img = el("img", { alt: "", loading: "lazy", src: photo });
    img.addEventListener("error", () => img.remove());
    art.append(img);
  }
  art.append(document.createTextNode((person.name || "?").slice(0, 1)));
  card.append(art, el("div", { class: "t" }, person.name || "Unknown"));
  if (person.character || person.role) {
    card.append(el("div", { class: "s" }, person.character || person.role));
  }
  card.addEventListener("click", () => onOpen && onOpen(person));
  return card;
}

/** Horizontal scroller section. */
export function section(title, cards, { seeAll = null, emptyLabel = null } = {}) {
  const head = el("div", { class: "section-head" },
    el("h2", {}, title),
    seeAll ? el("a", { class: "see-all", href: seeAll }, "See all") : null);
  const scroller = el("div", { class: "hscroll" });
  if (cards.length) scroller.append(...cards);
  else if (emptyLabel) scroller.append(el("div", { style: { color: "var(--text-faint)", padding: "18px 4px", fontSize: "13px" } }, emptyLabel));
  return el("div", { class: "section" }, head, scroller);
}

/** Big cinematic hero for home/detail pages. */
export function hero(data, { actions = [], facts = [] } = {}) {
  const root = el("section", { class: "hero" });
  const imageBox = el("div", { class: `hero-img ${data.backdrop_path ? "" : "no-art"}` });
  if (data.backdrop_path) {
    const img = el("img", { alt: "", src: artUrl(data.backdrop_path, "backdrop") });
    img.addEventListener("error", () => imageBox.classList.add("no-art"));
    imageBox.append(img);
  }
  const body = el("div", { class: "hero-body" },
    el("h1", {}, data.title || "Untitled"),
    facts.length ? el("div", { class: "facts" }, ...facts) : null,
    data.overview ? el("p", { class: "overview" }, data.overview) : null,
    actions.length ? el("div", { class: "actions" }, ...actions) : null);
  root.append(imageBox, body);
  return root;
}

export function factBox(label, value) {
  return el("div", { class: "fact" }, el("div", { class: "k" }, label), el("div", { class: "v" }, value || "—"));
}

/** Continue-watching tile. */
export function continueCard(row, { onOpen }) {
  const pct = row.duration_seconds ? Math.min(100, (row.position_seconds / row.duration_seconds) * 100) : 0;
  const card = el("article", { class: "poster-card", tabindex: "0" });
  const art = posterArt(row.poster_path, "poster", row.title);
  art.style.aspectRatio = "16 / 9";
  art.append(el("div", { class: "progress-bar" }, el("span", { style: { width: `${pct}%` } })));
  card.append(
    art,
    el("div", { class: "meta" },
      el("div", { class: "t" }, row.title || row.show_title || "Untitled"),
      el("div", { class: "s" },
        `${Math.max(0, Math.round((row.duration_seconds - row.position_seconds) / 60))} min left`)));
  card.addEventListener("click", onOpen);
  return card;
}

/** Episode list row. */
export function episodeRow(episode, { onOpen, onPlay, showNumber = true } = {}) {
  const row = el("div", { class: `episode-row ${episode.watched ? "watched" : ""}` });
  const thumb = el("div", { class: "ep-thumb" });
  if (episode.still_path) {
    const img = el("img", { alt: "", loading: "lazy", src: artUrl(episode.still_path, "still") });
    img.addEventListener("error", () => img.remove());
    thumb.append(img);
  } else thumb.append(icon("tv"));
  const label = episode.title && episode.title.trim()
    ? episode.title
    : `Episode ${episode.episode_number}`;
  row.append(
    showNumber ? el("div", { class: "ep-num" }, episode.episode_number) : null,
    thumb,
    el("div", {},
      el("div", { class: "t" }, label),
      el("div", { class: "s" },
        [
          episode.runtime_seconds ? formatRuntime(episode.runtime_seconds) : "",
          episode.position_seconds ? `Resumed at ${Math.round(episode.position_seconds / 60)}m` : "",
        ].filter(Boolean).join(" · ") || (episode.air_date ? `Aired ${episode.air_date}` : ""))),
    el("div", { class: "ep-side" },
      episode.file_path
        ? (() => {
            const button = el("button", { class: "mini-btn", title: "Play", onclick: (event) => { event.stopPropagation(); onPlay(); } });
            button.append(icon("play"));
            button.style.width = "32px";
            button.style.height = "32px";
            return button;
          })()
        : el("span", { class: "badge outline" }, "No file"),
      episode.watched ? el("span", { class: "badge good" }, "Watched") : null));
  row.addEventListener("click", onOpen);
  return row;
}

/** Music track row. */
export function trackRow(track, { index, onPlay, active = false } = {}) {
  const row = el("div", { class: "track-row", tabindex: "0" });
  const play = el("button", { class: "play-overlay", title: "Play", onclick: () => onPlay() });
  play.append(icon("play"));
  row.append(
    el("div", { class: "num" }, active ? "▶" : index),
    play,
    el("div", { style: { flex: "1", minWidth: "0" } },
      el("div", { class: "t" }, track.title || "Untitled"),
      el("div", { class: "s" }, track.artist_name || "")),
    el("div", { class: "dur" }, track.duration_seconds ? formatRuntime(track.duration_seconds) : ""));
  row.addEventListener("keydown", (event) => { if (event.key === "Enter") onPlay(); });
  return row;
}

export function listCard({ title, meta, onOpen, onRename, onDelete }) {
  const card = el("article", { class: "collection-card", tabindex: "0" });
  card.append(el("h3", {}, title), el("div", { class: "meta" }, meta));
  const actions = el("div", { class: "meta", style: { display: "flex", gap: "8px" } });
  if (onRename) actions.append(el("button", { class: "mark-btn", onclick: (e) => { e.stopPropagation(); onRename(); } }, "Rename"));
  if (onDelete) actions.append(el("button", { class: "mark-btn", onclick: (e) => { e.stopPropagation(); onDelete(); } }, "Delete"));
  card.append(actions);
  card.addEventListener("click", onOpen);
  return card;
}

export function historyRow(entry, { onOpen }) {
  return el("div", { class: "history-item", onclick: onOpen },
    icon(entry.media_type === "episode" ? "tv" : entry.media_type === "track" ? "music" : "film"),
    el("div", { style: { minWidth: "0" } },
      el("div", { class: "t", style: { fontWeight: "600" } }, entry.title || "Untitled"),
      el("div", { class: "s", style: { color: "var(--text-dim)", fontSize: "12px" } },
        entry.show_title ? `${entry.show_title} · ` : "")),
    el("div", { class: "when" }, relativeTime(entry.started_at)));
}
