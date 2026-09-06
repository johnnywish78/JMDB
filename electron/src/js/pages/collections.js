import { api } from "../api.js";
import { el, emptyState, promptDialog, confirmDialog, toast } from "../ui.js";
import { listCard } from "../components.js";
import { navigate } from "../router.js";

export default async function render(container) {
  const data = await api.get("/api/collections");
  const items = data.items || [];

  const head = el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Collections"),
      el("div", { class: "sub" }, "Group movies and shows however you like")),
    el("div", { class: "spacer" }),
    el("button", { class: "btn primary", onclick: createCollection }, "New collection"));
  container.append(head);

  async function createCollection() {
    const name = await promptDialog({
      title: "New collection",
      body: "Give your collection a name.",
      placeholder: "e.g. Weekend picks",
      confirmLabel: "Create",
    });
    if (!name || !name.trim()) return;
    try {
      await api.post("/api/collections", { name: name.trim() });
      toast("Collection created", "success");
      navigate("/collections");
    } catch (error) {
      toast(`Couldn't create: ${error.message}`, "error");
    }
  }

  if (!items.length) {
    container.append(emptyState({
      title: "No collections",
      body: "Collections are your own lists — “Christmas movies”, “Rewatch with friends”, anything. Create one to get started.",
      iconName: "folder",
      action: el("button", { class: "btn primary", onclick: createCollection }, "New collection"),
    }));
    return;
  }

  const grid = el("div", { class: "grid", style: { gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" } });
  for (const collection of items) {
    grid.append(listCard({
      title: collection.name,
      meta: `${collection.item_count} item${collection.item_count === 1 ? "" : "s"}${collection.description ? ` · ${collection.description}` : ""}`,
      onOpen: () => navigate(`/collections/${collection.id}`),
      onRename: async () => {
        const name = await promptDialog({
          title: "Rename collection", body: "", value: collection.name, confirmLabel: "Rename",
        });
        if (name && name.trim()) {
          await api.patch(`/api/collections/${collection.id}`, { name: name.trim() });
          navigate("/collections");
        }
      },
      onDelete: async () => {
        const sure = await confirmDialog({
          title: `Delete “${collection.name}”?`,
          body: "The collection is removed. The movies and shows inside stay in your library.",
          confirmLabel: "Delete",
          danger: true,
        });
        if (sure) {
          await api.del(`/api/collections/${collection.id}`);
          navigate("/collections");
        }
      },
    }));
  }
  container.append(grid);
}
