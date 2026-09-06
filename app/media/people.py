"""People catalog."""
from __future__ import annotations

from app.database.repositories import Repositories


class PeopleCatalog:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def list_page(self, page=0, per_page=60, query="") -> tuple[list[dict], int]:
        return self.repos.people.list_page(page, per_page, query)

    def search(self, query: str, limit: int = 30) -> list[dict]:
        return self.repos.people.search(query, limit)

    def person_detail(self, person_id: int, profile_id: int) -> dict | None:
        person = self.repos.people.get(person_id)
        if person is None:
            return None
        filmography = self.repos.people.filmography(person_id)
        known_for = [
            entry
            for entry in filmography
            if entry["role"] in ("actor", "director") and entry["poster_path"]
        ][:10]
        return {
            "id": person.id,
            "name": person.name,
            "biography": person.biography,
            "birthday": person.birthday,
            "deathday": person.deathday,
            "place_of_birth": person.place_of_birth,
            "photo_path": self.repos.artwork.local_path("person", person_id, "profile"),
            "external_ids": self.repos.external_ids.all_for("person", person_id),
            "filmography": filmography,
            "known_for": known_for,
            "credit_count": len(filmography),
        }
