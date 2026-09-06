"""Audio track discovery from probe data."""
from __future__ import annotations

from app.database.repositories import Repositories
from app.domain.value_objects import TrackSelection


class AudioService:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def tracks_for(self, media_file_id: int) -> list[TrackSelection]:
        media_file = self.repos.files.get(media_file_id)
        if media_file is None or not media_file.probe:
            return []
        out = []
        for track in media_file.probe.get("audio_tracks", []):
            label = track.get("title") or track.get("language") or f"Track {track.get('index')}"
            channels = track.get("channels")
            if channels:
                label += f" · {channels}ch"
            if track.get("codec"):
                label += f" ({track['codec']})"
            out.append(
                TrackSelection(
                    index=track.get("index", 0),
                    kind="audio",
                    language=track.get("language", ""),
                    title=label,
                    codec=track.get("codec", ""),
                )
            )
        return out
