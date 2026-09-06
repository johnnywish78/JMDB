"""Bookmarks persistence."""
from __future__ import annotations

from app.database.repositories import Repositories
from app.domain.models import Bookmark


class Bookmarks:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def add(self, url: str, title: str = "", folder: str = "") -> Bookmark:
        return self.repos.browser.add_bookmark(url, title, folder)

    def remove(self, url: str) -> None:
        self.repos.browser.remove_bookmark(url)

    def toggle(self, url: str, title: str = "") -> bool:
        if self.repos.browser.is_bookmarked(url):
            self.remove(url)
            return False
        self.add(url, title)
        return True

    def is_bookmarked(self, url: str) -> bool:
        return self.repos.browser.is_bookmarked(url)

    def all(self, folder: str | None = None) -> list[Bookmark]:
        return self.repos.browser.bookmarks(folder)
