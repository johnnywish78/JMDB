"""Media detection: file-type classification and filename intelligence.

All "understanding" of messy real-world filenames lives here and in the
matcher modules — never in the UI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

VIDEO_EXTENSIONS = {
    "mkv", "mp4", "m4v", "avi", "mov", "webm", "wmv", "flv", "ts", "m2ts",
    "mts", "mpg", "mpeg", "ogv", "3gp", "asf", "divx", "vob", "rmvb", "rm",
    "mpe", "qt", "f4v", "swf",
}
AUDIO_EXTENSIONS = {
    "mp3", "flac", "m4a", "aac", "ogg", "oga", "opus", "wma", "wav", "aiff",
    "aif", "alac", "ape", "wv", "m4b", "mpc", "mid", "midi",
}
SUBTITLE_EXTENSIONS = {"srt", "ass", "ssa", "vtt", "sub", "idx", "sup", "ttml", "sbv"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp", "gif", "tiff", "tif", "avif"}

# Local artwork filenames recognized inside media folders
LOCAL_ARTWORK = {
    "poster": {"poster", "poster.jpg", "poster.png", "folder", "folder.jpg", "folder.png",
               "cover", "cover.jpg", "cover.png", "movie"},
    "backdrop": {"backdrop", "backdrop.jpg", "backdrop.png", "fanart", "fanart.jpg",
                 "fanart.png", "background"},
    "logo": {"logo", "logo.jpg", "logo.png", "clearart"},
    "season_poster": {"season", "season-all"},
}

QUALITY_TAGS = {
    "360p", "480p", "576p", "720p", "1080p", "2160p", "4k", "8k",
    "hd", "sd", "uhd", "webrip", "web-dl", "webdl", "bluray", "blu-ray", "bdrip",
    "brrip", "dvdrip", "dvdscr", "hdtv", "pdtv", "cam", "ts", "telesync", "wp",
    "hdcam", "hq", "remux", "proper", "repack", "extended", "unrated",
    "remastered", "imax", "internal", "limited", "complete",
}

CODEC_TAGS = {
    "x264", "h264", "x265", "h265", "hevc", "xvid", "divx", "av1", "vp9",
    "aac", "ac3", "eac3", "dts", "dtshd", "truehd", "atmos", "flac", "mp3",
    "aac2", "aac5", "ddp", "dd", "dts-hd", "ma", "10bit", "8bit", "hdr",
    "hdr10", "dolby", "vision", "sdr",
}

RELEASE_NOISE = {
    "aac", "ac3", "eac3", "dts", "truehd", "atmos", "amzn", "nf", "nfw",
    "dsnp", "atvp", "hulu", "hmax", "pcok", "stz", "episode",
}

# Groups of tokens that are part of known editions — kept in the title
EDITION_PATTERNS = [
    r"(?i)\b(extended\s+(?:cut|edition|version)?)\b",
    r"(?i)\b(director'?s?\s+cut)\b",
    r"(?i)\b(ultimate\s+edition)\b",
    r"(?i)\b(unrated)\b",
    r"(?i)\b(remastered)\b",
    r"(?i)\b(imax)\b",
    r"(?i)\b(theatrical\s+(?:cut|version)?)\b",
]

# Episode patterns, tried in order of specificity
EPISODE_PATTERNS = [
    # S02E05 / s02e05e06 (multi-episode)
    re.compile(r"(?i)[\s._\-\[]*s(\d{1,2})[\s._\-]?e(\d{1,3})(?:[\s._\-]?e(\d{1,3}))?[\s._\-\]]*"),
    # 2x05
    re.compile(r"(?i)[\s._\-\[]*(\d{1,2})x(\d{1,3})[\s._\-\]]*"),
    # Season 2 Episode 5 / Séries 2 Episode 5
    re.compile(r"(?i)season[\s._\-]*(\d{1,2})[\s._\-]*episode[\s._\-]*(\d{1,3})"),
    # Episode 5 (season from context: parent dir)
    re.compile(r"(?i)episode[\s._\-]*(\d{1,3})"),
    # 205 at start/end of numeric runs like "show.205.title"
    re.compile(r"(?i)[\s._\-](\d)(\d{2})[\s._\-]"),
    # Ep 5
    re.compile(r"(?i)\bep[\s._\-]*(\d{1,3})\b"),
]

# Year like (2024) or .2024.
YEAR_PATTERN = re.compile(r"[\(\[\s._\-](19\d{2}|20\d{2})[\)\]\s._\-]?")
YEAR_EXACT = re.compile(r"^(19\d{2}|20\d{2})$")

MULTI_PART = re.compile(
    r"(?i)[\s._\-]?(?:part|pt|cd|disc|disk)[\s._\-]?(\d{1,2})$"
)

RESOLUTION_PATTERN = re.compile(r"(?i)\b(\d{3,4})p\b|\b(2160|4320)\b")

LANG_TAG = re.compile(r"(?i)[\s._\-\[\(](multi|dual|dub|dubbed|sub|subs|subbed)[\s._\-\]\)]")


@dataclass
class ParsedName:
    """Result of parsing a media filename."""

    title: str = ""
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episode_end: int | None = None  # for S01E02E03 style
    quality: str = ""
    resolution: str = ""
    part: int | None = None
    language_tags: list[str] = field(default_factory=list)


def classify_extension(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in SUBTITLE_EXTENSIONS:
        return "subtitle"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "other"


def strip_release_noise(text: str) -> str:
    """Remove scene/release tokens that pollute titles."""
    text = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", " ", text)  # bracketed groups
    tokens = re.split(r"[\s._\-]+", text)
    cleaned = []
    for token in tokens:
        low = token.lower()
        if not token:
            continue
        if low in QUALITY_TAGS or low in CODEC_TAGS or low in RELEASE_NOISE:
            continue
        if re.fullmatch(r"(?i)(h[\s._]?26[45]|x[\s._]?26[45]|hevc|av1|vp9)", token):
            continue
        if re.fullmatch(r"\d{3,4}p", low):
            continue
        if re.fullmatch(r"[a-fA-F0-9]{8,}", token):  # release hashes
            continue
        if re.fullmatch(r"[a-z]{2}\.[a-z]{2}", low):  # language tags like en.US
            continue
        if re.fullmatch(r"(?i)(aac|ac3|ddp?|dts([\-\.].*)?)(\.?[257]\.[01])?", token):
            continue
        if re.fullmatch(r"(?i)(web|br|dvd|tv)([\-\.]?rip)?", low):
            continue
        cleaned.append(token)
    return " ".join(cleaned).strip(" -_.")


def extract_year(tokens_or_text: str) -> tuple[str, int | None]:
    """Split a title string into (title, year) if a plausible year exists."""
    match = None
    for match in YEAR_PATTERN.finditer(" " + tokens_or_text.strip() + " "):
        candidate = int(match.group(1))
        if 1900 <= candidate <= 2099:
            break
    if not match:
        return tokens_or_text.strip(" -_."), None
    year = int(match.group(1))
    title = tokens_or_text[: max(0, match.start() - 1)].strip(" -_.")
    return title or tokens_or_text.strip(" -_."), year


def detect_quality(filename: str) -> str:
    low = filename.lower()
    res = RESOLUTION_PATTERN.search(low)
    if res:
        return f"{res.group(1) or res.group(2)}p"
    for tag in ("remux", "bluray", "web-dl", "webrip", "hdtv", "dvdrip"):
        if tag in low:
            return tag
    return ""


def subtitle_matches_video(sub_stem: str, video_stem: str) -> bool:
    """movie.en.srt matches movie.mkv; movie.srt too; 'all' subs match anything."""
    if sub_stem == video_stem:
        return True
    if sub_stem.lower().startswith(video_stem.lower() + "."):
        return True
    return False


def season_poster_filename(filename: str) -> int | None:
    """season02-poster.jpg / season 2 poster → season number."""
    stem = filename.rsplit(".", 1)[0].lower()
    match = re.match(r"season[\s._\-]*(all|special|\d{1,2})", stem)
    if not match:
        return None
    if match.group(1).isdigit():
        return int(match.group(1))
    return 0  # all-seasons / specials


def local_artwork_kind(filename: str) -> str | None:
    stem = filename.rsplit(".", 1)[0].lower().strip()
    if season_poster_filename(filename) is not None and "poster" not in stem:
        return "season_poster"
    for kind, names in LOCAL_ARTWORK.items():
        if stem in names:
            return kind
    return None
