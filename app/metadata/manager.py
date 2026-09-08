"""MetadataManager: tries providers in order with confidence-based matching,
caches positives per-provider, applies field-precedence merge to repo.
Missing keys / network / 404s all degrade silently down the chain."""
from __future__ import annotations

import logging
import time
from typing import Any

from app.domain.enums import MediaKind
from app.domain.models import DetectedMedia
from app.metadata.cache import (
    BUCKET_MOVIE,
    BUCKET_MUSIC,
    BUCKET_SERIES,
    MetadataCache,
)
from app.metadata.providers import (
    OMDbProvider,
    ProviderError,
    TMDBProvider,
    TVMazeProvider,
)

log = logging.getLogger("jmdb.meta")

TTL_S = 60 * 60 * 24 * 30  # 30 days
# Per-provider TTL for backoff when a provider is temporarily failing.
_PROVIDER_FAIL_TTL = 60 * 5  # 5 minutes


class MetadataManager:
    def __init__(self, cache: MetadataCache, tmdb_key: str = "", omdb_key: str = ""):
        self.cache = cache
        self.movie_chain: list = []
        self.series_chain: list = []
        self._provider_failures: dict[str, float] = {}  # provider_name -> failure_time
        self._build(tmdb_key, omdb_key)

    def _build(self, tmdb_key: str, omdb_key: str) -> None:
        try:
            tmdb = TMDBProvider(tmdb_key)
            self.movie_chain.append(tmdb)
            self.series_chain.append(tmdb)
        except ProviderError as exc:
            log.info("TMDB disabled: %s", exc)
        try:
            self.series_chain.insert(0, TVMazeProvider())  # keyless → first for series
        except ProviderError as exc:
            log.info("TVMaze disabled: %s", exc)
        try:
            self.movie_chain.append(OMDbProvider(omdb_key))
        except ProviderError as exc:
            log.info("OMDb disabled: %s", exc)

    def configured(self) -> bool:
        return bool(self.movie_chain or self.series_chain)

    # ------------------------------------------------------------------ API
    def enrich(self, media_id: int, detected: DetectedMedia,
               media_repo=None) -> dict | None:
        """Fetch best metadata for `detected`, store it, return the dict (or None)."""
        kind_info = self._classify(detected)
        if kind_info is None:
            return None
        chain = kind_info["chain"]
        bucket = kind_info["bucket"]
        if not chain:
            return None

        cache_key = self._cache_key(detected)
        meta = self.cache.get_any_provider(bucket, cache_key, TTL_S)
        if meta is None:
            for provider in chain:
                if self._is_blocked(provider):
                    continue
                try:
                    fn = provider.search_movie if kind_info["movie_like"] else provider.search_series
                    meta = fn(detected.title, detected.year)
                except ProviderError as exc:
                    log.info("%s failed: %s", provider.__class__.__name__, exc)
                    self._mark_failed(provider.__class__.__name__)
                    continue
                if meta:
                    self.cache.set(bucket, cache_key, meta,
                                   provider=provider.__class__.__name__)
                    log.info("%s matched: %s → %s", provider.__class__.__name__,
                             detected.title, meta.get("title"))
                    break

        if not meta:
            return None
        normalized = self._to_repo_payload(meta)
        if media_repo is not None:
            media_repo.apply_metadata(media_id, normalized)
        return {**normalized, "_raw_title": meta.get("title"),
                "_provider": meta.get("_provider")}

    def re_enrich(self, media_id: int, detected: DetectedMedia | None = None,
                  media_repo=None, *, clear_cache: bool = False) -> dict | None:
        """Re-enrich an existing media record.

        If *detected* is None the record's own title/year from the DB are used.
        Setting *clear_cache* forces a fresh provider lookup even if cached data
        exists — useful when the library file changed or the user requests repair.
        """
        if media_repo and media_id:
            row = media_repo.get(media_id)
            if not row:
                return None
            if detected is None:
                detected = DetectedMedia(
                    path=row.get("file_path") or "",
                    kind=self._kind_to_media_kind(row.get("kind", "movie")),
                    title=row["title"],
                    year=row.get("year"),
                )
        elif detected is None:
            return None

        kind_info = self._classify(detected)
        if kind_info is None:
            return None
        chain = kind_info["chain"]
        bucket = kind_info["bucket"]
        if not chain:
            return None

        cache_key = self._cache_key(detected)
        if clear_cache:
            self.cache.clear(bucket=bucket, key_prefix=cache_key)
            log.info("cleared cache for %s/%s", bucket, cache_key)

        meta = self.cache.get_any_provider(bucket, cache_key, TTL_S)
        if meta is None:
            for provider in chain:
                if self._is_blocked(provider):
                    continue
                try:
                    fn = provider.search_movie if kind_info["movie_like"] else provider.search_series
                    meta = fn(detected.title, detected.year)
                except ProviderError as exc:
                    log.info("%s failed on re-enrich: %s", provider.__class__.__name__, exc)
                    self._mark_failed(provider.__class__.__name__)
                    continue
                if meta:
                    self.cache.set(bucket, cache_key, meta,
                                   provider=provider.__class__.__name__)
                    log.info("%s matched on re-enrich: %s → %s",
                             provider.__class__.__name__, detected.title, meta.get("title"))
                    break

        if not meta:
            return None
        normalized = self._to_repo_payload(meta)
        if media_repo is not None:
            media_repo.apply_metadata(media_id, normalized)
        return {**normalized, "_provider": meta.get("_provider")}

    def merge_metadata(self, primary: dict, secondary: dict) -> dict:
        """Merge two provider payloads: primary wins on every field except where
        secondary supplies a non-empty value that primary is missing (e.g. IMDb ID)."""
        out = dict(primary)
        for key in ("imdb_id", "runtime_min"):
            if not out.get(key) and secondary.get(key):
                out[key] = secondary[key]
        if not out.get("overview") and secondary.get("overview"):
            out["overview"] = secondary["overview"]
        if not out.get("poster_url") and secondary.get("poster_url"):
            out["poster_url"] = secondary["poster_url"]
        return out

    def invalidate_provider(self, provider_class_name: str) -> int:
        """Temporarily block a misbehaving provider (marks it failed for 5 min).
        Returns number of entries cleared for that provider from cache."""
        return self.cache.clear(provider=provider_class_name)

    def clear_cache(self, bucket: str | None = None) -> int:
        """Clear the entire metadata cache (optionally scoped to a bucket)."""
        return self.cache.clear(bucket=bucket)

    def cache_stats(self) -> dict[str, int]:
        return self.cache.stats()

    # ── internals ─────────────────────────────────────────────────────────────

    def _classify(self, detected: DetectedMedia) -> dict | None:
        if detected.kind == MediaKind.MUSIC:
            return {"chain": [], "bucket": BUCKET_MUSIC, "movie_like": False}
        if detected.kind == MediaKind.EPISODE:
            return {"chain": self.series_chain, "bucket": BUCKET_SERIES,
                    "movie_like": False}
        if detected.kind == MediaKind.SHOW:
            return {"chain": self.series_chain, "bucket": BUCKET_SERIES,
                    "movie_like": False}
        if detected.kind == MediaKind.MOVIE:
            return {"chain": self.movie_chain, "bucket": BUCKET_MOVIE,
                    "movie_like": True}
        return None

    @staticmethod
    def _kind_to_media_kind(kind: str) -> MediaKind:
        return MediaKind(kind) if kind in {k.value for k in MediaKind} else MediaKind.MOVIE

    @staticmethod
    def _cache_key(detected: DetectedMedia) -> str:
        return f"{detected.title.casefold()}|{detected.year or ''}"

    def _is_blocked(self, provider) -> bool:
        name = provider.__class__.__name__
        last = self._provider_failures.get(name, 0)
        return time.time() - last < _PROVIDER_FAIL_TTL

    def _mark_failed(self, provider_name: str) -> None:
        self._provider_failures[provider_name] = time.time()

    @staticmethod
    def _to_repo_payload(meta: dict[str, Any]) -> dict[str, Any]:
        """Provider dict → repository columns, using explicit precedence."""
        return {
            "original_title": meta.get("original_title") or "",
            "rating": float(meta.get("rating") or 0),
            "overview": meta.get("overview") or "",
            "runtime_min": int(meta.get("runtime_min") or 0),
            "genres": meta.get("genres") or [],
            "year": meta.get("year"),
            "imdb_id": meta.get("imdb_id") or "",
            "tmdb_id": meta.get("tmdb_id"),
            "poster_url": meta.get("poster_url"),
            "backdrop_url": meta.get("backdrop_url"),
        }
