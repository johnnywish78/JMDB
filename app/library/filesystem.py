"""Filesystem walking and safe path utilities."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class FoundFile:
    path: str
    filename: str
    directory: str
    size_bytes: int
    mtime_ns: int
    extension: str


def is_valid_media_root(path: str) -> bool:
    """A media root must exist and be a directory we can read."""
    try:
        p = Path(path).expanduser().resolve()
        return p.is_dir() and os.access(p, os.R_OK)
    except (OSError, ValueError):
        return False


def walk_files(
    root: str,
    include_hidden: bool = False,
    follow_symlinks: bool = False,
    report_dir=None,
) -> Iterator[FoundFile]:
    """Yield FoundFile records under root.

    Robust against permission errors and races (files vanishing mid-scan):
    unreadable subtrees are skipped and reported, not fatal.
    """
    root_path = Path(root)
    for dirpath, dirnames, filenames in os.walk(
        root_path, topdown=True, followlinks=follow_symlinks, onerror=None
    ):
        dir_path = Path(dirpath)
        if not include_hidden:
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in ("$RECYCLE.BIN", "System Volume Information")
            ]
        else:
            dirnames[:] = [d for d in dirnames if d not in ("$RECYCLE.BIN", "System Volume Information")]
        for filename in filenames:
            if filename.startswith("."):
                continue
            full = dir_path / filename
            try:
                stat = full.stat()
            except OSError:
                continue
            yield FoundFile(
                path=str(full),
                filename=filename,
                directory=str(dir_path),
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                extension=full.suffix.lower().lstrip("."),
            )


def human_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def common_root(paths: list[str]) -> str:
    """Deepest common directory of several paths (used by duplicate reports)."""
    if not paths:
        return ""
    parts = [Path(p).parts for p in paths]
    common = parts[0]
    for other in parts[1:]:
        i = 0
        while i < min(len(common), len(other)) and common[i] == other[i]:
            i += 1
        common = common[:i]
    return str(Path(*common)) if common else ""
