"""Series matching: group episode candidates into shows, resolve titles."""
from __future__ import annotations

import re
from collections import defaultdict

from app.library.episode_matcher import EpisodeCandidate

# US-style show titles use punctuation the scene replaces with dots
_PUNCT = re.compile(r"[\:\'’,\!?]")


def normalize_show_title(title: str) -> str:
    """Normalization used to group episodes of the same show."""
    lowered = title.lower()
    lowered = _PUNCT.sub("", lowered)
    lowered = lowered.replace("&", "and")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def group_by_show(candidates: list[EpisodeCandidate]) -> dict[str, list[EpisodeCandidate]]:
    groups: dict[str, list[EpisodeCandidate]] = defaultdict(list)
    for candidate in candidates:
        groups[normalize_show_title(candidate.show_title)].append(candidate)
    return dict(groups)


def canonical_title(candidates: list[EpisodeCandidate]) -> str:
    """Best display title among a group: prefer the shortest clean variant."""
    titles = [c.show_title for c in candidates if c.show_title]
    if not titles:
        return ""
    counts: dict[str, int] = defaultdict(int)
    for title in titles:
        counts[title] += 1
    # most frequent, then shortest (scene titles are usually fine)
    best = sorted(counts.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))
    return best[0][0]
