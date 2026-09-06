"""Subtitle discovery: external files near the video + embedded tracks."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.database.repositories import Repositories
from app.domain.value_objects import TrackSelection
from app.library.media_detector import subtitle_matches_video

SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
LANG_RE = re.compile(r"\.([a-z]{2,3})(?:\.[a-z]{2})?\.(?:srt|ass|ssa|vtt|sub)$", re.IGNORECASE)


@dataclass
class SubtitleOption:
    label: str
    file_path: str = ""      # external file
    track: TrackSelection | None = None  # embedded track
    language: str = ""

    @property
    def is_embedded(self) -> bool:
        return self.track is not None


class SubtitleService:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def options_for(self, media_file_id: int) -> list[SubtitleOption]:
        """All usable subtitles for a file: embedded tracks + external files."""
        media_file = self.repos.files.get(media_file_id)
        if media_file is None:
            return []
        options: list[SubtitleOption] = []

        # embedded tracks from probe data
        if media_file.probe:
            for track in media_file.probe.get("subtitle_tracks", []):
                language = track.get("language", "")
                options.append(
                    SubtitleOption(
                        label=f"Embedded · {track.get('title') or language or 'track ' + str(track.get('index'))}",
                        track=TrackSelection(
                            index=track.get("index", 0),
                            kind="subtitle",
                            language=language,
                            codec=track.get("codec", ""),
                        ),
                        language=language,
                    )
                )

        # external files (DB-indexed first, then a direct directory look)
        seen_paths = set()
        for candidate in self.repos.files.subtitles_near(media_file.directory, media_file.stem):
            if candidate.path not in seen_paths:
                seen_paths.add(candidate.path)
                options.append(
                    SubtitleOption(
                        label=f"External · {Path(candidate.path).name}",
                        file_path=candidate.path,
                        language=self._language_of(candidate.path),
                    )
                )
        try:
            directory = Path(media_file.path).parent
            if directory.is_dir():
                for entry in sorted(directory.iterdir()):
                    if (
                        entry.is_file()
                        and entry.suffix.lower() in SUBTITLE_EXTENSIONS
                        and entry.name not in seen_paths
                        and not entry.name.startswith(".")
                    ):
                        if subtitle_matches_video(entry.stem, media_file.stem):
                            options.append(
                                SubtitleOption(
                                    label=f"External · {entry.name}",
                                    file_path=str(entry),
                                    language=self._language_of(str(entry)),
                                )
                            )
        except OSError:
            pass
        return options

    @staticmethod
    def _language_of(path: str) -> str:
        match = LANG_RE.search(Path(path).name)
        return match.group(1).lower() if match else ""

    @staticmethod
    def is_subtitle_file(path: str) -> bool:
        return Path(path).suffix.lower() in SUBTITLE_EXTENSIONS and os.path.exists(path)
