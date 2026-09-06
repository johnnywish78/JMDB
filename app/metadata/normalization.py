"""Title normalization and match confidence for provider lookups."""
from __future__ import annotations

import re
import unicodedata

ARTICLES = {"the", "a", "an"}

_PUNCT = re.compile(r"[\:\'’,\.!?&]"


                    )
_NOISE_WORDS = {
    "and", "or", "in", "on", "at", "of", "to", "for", "with",
}


def normalize_title(title: str) -> str:
    """Aggressive normalization for matching: lowercase, strip punctuation,
    articles, and diacritics."""
    if not title:
        return ""
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _PUNCT.sub(" ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w]
    while words and words[0] in ARTICLES:
        words = words[1:]
    return " ".join(words)


def sort_title(title: str) -> str:
    """'The Matrix' → 'Matrix, The' for sort keys."""
    for article in ARTICLES:
        if title.lower().startswith(article + " "):
            return title[len(article) + 1 :].strip() + ", " + article.capitalize()
    return title


def match_confidence(
    local_title: str,
    candidate_title: str,
    local_year: int | None = None,
    candidate_year: int | None = None,
) -> float:
    """0.0–1.0 confidence that a provider result matches a local item."""
    a, b = normalize_title(local_title), normalize_title(candidate_title)
    if not a or not b:
        return 0.0
    if a == b:
        score = 1.0
    elif a in b or b in a:
        score = 0.85
    else:
        # token overlap (Jaccard-ish)
        sa, sb = set(a.split()), set(b.split())
        overlap = len(sa & sb) / max(1, len(sa | sb))
        score = overlap
        if score < 0.5:
            return score * 0.8
    if local_year and candidate_year:
        if abs(local_year - candidate_year) == 0:
            score = min(1.0, score + 0.1)
        elif abs(local_year - candidate_year) > 2:
            score *= 0.6
    return score


def clean_overview(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    # provider artifacts
    for prefix in ("Add a Plot »", "Add a Plot", "N/A", "—"):
        if text.startswith(prefix):
            return ""
    return text


def iso_date(value, default: str = "") -> str:
    """Normalize assorted provider date formats to YYYY-MM-DD."""
    if not value:
        return default
    value = str(value)
    match = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", value)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.match(r"(\d{1,2})\s+(\w{3,})\s+(\d{4})", value)  # '15 Mar 2019'
    if match:
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month = months.get(match.group(2)[:3].lower())
        if month:
            return f"{match.group(3)}-{month:02d}-{int(match.group(1)):02d}"
    return default
