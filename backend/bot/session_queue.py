"""
session_queue.py — In-memory per-guild track session.

Lavalink remains the audio engine, but we own the ordered track list and
the current playback index. This gives us:
  - True "previous track" support
  - Played tracks stay visible in the queue
  - Click-to-jump anywhere in the list
  - Session disappears when the bot leaves (no DB needed)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

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
    encoded: Optional[str] = None   # Lavalink encoded track (for direct play)

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
    current_index: int = -1   # -1 = nothing playing

    # ------------------------------------------------------------------ #
    # Mutation helpers
    # ------------------------------------------------------------------ #

    def add(self, track: TrackInfo) -> int:
        """Append track; return its index."""
        self.tracks.append(track)
        return len(self.tracks) - 1

    def set_index(self, i: int) -> Optional[TrackInfo]:
        """Set current_index; return the track at that position (or None)."""
        if 0 <= i < len(self.tracks):
            self.current_index = i
            return self.tracks[i]
        return None

    def advance(self) -> Optional[TrackInfo]:
        """Move to the next track; return it (or None if end of queue)."""
        return self.set_index(self.current_index + 1)

    def previous(self) -> Optional[TrackInfo]:
        """Move to the previous track; return it (or None if at start)."""
        return self.set_index(self.current_index - 1)

    @property
    def current(self) -> Optional[TrackInfo]:
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def clear(self):
        self.tracks = []
        self.current_index = -1

    def to_api(self) -> dict:
        return {
            "tracks": [t.to_dict() for t in self.tracks],
            "current_index": self.current_index,
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
    """Convert a wavelink.Playable to a TrackInfo dict."""
    return TrackInfo(
        title=track.title or "Unknown",
        author=track.author or "Unknown",
        uri=track.uri or "",
        thumbnail=getattr(track, "artwork", None) or getattr(track, "preview_url", None),
        duration=track.length or 0,
        encoded=track.encoded if hasattr(track, "encoded") else None,
    )
