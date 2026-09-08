"""Filename → media identity. Production-grade normalization and detection."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from app.domain.enums import MediaKind
from app.domain.models import DetectedMedia

# --------------------------------------------------------------------------- patterns
_EP_SXXEYY = re.compile(
    r"[Ss](\d{1,2})[ ._\-]*[Ee](\d{1,2})",
)
_EP_1x00 = re.compile(
    r"(?<![0-9A-Za-z])(\d{1,2})[xX](\d{1,2})(?![0-9A-Za-z])",
)
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_BRACKET = re.compile(r"[\[\(][^\]\)]*[\]\)]")
_RELEASE_TAG = re.compile(
    r"(?i)\b("
    r"480p|576p|720p|1080p|2160p|4320p|4k|8k|"
    r"x264|x265|h264|h265|hevc|avc|"
    r"bluray|blu-ray|brrip|bdrip|webrip|web-dl|webdl|web|"
    r"dvdrip|dvd|hdtv|hdrip|proper|repack|"
    r"extended|remastered|remux|"
    r"10bit|8bit|hdr|hdr10|dv|"
    r"dolby|atmos|aac|ac3|dts|dd5\.1|5\.1|2\.0|"
    r"multi|dual|sub|subs|internal|"
    r"limited|xvid|divx|"
    r"amzn|nf|dsnp|hmax|hulu|atvp|"
    r"480p|720p|1080p|2160p|"
    r"hd|ma|dl|rip"
    r")\b",
)
_GROUP_TAIL = re.compile(r"(?:\s[-.]+\s*|\.\s+)[A-Za-z][\w\s.-]*$", re.IGNORECASE)
# Known collection prefixes that should be removed when preceded by a number,
# or when appearing as "Collection - Title" at the start of a filename.
_KNOWN_COLLECTIONS = re.compile(
    r"^(the\s+)?"
    r"(james\s+bond|fast\s+and\s+furious|mad\s+max|star\s+wars|pirates?\s+of\s+the|"
    r"matrix|hammer\s+horror|saw|halo|resident\s+evil|terminator|"
    r"alien|predator|x-men|spider-man|iron\s+man|avengers|dc\s*extended)",
    re.IGNORECASE,
)
# Collection-name-as-prefix pattern: "James Bond - Moonraker" or "Star Wars - A New Hope"
_COLLECTION_DASH = re.compile(
    r"^(?:the\s+)?"
    r"(?:james\s+bond|fast\s+and\s+furious|mad\s+max|star\s+wars|"
    r"pirates?\s+of\s+the|matrix|hammer\s+horror|saw|halo|resident\s+evil|"
    r"terminator|alien|predator|x-men|spider-man|iron\s+man|avengers|dc\s*extended)"
    r"\s*-\s*",
    re.IGNORECASE,
)
# Matches: "1 Dr No", "10 James Bond Moonraker", "6James Bond On Her Majestys..."
_SEQ_PREFIX = re.compile(
    r"""^(?P<prefix>\d{1,3})    # leading number 1-999
          (?P<sep>[ .\-]?)      # optional separator
          (?P<body>.*)$""",
    re.VERBOSE,
)
# Normalise smart/curly apostrophes to ASCII single-quote.
_APOSTROPHE = re.compile(r"[''']")
# Strip punctuation EXCEPT hyphens and apostrophes (they appear in legitimate titles).
_STRIP_PUNCT = re.compile(r"[^A-Za-z0-9\u00C0-\u024F\s'\-]+")
_MULTI_WS = re.compile(r"\s{2,}")

# Known collection prefixes that should be removed when preceded by a number.
_KNOWN_COLLECTIONS = re.compile(
    r"^(the\s+)?"
    r"(james\s+bond|fast\s+and\s+furious|mad\s+max|star\s+wars|pirates?\s+of\s+the|"
    r"matrix|hammer\s+horror|saw|halo|resident\s+evil|terminator|"
    r"alien|predator|x-men|spider-man|iron\s+man|avengers|dc\s*extended)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = _APOSTROPHE.sub("'", text)
    text = _BRACKET.sub(" ", text)
    text = _RELEASE_TAG.sub(" ", text)
    # Remove collection-name prefix like "James Bond - " at the start
    text = _COLLECTION_DASH.sub("", text)
    # Remove trailing release-group tail like " - SPARKS" or ".GuYVer"
    text = _GROUP_TAIL.sub("", text)
    text = _STRIP_PUNCT.sub(" ", text)
    text = _MULTI_WS.sub(" ", text).strip()
    # Final cleanup: remove any stray trailing dashes/dots
    text = re.sub(r'[-.\s]+$', '', text).strip()
    return text


def _find_year(stem: str) -> tuple[str, int | None]:
    """Return (stem_with_year_removed, year_int_or_None)."""
    m = _YEAR.search(stem)
    if m:
        return stem[:m.start()] + stem[m.end():], int(m.group(1))
    return stem, None


def _maybe_strip_seq_prefix(title: str) -> tuple[str, bool]:
    """Try to strip a leading sequence number from *title*.

    Returns (possibly_stripped_title, was_stripped).
    Strips iteratively so "10 James Bond Moonraker" → "Moonraker".
    """
    was_stripped = False
    for _ in range(5):  # multiple passes for nested prefixes
        m = _SEQ_PREFIX.match(title)
        if not m:
            break
        num = int(m.group("prefix"))
        body = m.group("body").strip()
        if not body:
            break
        # If body is purely numeric it's probably the real title (e.g. "300", "1917")
        if re.fullmatch(r"\d+", body):
            break
        if 1 <= num <= 99 and len(body) >= 2:
            if _KNOWN_COLLECTIONS.match(body):
                title = body.strip()
                was_stripped = True
                continue
            if num <= 20 and " " in body:
                title = body.strip()
                was_stripped = True
                continue
            # Single-word body with small leading number is likely a seq prefix too
            # (e.g. "4 Thunderball" → "Thunderball")
            if num <= 30 and len(body.split()) == 1 and len(body) >= 3:
                title = body.strip()
                was_stripped = True
                continue
        break
    # Second pass: strip any remaining "Collection Name - " or "Collection Name " prefix
    title2, changed2 = _strip_collection_prefix(title)
    if changed2:
        title = title2
        was_stripped = True
    return title, was_stripped


def _strip_collection_prefix(title: str) -> tuple[str, bool]:
    """Strip a known collection name prefix from the start of *title*.

    Handles both "James Bond - Moonraker" and "James Bond Moonraker".
    """
    m = _KNOWN_COLLECTIONS.match(title)
    if not m:
        return title, False
    after = title[m.end():].strip()
    # Remove optional trailing separator (dash, dot, space)
    after = re.sub(r'^[-.\s]+', '', after)
    if after:
        return after, True
    return title, False


def detect(path: Path | str) -> DetectedMedia:
    p = Path(path)
    ext = p.suffix.lower()

    # -- music -----------------------------------------------------------------
    if ext in {".mp3", ".flac", ".aac", ".ogg", ".opus", ".wav", ".m4a", ".wma"}:
        stem = p.stem
        # Strip track number prefix "01. Title" / "01 - Title" / "01Title"
        track_m = re.match(r"^\s*(\d+)\s*[.\-]?\s*(.+)", stem)
        if track_m:
            stem = track_m.group(2).strip()
        # For music, don't apply _GROUP_TAIL (it would eat "Artist - Song" patterns)
        text = unicodedata.normalize("NFKD", stem)
        text = _APOSTROPHE.sub("'", text)
        text = _BRACKET.sub(" ", text)
        text = _RELEASE_TAG.sub(" ", text)
        text = _STRIP_PUNCT.sub(" ", text)
        text = _MULTI_WS.sub(" ", text).strip()
        title = text or _normalize(p.stem)
        return DetectedMedia(path=str(p), kind=MediaKind.MUSIC, title=title)

    # -- video -----------------------------------------------------------------
    stem = p.stem
    normed = _normalize(stem)

    # Episode detection (must come before generic year extraction)
    ep = _EP_SXXEYY.search(normed) or _EP_1x00.search(normed)
    if ep:
        show_part = normed[:ep.start()]
        show_part, _ = _find_year(show_part)
        title = _normalize(show_part) or _normalize(normed[ep.end():])
        title, _ = _maybe_strip_seq_prefix(title)
        title = title.strip() or "?"
        year_m = _YEAR.search(normed)
        return DetectedMedia(
            path=str(p),
            kind=MediaKind.EPISODE,
            title=title,
            year=int(year_m.group(1)) if year_m else None,
            season=int(ep.group(1)),
            number=int(ep.group(2)),
        )

    # Movie / general video — detect year from raw stem, normalize, then strip year from normalized text
    _, year = _find_year(stem)
    title = _normalize(normed)
    # Normalize may have reintroduced the year (if it was embedded in dots), strip it again
    title, _ = _find_year(title)
    title, _ = _maybe_strip_seq_prefix(title)
    # If stripping left nothing and the original was a pure number, keep it as title
    if not title.strip() and re.fullmatch(r"\d+", normed.replace(".", " ").strip()):
        title = normed.replace(".", " ").strip()
    title = title.strip() or "?"

    return DetectedMedia(
        path=str(p),
        kind=MediaKind.MOVIE,
        title=title,
        year=year,
    )
