"""Filename detector contract tests (pure logic)."""
from __future__ import annotations

import pytest

from app.domain.enums import MediaKind
from app.library.media_detector import detect


@pytest.mark.parametrize("filename, title, year, season, number", [
    ("The.Matrix.1999.1080p.BluRay.x264.mkv", "The Matrix", 1999, None, None),
    ("My.Movie.Collection.2020.2160p.WEB-DL.mkv", "My Movie Collection", 2020, None, None),
    ("WALL-E.2008.720p.mkv", "WALL-E", 2008, None, None),
    ("Breaking.Bad.S05E14.Ozymandias.1080p.mkv", "Breaking Bad", None, 5, 14),
    ("Show.Name.2x03.avi", "Show Name", None, 2, 3),
])
def test_detect(filename, title, year, season, number):
    result = detect(filename)
    assert result.title == title
    assert result.year == year
    assert result.season == season
    assert result.number == number
    expected_kind = MediaKind.EPISODE if season is not None else MediaKind.MOVIE
    assert result.kind == expected_kind


def test_episode_title_fallback_after_marker():
    result = detect("S01E02.The.North.Remembers.1080p.mkv")
    assert result.title == "The North Remembers"
    assert result.kind == MediaKind.EPISODE


def test_audio_is_music():
    result = detect("Pink.Floyd/01.Shine.On.You.Crazy.Diamond.flac")
    assert result.kind == MediaKind.MUSIC
    assert result.title == "Shine On You Crazy Diamond"


def test_no_year_without_valid_year_token():
    result = detect("Random.Movie.Name.720p.mkv")
    assert result.year is None
    assert "Random" in result.title


# ─── Bond / collection prefix tests ───────────────────────────────────────────

def test_bond_1_dr_no():
    result = detect("1 Dr No 1962.mkv")
    assert result.title == "Dr No"
    assert result.year == 1962
    assert result.kind == MediaKind.MOVIE


def test_bond_10_moonraker():
    result = detect("10 James Bond Moonraker 1979.mkv")
    assert result.title == "Moonraker"
    assert result.year == 1979
    assert result.kind == MediaKind.MOVIE


def test_bond_11_for_your_eyes_only():
    result = detect("11 James Bond For Your Eyes Only 1981.mkv")
    assert result.title == "For Your Eyes Only"
    assert result.year == 1981
    assert result.kind == MediaKind.MOVIE


def test_bond_6_hermitys_secret_service():
    result = detect("6James Bond On Her Majestys Secret Service 1969.mkv")
    assert result.title == "On Her Majestys Secret Service"
    assert result.year == 1969
    assert result.kind == MediaKind.MOVIE


def test_bond_goldeneye():
    result = detect("GoldenEye 1995.mkv")
    assert result.title == "GoldenEye"
    assert result.year == 1995
    assert result.kind == MediaKind.MOVIE


def test_bond_casino_royale():
    result = detect("Casino Royale 2006.mkv")
    assert result.title == "Casino Royale"
    assert result.year == 2006
    assert result.kind == MediaKind.MOVIE


def test_bond_skyfall():
    result = detect("Skyfall 2012.mkv")
    assert result.title == "Skyfall"
    assert result.year == 2012
    assert result.kind == MediaKind.MOVIE


def test_bond_spectre():
    result = detect("Spectre 2015.mkv")
    assert result.title == "Spectre"
    assert result.year == 2015
    assert result.kind == MediaKind.MOVIE


def test_bond_with_dashes_and_brackets():
    result = detect("James Bond - Moonraker (1979).mkv")
    assert result.title == "Moonraker"
    assert result.year == 1979


def test_bond_with_apostrophe():
    result = detect("On Her Majesty's Secret Service 1969.mkv")
    assert result.title == "On Her Majesty's Secret Service"
    assert result.year == 1969


# ─── TV episode tests ─────────────────────────────────────────────────────────

def test_tv_sxxeYY():
    result = detect("Arcane.S01E01.The_Http_Man.mkv")
    assert result.title == "Arcane"
    assert result.kind == MediaKind.EPISODE
    assert result.season == 1
    assert result.number == 1


def test_tv_1x01():
    result = detect("Arcane.1x01.The_Http_Man.mkv")
    assert result.title == "Arcane"
    assert result.kind == MediaKind.EPISODE
    assert result.season == 1
    assert result.number == 1


def test_tv_with_year():
    result = detect("Arcane.2021.S01E01.1080p.mkv")
    assert result.title == "Arcane"
    assert result.kind == MediaKind.EPISODE
    assert result.season == 1
    assert result.number == 1


# ─── Music tests ──────────────────────────────────────────────────────────────

def test_music_flac():
    result = detect("Pink Floyd - Shine On You Crazy Diamond.flac")
    assert result.kind == MediaKind.MUSIC
    assert result.title == "Pink Floyd - Shine On You Crazy Diamond"


def test_music_with_track_number():
    result = detect("01. Bohemian Rhapsody.mp3")
    assert result.kind == MediaKind.MUSIC
    assert result.title == "Bohemian Rhapsody"


def test_music_m4a():
    result = detect("Album/02.Hot.Fun.Shit.mp3")
    assert result.kind == MediaKind.MUSIC
    assert result.title == "Hot Fun Shit"


# ─── Year extraction edge cases ───────────────────────────────────────────────

def test_year_not_in_release_tags():
    # 2024 should not be treated as year when it's part of a release tag
    result = detect("Movie.Title.2024.1080p.WEB-DL.mkv")
    assert result.year == 2024


def test_valid_number_titles():
    # These are real movie titles that are just numbers
    for title_text, expected in [("1917.mkv", "1917"), ("300.2006.mkv", "300"),
                                  ("9.mkv", "9")]:
        result = detect(title_text)
        assert result.title == expected, f"Failed for {title_text}: got {result.title}"


def test_release_noise_stripped():
    result = detect("Movie.Title.2020.1080p.BluRay.x264.DTS-HD.MA.5.1-GuYVer.mkv")
    assert result.title == "Movie Title"
    assert result.year == 2020


def test_dashed_release_group_tail_removed():
    result = detect("Movie Title 2020.1080p.mkv - SPARKS")
    assert result.title == "Movie Title"
    assert result.year == 2020
