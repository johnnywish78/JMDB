import { api } from "../api.js";
import { el, icon, toast } from "../ui.js";
import { navigate } from "../router.js";

/** Services page: exactly the four registered services. Each opens INSIDE
 * the Browser Hub (embedded) or in an external browser when the site needs
 * DRM/system features. TV Time is a web tile — it has no public API, and we
 * say so honestly. */
export default async function render(container) {
  const data = await api.get("/api/services");
  const items = data.items || [];

  container.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Services"),
      el("div", { class: "sub" }, "Your streaming and messaging services, opened inside the Browser Hub"))));

  const grid = el("div", { class: "service-grid" });
  for (const service of items) {
    const card = el("article", { class: "service-card", style: { "--svc-accent": service.accent || "var(--accent)" } });
    card.append(
      el("div", { class: "svc-icon" }, service.icon || "◆"),
      el("h3", {}, service.name || service.id),
      el("div", { class: "desc" }, service.description || ""),
      el("div", { class: "note" }, service.url || ""));

    const actions = el("div", { class: "actions" });
    actions.append(el("button", {
      class: "btn primary",
      onclick: async () => {
        if (service.requires_drm) {
          await openExternally(service.url);
        } else if (service.embedded === false) {
          await openExternally(service.url);
        } else {
          navigate("/browser");
          setTimeout(() => {
            if (window.jmdb?.hub) window.jmdb.hub.createTab(service.url);
          }, 250);
        }
      },
    }, icon("globe"), "Open in Browser Hub"));

    actions.append(el("button", {
      class: "btn",
      title: "Open in your default web browser",
      onclick: () => openExternally(service.url),
    }, icon("external"), "External"));

    card.append(actions);
    if (service.notes) card.append(el("div", { class: "note" }, service.notes));
    if (service.id === "tv_time") {
      card.append(el("div", { class: "note" }, "Note: TV Time has no public API — this opens their website; tracking happens there."));
    }
    grid.append(card);
  }
  container.append(grid);
}

async function openExternally(url) {
  if (window.jmdb?.external?.open) {
    const result = await window.jmdb.external.open(url);
    if (!result || !result.ok) toast("Couldn't open the external browser", "error");
  } else {
    window.open(url, "_blank");
  }
}
