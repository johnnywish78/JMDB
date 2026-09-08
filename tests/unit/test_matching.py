"""Tests for TMDB candidate matching confidence scoring."""
from __future__ import annotations

from app.metadata.providers import _normalized_title, _score_candidate, _title_similarity


class TestTitleSimilarity:
    def test_exact_match(self):
        assert _title_similarity("Moonraker", "Moonraker") == 1.0

    def test_same_tokens_different_order(self):
        # "James Bond Moonraker" vs "Moonraker James Bond"
        s = _title_similarity("James Bond Moonraker", "Moonraker James Bond")
        assert s > 0.5

    def test_partial_overlap(self):
        s = _title_similarity("Moonraker", "Moonraker 2")
        assert 0 < s < 1.0

    def test_completely_different(self):
        s = _title_similarity("Moonraker", "The Matrix")
        assert s < 0.3


class TestScoreCandidate:
    def test_exact_title_exact_year(self):
        s = _score_candidate("Moonraker", 1979, "Moonraker", 1979)
        assert s >= 0.85

    def test_exact_title_year_off_by_two(self):
        s = _score_candidate("Moonraker", 1979, "Moonraker", 1981)
        # Same title but year diff 2 → moderate score, still acceptable
        assert s >= 0.55

    def test_exact_title_year_far_off(self):
        s = _score_candidate("Moonraker", 1979, "Moonraker", 2020)
        # Strong penalty for distant year
        assert s < 0.5

    def test_partial_title_good_year(self):
        s = _score_candidate("Dr No", 1962, "Dr. No", 1962)
        assert s >= 0.7

    def test_different_titles_same_year(self):
        s = _score_candidate("Moonraker", 1979, "The Matrix", 1999)
        assert s < 0.3

    def test_missing_year_no_penalty(self):
        s = _score_candidate("Moonraker", None, "Moonraker", 1979)
        assert s >= 0.5  # title match only


class TestNormalizedTitle:
    def test_lowercase_punctuation_stripped(self):
        # Note: apostrophes are stripped by _normalized_title (used for matching),
        # so "Majesty's" → "majesty s"
        assert _normalized_title("On Her Majesty's Secret Service") == \
            "on her majesty s secret service"

    def test_numbers_preserved(self):
        assert _normalized_title("300") == "300"

    def test_multiple_spaces_collapsed(self):
        assert _normalized_title("Movie   Title") == "movie title"
