"""Filesystem walking — conservative, non-destructive, Qt-free."""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".webm", ".mpg", ".mpeg", ".m2ts"}
AUDIO_EXTS = {".mp3", ".flac", ".aac", ".ogg", ".opus", ".wav", ".m4a", ".wma"}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".sub", ".vtt"}

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}


def iter_media_files(root: Path) -> Iterator[Path]:
    root = Path(root)
    if root.is_file() and is_media(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if is_media(p):
                yield p


def is_media(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS or path.suffix.lower() in AUDIO_EXTS


def subtitle_candidates(video: Path) -> list[Path]:
    return [video.with_suffix(ext) for ext in SUBTITLE_EXTS if video.with_suffix(ext).exists()]
