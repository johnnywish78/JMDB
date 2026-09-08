"""Small validated value objects."""
from __future__ import annotations

import re

_HUMAN_H = 3600
_HUMAN_M = 60


def human_minutes(minutes: int) -> str:
    if minutes <= 0:
        return "—"
    hours, mins = divmod(minutes, _HUMAN_M)
    return f"{hours}h {mins}m" if hours else f"{mins}m"


def clock(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, _HUMAN_H)
    mins, secs = divmod(rem, _HUMAN_M)
    return f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"


class Rating:
    """0..10 personal or provider rating."""

    def __init__(self, value: float):
        if not 0 <= float(value) <= 10:
            raise ValueError(f"rating out of range: {value}")
        self.value = round(float(value), 1)

    def __float__(self) -> float:  # pragma: no cover - trivial
        return self.value


_SEPARATORS = re.compile(r"[._]+")


def sanitize_title(raw: str) -> str:
    """'the_matrix' / 'the.matrix' -> 'The Matrix' (keeps numerals/unicode)."""
    title = _SEPARATORS.sub(" ", raw).strip(" -")
    title = re.sub(r"\s+(?=\d{4}\b)", " ", title)  # keep space before year fine
    return re.sub(r"\s{2,}", " ", title).strip()
