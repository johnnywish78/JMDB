"""Media probing via ffprobe (preferred) or ffmpeg.

Probing extracts runtime, video/audio/subtitle streams. It is best-effort:
when no tool is found, or a file is unreadable, probing returns ``None`` and
the library continues to work with filename-derived information only.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

TIMEOUT = 15


def _imageio_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


@dataclass
class ProbeResult:
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    video_codec: str = ""
    audio_tracks: list[dict] = field(default_factory=list)
    subtitle_tracks: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "video_codec": self.video_codec,
            "audio_tracks": self.audio_tracks,
            "subtitle_tracks": self.subtitle_tracks,
        }


class ProbeTools:
    """Locate and run ffprobe/ffmpeg binaries."""

    def __init__(self) -> None:
        self._ffprobe = shutil.which("ffprobe")
        self._ffmpeg = shutil.which("ffmpeg") or _imageio_ffmpeg()

    @property
    def available(self) -> bool:
        return bool(self._ffprobe or self._ffmpeg)

    def describe(self) -> str:
        if self._ffprobe:
            return f"ffprobe ({self._ffprobe})"
        if self._ffmpeg:
            return f"ffmpeg ({self._ffmpeg})"
        return "not available"

    def probe(self, path: str) -> ProbeResult | None:
        if self._ffprobe:
            result = self._probe_with_ffprobe(path)
            if result:
                return result
        if self._ffmpeg:
            return self._probe_with_ffmpeg(path)
        return None

    # -- ffprobe ------------------------------------------------------------
    def _probe_with_ffprobe(self, path: str) -> ProbeResult | None:
        try:
            proc = subprocess.run(
                [
                    self._ffprobe, "-v", "error", "-print_format", "json",
                    "-show_format", "-show_streams", "--", path,
                ],
                capture_output=True, text=True, timeout=TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            return None
        return self._from_ffprobe_json(data)

    def _from_ffprobe_json(self, data: dict) -> ProbeResult:
        result = ProbeResult(raw=data)
        fmt = data.get("format", {})
        try:
            result.duration_seconds = float(fmt.get("duration", 0) or 0)
        except ValueError:
            pass
        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video":
                if not result.video_codec:
                    result.video_codec = stream.get("codec_name", "")
                    result.width = int(stream.get("width", 0) or 0)
                    result.height = int(stream.get("height", 0) or 0)
                    if not result.duration_seconds:
                        try:
                            result.duration_seconds = float(stream.get("duration", 0) or 0)
                        except ValueError:
                            pass
            elif codec_type == "audio":
                result.audio_tracks.append(
                    {
                        "index": int(stream.get("stream_index", len(result.audio_tracks))),
                        "language": (stream.get("tags", {}) or {}).get("language", ""),
                        "codec": stream.get("codec_name", ""),
                        "channels": int(stream.get("channels", 0) or 0),
                        "title": (stream.get("tags", {}) or {}).get("title", ""),
                    }
                )
            elif codec_type == "subtitle":
                result.subtitle_tracks.append(
                    {
                        "index": int(stream.get("stream_index", len(result.subtitle_tracks) + len(result.audio_tracks))),
                        "language": (stream.get("tags", {}) or {}).get("language", ""),
                        "codec": stream.get("codec_name", ""),
                        "title": (stream.get("tags", {}) or {}).get("title", ""),
                    }
                )
        return result

    # -- ffmpeg fallback --------------------------------------------------------
    DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
    STREAM_RE = re.compile(
        r"Stream\s*#\d+:(\d+)(?:\[\w+\])?\s*:\s*(\w+)[^,]*"
        r"(?:.*?,\s*(?:(\w+)" r"(?:\s*\(([^)]*)\))?)?(?:,\s*(\S+))?)?"
    )

    def _probe_with_ffmpeg(self, path: str) -> ProbeResult | None:
        try:
            proc = subprocess.run(
                [self._ffmpeg, "-hide_banner", "-i", "--", path],
                capture_output=True, text=True, timeout=TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        # ffmpeg exits non-zero without an output file; stderr is still useful
        output = proc.stderr
        if "No such file" in output or not output:
            return None
        result = ProbeResult()
        duration = self.DURATION_RE.search(output)
        if duration:
            h, m, s = duration.groups()
            result.duration_seconds = int(h) * 3600 + int(m) * 60 + float(s)
        for match in re.finditer(
            r"Stream #\d+:(\d+).*?: (Video|Audio|Subtitle): ([^,]+)", output
        ):
            index, kind, rest = int(match.group(1)), match.group(2), match.group(3)
            lang_match = re.search(r"\(([a-z]{2,3})\)", output[match.end():match.end() + 120])
            language = lang_match.group(1) if lang_match else ""
            if kind == "Video":
                codec = rest.strip().split(" ")[0].split("(")[0]
                result.video_codec = codec
                dims = re.search(r"(\d{2,5})x(\d{2,5})", rest)
                if dims:
                    result.width, result.height = int(dims.group(1)), int(dims.group(2))
            elif kind == "Audio":
                result.audio_tracks.append(
                    {"index": index, "language": language, "codec": rest.strip().split(" ")[0], "channels": 0, "title": ""}
                )
            elif kind == "Subtitle":
                result.subtitle_tracks.append(
                    {"index": index, "language": language, "codec": rest.strip().split(" ")[0], "title": ""}
                )
        if result.duration_seconds == 0 and not result.video_codec and not result.audio_tracks:
            return None
        return result


def safe_start_time_args(player_kind: str, position_seconds: float) -> list[str]:
    """Player-specific CLI args to resume at a position (external backend)."""
    if position_seconds <= 0:
        return []
    if player_kind == "vlc":
        return ["--start-time", f"{position_seconds:.1f}"]
    if player_kind == "mpv":
        return ["--start", f"+{position_seconds:.1f}"]
    if player_kind == "ffplay":
        return ["-ss", f"{position_seconds:.1f}"]
    return []
