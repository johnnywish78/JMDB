import { api, artUrl } from "../api.js";
import { el, icon, formatDate } from "../ui.js";
import { factBox } from "../components.js";
import { posterCard, section } from "../components.js";
import { navigate } from "../router.js";

export default async function render(container, route, params) {
  const id = Number(params[0]);
  const person = await api.get(`/api/people/${id}`);

  container.append(el("div", { class: "page-head" },
    el("div", {},
      el("h1", {}, person.name || "Unknown"),
      el("div", { class: "sub" }, person.place_of_birth || person.disambiguation || ""))));

  const layout = el("div", { class: "detail-layout" });
  const photo = el("div", { class: "detail-poster" });
  if (person.photo_path) {
    const img = el("img", { alt: "", src: artUrl(person.photo_path, "profile") });
    img.addEventListener("error", () => img.remove());
    photo.append(img);
  } else photo.append(icon("users"));

  const info = el("div", {});
  info.append(el("div", { class: "facts-grid" },
    factBox("Born", person.birthday ? formatDate(person.birthday) : "—"),
    factBox("Died", person.deathday ? formatDate(person.deathday) : "—"),
    factBox("Place of birth", person.place_of_birth || "—"),
    factBox("Known for", (person.filmography || []).length ? `${person.filmography.length} credit${person.filmography.length === 1 ? "" : "s"}` : "—")));

  if (person.biography) {
    info.append(el("div", { class: "section" },
      el("div", { class: "section-head" }, el("h2", {}, "Biography")),
      el("p", { style: { color: "var(--text-dim)", lineHeight: "1.7", margin: "0", whiteSpace: "pre-line" } }, person.biography)));
  }

  const byRole = {};
  for (const credit of person.filmography || []) {
    const key = credit.role === "actor" ? "Acting" : credit.role === "director" ? "Directing" : credit.role || "Other";
    (byRole[key] = byRole[key] || []).push(credit);
  }
  for (const [role, credits] of Object.entries(byRole)) {
    info.append(section(role, credits.map((credit) => posterCard({
      title: credit.media_title,
      year: credit.media_year,
      poster_path: credit.poster_path,
    }, {
      onOpen: () => navigate(credit.media_type === "tv_show" ? `/show/${credit.media_id}` : `/movie/${credit.media_id}`),
    }))));
  }

  layout.append(photo, info);
  container.append(layout);
}
