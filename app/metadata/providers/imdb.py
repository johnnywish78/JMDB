"""IMDb integration — honest boundaries.

IMDb does not offer an unrestricted public metadata API. JMDB therefore:

* stores IMDb IDs (``tt…``) on movies/shows/episodes/people whenever a
  provider returns them (TMDB, OMDb, TVmaze),
* resolves IMDb ratings/plot via OMDb (which is a legitimate licensed API
  for IMDb data),
* links out to imdb.com pages,
* and NEVER scrapes IMDb HTML.
"""
from __future__ import annotations

import re

IMDB_ID_RE = re.compile(r"^(tt\d{7,10})$", re.IGNORECASE)
IMDB_URL_RE = re.compile(r"imdb\.com/title/(tt\d{7,10})", re.IGNORECASE)
IMDB_NAME_URL_RE = re.compile(r"imdb\.com/name/(nm\d{7,10})", re.IGNORECASE)


def normalize_imdb_id(value: str | None) -> str:
    """'https://www.imdb.com/title/tt1234567/' → 'tt1234567'."""
    if not value:
        return ""
    value = value.strip()
    match = IMDB_ID_RE.match(value)
    if match:
        return match.group(1).lower()
    match = IMDB_URL_RE.search(value) or IMDB_NAME_URL_RE.search(value)
    if match:
        return match.group(1).lower()
    return ""


def is_valid_imdb_id(value: str | None) -> bool:
    return bool(IMDB_ID_RE.match(value or ""))


def imdb_title_url(imdb_id: str | None) -> str:
    imdb_id = normalize_imdb_id(imdb_id)
    return f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else ""


def imdb_name_url(imdb_id: str | None) -> str:
    imdb_id = normalize_imdb_id(imdb_id)
    return f"https://www.imdb.com/name/{imdb_id}/" if imdb_id else ""


def strip_imdb_from_title(title: str) -> tuple[str, str]:
    """Some libraries name files 'Movie [tt1234567]'. Extract both."""
    match = re.search(r"\[(tt\d{7,10})\]", title)
    if match:
        return title[: match.start()].strip(), match.group(1).lower()
    return title, ""
