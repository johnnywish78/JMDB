"""Playback session: one item being played, with its DB bookkeeping."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.value_objects import PlayableItem


@dataclass
class PlaybackSession:
    item: PlayableItem
    profile_id: int
    history_id: Optional[int] = None
    started_at: float = field(default_factory=time.monotonic)
    started_wall: datetime = field(default_factory=datetime.utcnow)
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    last_save: float = 0.0
    completed: bool = False
    resumed: bool = False
    start_position: float = 0.0
    queue: list[PlayableItem] = field(default_factory=list)
    queue_index: int = 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def current(self) -> PlayableItem:
        return self.queue[self.queue_index] if self.queue and 0 <= self.queue_index < len(self.queue) else self.item

    def next_item(self) -> Optional[PlayableItem]:
        if self.queue and self.queue_index + 1 < len(self.queue):
            return self.queue[self.queue_index + 1]
        return None

    def previous_item(self) -> Optional[PlayableItem]:
        if self.queue and self.queue_index - 1 >= 0:
            return self.queue[self.queue_index - 1]
        return None
