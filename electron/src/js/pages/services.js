import { api } from "../api.js";
import { el, icon, toast } from "../ui.js";
import { navigate } from "../router.js";
import { brandIcon } from "../brand-icons.js";

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

    // real brand mark for known services; a neutral globe for anything else
    const brand = brandIcon(service.id);
    const iconBox = el("div", { class: "svc-icon", "aria-hidden": "true" }, brand || icon("globe"));
    if (brand && service.icon) iconBox.title = service.name || service.id;
    card.append(
      iconBox,
      el("h3", {}, service.name || service.id),
      el("div", { class: "desc" }, service.description || ""),
      el("div", { class: "note" }, service.url || ""));

    const actions = el("div", { class: "actions" });

    // The Electron Browser Hub is part of this app: when the hub bridge
    // exists and the site doesn't need DRM, open it embedded. The target
    // page owns the tab lifecycle (loading spinner, errors, focus).
    const canEmbed = Boolean(window.jmdb?.hub) && !service.requires_drm;
    // honest labels: the button names what it will ACTUALLY do here
    const primaryLabel = canEmbed ? "Open in Browser Hub"
      : service.requires_drm ? "Open (system browser)"
      : "Open in a browser tab";
    actions.append(el("button", {
      class: "btn primary",
      title: canEmbed ? "Open in a Browser Hub tab"
        : service.requires_drm ? "This site needs DRM — open it in your default web browser"
        : "Open in a new browser tab",
      onclick: async () => {
        if (canEmbed) {
          // the browser page reads ?url= on mount and opens the tab itself —
          // no timing tricks; failures surface as the hub's own error UI
          navigate(`/browser?url=${encodeURIComponent(service.url)}`);
        } else {
          const ok = await openExternally(service.url);
          if (!ok) toast(`Couldn't open ${service.name || service.url}`, "error");
        }
      },
    }, icon("globe"), primaryLabel));

    actions.append(el("button", {
      class: "btn",
      title: "Open in your default web browser",
      onclick: async () => {
        const ok = await openExternally(service.url);
        if (!ok) toast(`Couldn't open ${service.name || service.url}`, "error");
      },
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
    return Boolean(result && result.ok);
  }
  window.open(url, "_blank", "noopener");
  return true;
}
