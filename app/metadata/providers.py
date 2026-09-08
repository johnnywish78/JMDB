"""HTTP providers. Every provider is optional, guarded, and raises ProviderError
on any failure so the manager can fall through the chain. Includes confidence-based
TMDB candidate selection."""
from __future__ import annotations

import logging
import re

try:
    import requests
except ImportError:  # pragma: no cover - env-dependent
    requests = None  # type: ignore

log = logging.getLogger("jmdb.meta")

_PROVIDER_TIMEOUT = 6  # seconds


class ProviderError(Exception):
    pass


def _require_requests() -> None:
    if requests is None:
        raise ProviderError("python 'requests' package is not installed")


def _session():
    _require_requests()
    s = requests.Session()
    s.headers["User-Agent"] = "JMDB/1.0"
    return s


def _year_from(date_str: str | None) -> int | None:
    if date_str:
        m = re.match(r"(\d{4})", date_str)
        return int(m.group(1)) if m else None
    return None


# ─── similarity helpers ───────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[a-z0-9]+", (text or "").lower())]


def _normalized_title(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _title_similarity(a: str, b: str) -> float:
    """Rough cosine-like similarity on token sets (0..1)."""
    sa, sb = set(_tokenize(a)), set(_tokenize(b))
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    union = sa | sb
    return len(inter) / len(union) if union else 0.0


def _exact_token_match(a: str, b: str) -> bool:
    return set(_tokenize(a)) == set(_tokenize(b)) and len(_tokenize(a)) >= 2


def _score_candidate(query_title: str, query_year: int | None,
                     cand_title: str, cand_year: int | None) -> float:
    """Score a single TMDB candidate against the query. Returns 0..1+."""
    score = 0.0

    # Title similarity (up to 0.5)
    sim = _title_similarity(query_title, cand_title)
    score += sim * 0.5

    # Bonus for exact token match
    if _exact_token_match(query_title, cand_title):
        score += 0.15

    # Year scoring (up to 0.35)
    if query_year is not None and cand_year is not None:
        diff = abs(query_year - cand_year)
        if diff == 0:
            score += 0.35
        elif diff == 1:
            score += 0.20
        elif diff == 2:
            score += 0.10
        elif diff <= 5:
            score += 0.05
        else:
            score -= 0.20  # strong penalty for distant years
    elif query_year is None:
        # No year hint — don't penalise, but don't reward either
        pass

    # Small bonus if titles are very short and match closely (less ambiguity)
    if len(_tokenize(query_title)) <= 3 and sim > 0.7:
        score += 0.05

    return min(score, 1.0)


_MIN_CONFIDENCE = 0.45


# ─── TMDBProvider ─────────────────────────────────────────────────────────────

class TMDBProvider:
    """Needs a free API key. Movies + series."""
    BASE = "https://api.themoviedb.org/3"
    IMG = "https://image.tmdb.org/t/p"

    def __init__(self, api_key: str):
        if not api_key:
            raise ProviderError("TMDB_API_KEY not configured")
        _require_requests()
        self.key = api_key
        self.http = _session()
        self._movie_genres: dict[int, str] | None = None
        self._tv_genres: dict[int, str] | None = None

    def _get(self, path: str, **params) -> dict:
        try:
            r = self.http.get(f"{self.BASE}{path}",
                              params={**params, "api_key": self.key},
                              timeout=_PROVIDER_TIMEOUT)
            if r.status_code == 401:
                raise ProviderError("TMDB rejected the API key (401)")
            if r.status_code == 429:
                raise ProviderError("TMDB rate-limited (429)")
            r.raise_for_status()
            return r.json()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"TMDB request failed: {exc}") from exc

    def _genres(self, ids: list[int], tv: bool) -> list[str]:
        if tv and self._tv_genres is None:
            try:
                self._tv_genres = {g["id"]: g["name"] for g in
                                   self._get("/genre/tv/list").get("genres", [])}
            except ProviderError:
                self._tv_genres = {}
        if not tv and self._movie_genres is None:
            try:
                self._movie_genres = {g["id"]: g["name"] for g in
                                      self._get("/genre/movie/list").get("genres", [])}
            except ProviderError:
                self._movie_genres = {}
        table = self._tv_genres if tv else self._movie_genres
        if table is None:
            return []
        return [table[i] for i in ids or [] if i in table]

    def search_movie(self, title: str, year: int | None = None) -> dict | None:
        try:
            data = self._get("/search/movie", query=title,
                             year=year or "", include_adult="false")
        except ProviderError:
            return None
        results = data.get("results") or []
        if not results:
            return None
        best, best_score = self._pick_best(results, title, year)
        if best is None or best_score < _MIN_CONFIDENCE:
            log.info("TMDB movie: no confident match for '%s' (year=%s), best_score=%.2f",
                     title, year, best_score if best_score else 0)
            return None
        log.info("TMDB movie matched: '%s' → '%s' (year %s/%s) score=%.2f",
                 title, best.get("title"), year, best.get("year"), best_score)
        return self._norm_movie(best)

    def search_series(self, title: str, year: int | None = None) -> dict | None:
        try:
            data = self._get("/search/tv", query=title,
                             first_air_date_year=year or "")
        except ProviderError:
            return None
        results = data.get("results") or []
        if not results:
            return None
        best, best_score = self._pick_best(results, title, year, is_series=True)
        if best is None or best_score < _MIN_CONFIDENCE:
            log.info("TMDB series: no confident match for '%s' (year=%s), best_score=%.2f",
                     title, year, best_score if best_score else 0)
            return None
        log.info("TMDB series matched: '%s' → '%s' (year %s/%s) score=%.2f",
                 title, best.get("name"), year, best.get("year"), best_score)
        return {
            "title": best.get("name") or title,
            "original_title": best.get("original_name") or "",
            "year": _year_from(best.get("first_air_date")),
            "rating": round(float(best.get("vote_average") or 0), 1),
            "overview": best.get("overview") or "",
            "genres": self._genres(best.get("genre_ids"), tv=True),
            "poster_url": self.poster_url(best.get("poster_path")),
            "backdrop_url": self.backdrop_url(best.get("backdrop_path")),
            "tmdb_id": best.get("id"),
        }

    def _pick_best(self, results: list, title: str, year: int | None,
                   is_series: bool = False) -> tuple[dict, float]:
        best_result, best_score = None, -1.0
        for hit in results:
            cand_title = hit.get("title") if not is_series else hit.get("name")
            cand_year = _year_from(hit.get("release_date") if not is_series
                                   else hit.get("first_air_date"))
            s = _score_candidate(title, year, cand_title or "", cand_year)
            if s > best_score:
                best_score = s
                best_result = hit
        return best_result or results[0], best_score

    def _norm_movie(self, hit: dict) -> dict:
        return {
            "title": hit.get("title") or "",
            "original_title": hit.get("original_title") or "",
            "year": _year_from(hit.get("release_date")),
            "rating": round(float(hit.get("vote_average") or 0), 1),
            "overview": hit.get("overview") or "",
            "genres": self._genres(hit.get("genre_ids"), tv=False),
            "poster_url": self.poster_url(hit.get("poster_path")),
            "backdrop_url": self.backdrop_url(hit.get("backdrop_path")),
            "tmdb_id": hit.get("id"),
        }

    @classmethod
    def poster_url(cls, path: str | None, size: str = "w500") -> str | None:
        return f"{cls.IMG}/{size}{path}" if path else None

    @classmethod
    def backdrop_url(cls, path: str | None, size: str = "w780") -> str | None:
        return f"{cls.IMG}/{size}{path}" if path else None


# ─── TVMazeProvider ───────────────────────────────────────────────────────────

class TVMazeProvider:
    """Free, keyless series provider — the zero-config default for TV."""
    BASE = "https://api.tvmaze.com"

    def __init__(self):
        _require_requests()
        self.http = _session()

    def search_series(self, title: str, year: int | None = None) -> dict | None:
        try:
            r = self.http.get(f"{self.BASE}/singlesearch/shows",
                              params={"q": title}, timeout=_PROVIDER_TIMEOUT)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            show = r.json()
        except Exception as exc:
            raise ProviderError(f"TVMaze request failed: {exc}") from exc
        summary = re.sub(r"<[^>]+>", "", show.get("summary") or "")
        rating = (show.get("rating") or {}).get("average") or 0
        image = show.get("image") or {}
        return {
            "title": show.get("name") or title,
            "original_title": "",
            "year": _year_from(show.get("premiered")),
            "rating": round(float(rating), 1),
            "overview": summary,
            "genres": show.get("genres") or [],
            "poster_url": image.get("medium") or image.get("original"),
            "backdrop_url": image.get("original"),
            "tmdb_id": None,
        }


# ─── OMDbProvider ─────────────────────────────────────────────────────────────

class OMDbProvider:
    """Key-based movie fallback (imdb ratings included)."""
    BASE = "https://www.omdbapi.com/"

    def __init__(self, api_key: str):
        if not api_key:
            raise ProviderError("OMDB_API_KEY not configured")
        _require_requests()
        self.key = api_key
        self.http = _session()

    def search_movie(self, title: str, year: int | None = None) -> dict | None:
        try:
            r = self.http.get(self.BASE, params={
                "apikey": self.key, "t": title, "y": year or "", "type": "movie",
            }, timeout=_PROVIDER_TIMEOUT)
            data = r.json()
        except Exception as exc:
            raise ProviderError(f"OMDb request failed: {exc}") from exc
        if data.get("Response") != "True":
            return None
        runtime = 0
        m = re.match(r"(\d+)", data.get("Runtime", ""))
        if m:
            runtime = int(m.group(1))
        try:
            rating = round(float(data.get("imdbRating", 0) or 0), 1)
        except ValueError:
            rating = 0.0
        return {
            "title": data.get("Title") or title,
            "original_title": "",
            "year": int(data["Year"][:4]) if (data.get("Year") or "")[:4].isdigit() else year,
            "rating": rating,
            "overview": data.get("Plot", "") if data.get("Plot") != "N/A" else "",
            "runtime_min": runtime,
            "genres": [g.strip() for g in (data.get("Genre") or "").split(",") if g.strip()],
            "poster_url": data.get("Poster") if (data.get("Poster") or "").startswith("http") else None,
            "backdrop_url": None,
            "imdb_id": data.get("imdbID") or "",
        }
