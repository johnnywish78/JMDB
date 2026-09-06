"""Repository layer: the only place SQL for library data is written."""
from __future__ import annotations

from dataclasses import fields as dc_fields
from typing import Any

from app.database.connection import Database


def row_to_dataclass(row, cls):
    """Map a sqlite3.Row to a dataclass by matching column names."""
    if row is None:
        return None
    valid = {f.name for f in dc_fields(cls)}
    kwargs = {k: row[k] for k in row.keys() if k in valid}
    return cls(**kwargs)


def rows_to_dataclasses(rows, cls):
    return [row_to_dataclass(r, cls) for r in rows]


class BaseRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _now(self) -> str:
        from datetime import datetime

        return datetime.utcnow().isoformat()

    def _parse_dt(self, value: Any):
        if not value:
            return None
        from datetime import datetime

        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None


class Repositories:
    """Bundle of all repositories over one database connection."""

    def __init__(self, db: Database) -> None:
        self.db = db
        from app.database.repositories.profiles import ProfilesRepository
        from app.database.repositories.locations import LibraryLocationsRepository
        from app.database.repositories.files import MediaFilesRepository
        from app.database.repositories.movies import MoviesRepository
        from app.database.repositories.tv import TvRepository
        from app.database.repositories.people import PeopleRepository
        from app.database.repositories.taxonomy import TaxonomyRepository
        from app.database.repositories.collections import CollectionsRepository
        from app.database.repositories.music import MusicRepository
        from app.database.repositories.lists import UserListsRepository
        from app.database.repositories.playback import PlaybackRepository
        from app.database.repositories.external import (
            ArtworkRepository,
            ExternalIdsRepository,
        )
        from app.database.repositories.metadata_cache import (
            MetadataCacheRepository,
            MetadataSourcesRepository,
        )
        from app.database.repositories.browser import BrowserRepository
        from app.database.repositories.services import (
            AppSettingsRepository,
            ServiceAccountsRepository,
        )

        self.profiles = ProfilesRepository(db)
        self.locations = LibraryLocationsRepository(db)
        self.files = MediaFilesRepository(db)
        self.movies = MoviesRepository(db)
        self.tv = TvRepository(db)
        self.people = PeopleRepository(db)
        self.taxonomy = TaxonomyRepository(db)
        self.collections = CollectionsRepository(db)
        self.music = MusicRepository(db)
        self.lists = UserListsRepository(db)
        self.playback = PlaybackRepository(db)
        self.external_ids = ExternalIdsRepository(db)
        self.artwork = ArtworkRepository(db)
        self.metadata_cache = MetadataCacheRepository(db)
        self.metadata_sources = MetadataSourcesRepository(db)
        self.browser = BrowserRepository(db)
        self.service_accounts = ServiceAccountsRepository(db)
        self.app_settings = AppSettingsRepository(db)

# Re-export repository classes for type imports elsewhere.
from app.database.repositories.profiles import ProfilesRepository  # noqa: E402,F401
from app.database.repositories.locations import LibraryLocationsRepository  # noqa: E402,F401
from app.database.repositories.files import MediaFilesRepository  # noqa: E402,F401
from app.database.repositories.movies import MoviesRepository  # noqa: E402,F401
from app.database.repositories.tv import TvRepository  # noqa: E402,F401
from app.database.repositories.people import PeopleRepository  # noqa: E402,F401
from app.database.repositories.taxonomy import TaxonomyRepository  # noqa: E402,F401
from app.database.repositories.collections import CollectionsRepository  # noqa: E402,F401
from app.database.repositories.music import MusicRepository  # noqa: E402,F401
from app.database.repositories.lists import UserListsRepository  # noqa: E402,F401
from app.database.repositories.playback import PlaybackRepository  # noqa: E402,F401
from app.database.repositories.external import (  # noqa: E402,F401
    ArtworkRepository,
    ExternalIdsRepository,
)
from app.database.repositories.metadata_cache import (  # noqa: E402,F401
    MetadataCacheRepository,
    MetadataSourcesRepository,
)
from app.database.repositories.browser import BrowserRepository  # noqa: E402,F401
from app.database.repositories.services import (  # noqa: E402,F401
    AppSettingsRepository,
    ServiceAccountsRepository,
)
