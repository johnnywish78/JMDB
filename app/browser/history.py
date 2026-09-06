"""Browser history persistence (DB-backed)."""
from __future__ import annotations

from app.database.repositories import Repositories


class BrowserHistory:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def add(self, url: str, title: str = "") -> None:
        self.repos.browser.add_history(url, title)

    def entries(self, limit: int = 200, query: str = "") -> list[dict]:
        return [
            {
                "url": entry.url,
                "title": entry.title,
                "visited_at": entry.visited_at.isoformat() if entry.visited_at else "",
            }
            for entry in self.repos.browser.history(limit, query)
        ]

    def clear(self) -> None:
        self.repos.browser.clear_history()

    def top_sites(self, limit: int = 10) -> list[dict]:
        return self.repos.browser.top_sites(limit)
