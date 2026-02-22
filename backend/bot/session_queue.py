"""
session_queue.py — In-memory per-guild track session.

Lavalink remains the audio engine, but we own the ordered track list and
the current playback index. This gives us:
  - True "previous track" support
  - Played tracks stay visible in the queue
  - Click-to-jump anywhere in the list
  - Shuffle and repeat managed here, not via Lavalink
  - Session disappears when the bot leaves (no DB needed)
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional, Literal

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TrackInfo:
    title: str
    author: str
    uri: str
    thumbnail: Optional[str]
    duration: int          # milliseconds
    encoded: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "author": self.author,
            "uri": self.uri,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "encoded": self.encoded,
        }


@dataclass
class GuildSession:
    guild_id: int
    tracks: list[TrackInfo] = field(default_factory=list)
    current_index: int = -1
    repeat_mode: Literal["off", "one", "all"] = "off"
    shuffle_enabled: bool = False
    # Original track order (preserved when shuffle is toggled)
    _original_tracks: list[TrackInfo] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Mutation helpers
    # ------------------------------------------------------------------ #

    def add(self, track: TrackInfo) -> int:
        """Append track; return its index."""
        self.tracks.append(track)
        if self.shuffle_enabled:
            self._original_tracks.append(track)
        return len(self.tracks) - 1

    def set_index(self, i: int) -> Optional[TrackInfo]:
        """Set current_index; return the track at that position (or None)."""
        if 0 <= i < len(self.tracks):
            self.current_index = i
            return self.tracks[i]
        return None

    def advance(self) -> Optional[TrackInfo]:
        """Move to the next track according to repeat/shuffle state.
        Returns the next track, or None if at end (and repeat is off)."""
        if not self.tracks:
            return None

        if self.repeat_mode == "one":
            # Stay on the same track
            return self.current

        next_idx = self.current_index + 1

        if self.repeat_mode == "all" and next_idx >= len(self.tracks):
            # Loop back to the start
            next_idx = 0

        return self.set_index(next_idx)

    def previous(self) -> Optional[TrackInfo]:
        """Move to the previous track; return it (or None if at start)."""
        if self.repeat_mode == "all" and self.current_index == 0:
            return self.set_index(len(self.tracks) - 1)
        return self.set_index(self.current_index - 1)

    @property
    def current(self) -> Optional[TrackInfo]:
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def shuffle(self):
        """Shuffle the upcoming (unplayed) tracks, preserving played ones."""
        if not self.tracks:
            return
        # Save original order (unshuffled) for toggling off
        self._original_tracks = list(self.tracks)
        self.shuffle_enabled = True

        played = self.tracks[:self.current_index + 1]
        upcoming = self.tracks[self.current_index + 1:]
        random.shuffle(upcoming)
        self.tracks = played + upcoming

    def unshuffle(self):
        """Restore original track order."""
        if not self._original_tracks:
            return
        current_track = self.current
        self.tracks = list(self._original_tracks)
        # Try to maintain current position
        if current_track:
            try:
                self.current_index = self.tracks.index(current_track)
            except ValueError:
                self.current_index = min(self.current_index, len(self.tracks) - 1)
        self.shuffle_enabled = False
        self._original_tracks = []

    def clear(self):
        self.tracks = []
        self._original_tracks = []
        self.current_index = -1
        self.repeat_mode = "off"
        self.shuffle_enabled = False

    def to_api(self) -> dict:
        return {
            "tracks": [t.to_dict() for t in self.tracks],
            "current_index": self.current_index,
            "repeat_mode": self.repeat_mode,
            "shuffle_enabled": self.shuffle_enabled,
        }


# ---------------------------------------------------------------------------
# Global session store
# ---------------------------------------------------------------------------

_sessions: dict[int, GuildSession] = {}


def get(guild_id: int) -> GuildSession:
    """Return the session for a guild, creating it if necessary."""
    if guild_id not in _sessions:
        _sessions[guild_id] = GuildSession(guild_id=guild_id)
    return _sessions[guild_id]


def clear(guild_id: int):
    """Remove the session for a guild (call on bot disconnect)."""
    _sessions.pop(guild_id, None)


def from_wavelink_track(track) -> TrackInfo:
    """Convert a wavelink.Playable to a TrackInfo."""
    return TrackInfo(
        title=track.title or "Unknown",
        author=track.author or "Unknown",
        uri=track.uri or "",
        thumbnail=getattr(track, "artwork", None) or getattr(track, "preview_url", None),
        duration=track.length or 0,
        encoded=track.encoded if hasattr(track, "encoded") else None,
    )
