"""User collections service (create/rename/delete/add/remove/reorder)."""
from __future__ import annotations

from app.database.repositories import Repositories
from app.domain.events import EventBus


class CollectionsService:
    def __init__(self, repos: Repositories, events: EventBus) -> None:
        self.repos = repos
        self.events = events

    def list(self) -> list[dict]:
        return self.repos.collections.list()

    def create(self, name: str, description: str = ""):
        if not name.strip():
            raise ValueError("collection name cannot be empty")
        existing = self.repos.collections.get_by_name(name)
        if existing:
            raise ValueError(f"a collection named '{name}' already exists")
        return self.repos.collections.create(name, description)

    def rename(self, collection_id: int, name: str, description: str | None = None) -> None:
        if not name.strip():
            raise ValueError("collection name cannot be empty")
        self.repos.collections.rename(collection_id, name, description)

    def delete(self, collection_id: int) -> None:
        self.repos.collections.delete(collection_id)

    def items(self, collection_id: int) -> list[dict]:
        return self.repos.collections.items(collection_id)

    def add(self, collection_id: int, media_type: str, media_id: int) -> None:
        self.repos.collections.add_item(collection_id, media_type, media_id)

    def remove(self, collection_id: int, media_type: str, media_id: int) -> None:
        self.repos.collections.remove_item(collection_id, media_type, media_id)

    def reorder(self, collection_id: int, ordered: list[tuple[str, int]]) -> None:
        self.repos.collections.reorder(collection_id, ordered)

    def collections_for(self, media_type: str, media_id: int) -> list[dict]:
        ids = self.repos.collections.collections_containing(media_type, media_id)
        out = []
        for cid in ids:
            row = self.repos.collections.get(cid)
            if row:
                out.append({"id": row.id, "name": row.name, "description": row.description})
        return out
