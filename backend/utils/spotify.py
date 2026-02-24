"""
spotify.py — Fetch playlist/album track metadata from the Spotify Web API.

Uses the Client-Credentials flow (no user login needed) via httpx.
No DRM content is downloaded — only track metadata (title, artist, duration,
cover art) is retrieved so tracks can be stored and later searched on YouTube.

Required env vars:
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import time
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

_SPOTIFY_RE = re.compile(
    r"(?:https?://open\.spotify\.com|spotify:)"
    r"[/:](?P<type>playlist|album|track)[/:](?P<id>[A-Za-z0-9]+)"
)


def is_spotify_url(url: str) -> bool:
    return bool(_SPOTIFY_RE.search(url))


def parse_spotify_url(url: str) -> tuple[str, str] | None:
    """Return (type, spotify_id) or None if not a recognisable Spotify URL."""
    m = _SPOTIFY_RE.search(url)
    if not m:
        return None
    return m.group("type"), m.group("id")


# ---------------------------------------------------------------------------
# Token cache (simple in-process cache; safe for single-process servers)
# ---------------------------------------------------------------------------

_token_cache: dict = {"token": None, "expires_at": 0.0}


async def _get_token(client: httpx.AsyncClient) -> str:
    """Return a valid client-credentials token, refreshing if needed."""
    if time.monotonic() < _token_cache["expires_at"] and _token_cache["token"]:
        return _token_cache["token"]

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")

    if not client_id or not client_secret or client_id == "your_spotify_client_id_here":
        raise ValueError(
            "Spotify credentials not configured. "
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env file. "
            "Get them at https://developer.spotify.com/dashboard"
        )

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = await client.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {credentials}"},
        data={"grant_type": "client_credentials"},
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    # Subtract 30 s buffer so we refresh before expiry
    _token_cache["expires_at"] = time.monotonic() + data["expires_in"] - 30
    return _token_cache["token"]


# ---------------------------------------------------------------------------
# Track normaliser
# ---------------------------------------------------------------------------

def _normalise_track(item: dict) -> dict | None:
    """Convert a Spotify track object (or playlist track wrapper) to our format."""
    # Playlist tracks are wrapped: {"track": {...}}
    track = item.get("track") or item
    if not track or not track.get("id"):
        return None  # local file or null track

    name = track.get("name", "Unknown Track")
    artists = track.get("artists") or []
    artist = ", ".join(a["name"] for a in artists if a.get("name")) or "Unknown"
    duration_ms = track.get("duration_ms") or 0

    # Thumbnail: prefer album images
    images = (track.get("album") or {}).get("images") or []
    thumbnail = images[0]["url"] if images else None

    # Spotify URI — we store it but don't stream from it; bot searches YTM by title+artist
    uri = (track.get("external_urls") or {}).get("spotify") or ""

    return {
        "title": name,
        "author": artist,
        "uri": uri,
        "duration_secs": duration_ms / 1000,
        "thumbnail": thumbnail,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SpotifyImportResult:
    """Holds the playlist name + lazily-paginated async iterator over tracks."""
    def __init__(self, name: str, total: int, iterator: AsyncIterator[dict]):
        self.name = name
        self.total = total
        self.tracks = iterator


async def fetch_spotify_playlist(url: str) -> SpotifyImportResult | None:
    """
    Given a Spotify playlist or album URL, return a SpotifyImportResult whose
    `.tracks` is an async iterator yielding normalised track dicts one at a time.

    Returns None if the URL is not a Spotify URL.
    Raises ValueError for bad credentials, httpx.HTTPError for API failures.
    """
    parsed = parse_spotify_url(url)
    if not parsed:
        return None
    resource_type, resource_id = parsed

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        if resource_type == "playlist":
            # Fetch playlist metadata — no fields filter; some curated playlists
            # return 404 when a fields param is supplied even though they exist.
            meta = await client.get(
                f"https://api.spotify.com/v1/playlists/{resource_id}",
                headers=headers,
            )
            if meta.status_code == 404:
                raise ValueError(
                    "Spotify returned 404 for that playlist. "
                    "Spotify-curated / algorithmic playlists (e.g. Discover Weekly, "
                    "Daily Mix, Top Hits) are not accessible via the Spotify Web API "
                    "for third-party apps. Please try a playlist you created or one "
                    "shared by another user."
                )
            meta.raise_for_status()
            meta_data = meta.json()
            playlist_name = meta_data.get("name", "Spotify Playlist")
            total = (meta_data.get("tracks") or {}).get("total", 0)

        elif resource_type == "album":
            meta = await client.get(
                f"https://api.spotify.com/v1/albums/{resource_id}",
                headers=headers,
            )
            if meta.status_code == 404:
                raise ValueError(
                    "Spotify returned 404 for that album. "
                    "Please check the URL and try again."
                )
            meta.raise_for_status()
            meta_data = meta.json()
            playlist_name = meta_data.get("name", "Spotify Album")
            total = (meta_data.get("tracks") or {}).get("total", 0)

        elif resource_type == "track":
            # Single track — wrap it like a 1-item playlist
            meta = await client.get(
                f"https://api.spotify.com/v1/tracks/{resource_id}",
                headers=headers,
            )
            if meta.status_code == 404:
                raise ValueError(
                    "Spotify returned 404 for that track. "
                    "Please check the URL and try again."
                )
            meta.raise_for_status()
            single = meta.json()
            track_data = _normalise_track(single)
            if not track_data:
                return None
            playlist_name = track_data["title"]
            total = 1

            async def _single_iter():
                yield track_data

            return SpotifyImportResult(playlist_name, 1, _single_iter())

        else:
            return None

    # Return result with a lazy async generator so the SSE loop can yield
    # progress events between pages without buffering all tracks at once.
    return SpotifyImportResult(
        playlist_name,
        total,
        _paginate_tracks(resource_type, resource_id, total),
    )


async def _paginate_tracks(
    resource_type: str,
    resource_id: str,
    total: int,
    page_size: int = 100,
) -> AsyncIterator[dict]:
    """Async generator: yields one normalised track dict per track."""
    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        offset = 0
        while offset < total:
            if resource_type == "playlist":
                url = f"https://api.spotify.com/v1/playlists/{resource_id}/tracks"
                params = {
                    "limit": page_size,
                    "offset": offset,
                    "fields": "items(track(id,name,artists,duration_ms,album(images),external_urls))",
                }
            else:  # album
                url = f"https://api.spotify.com/v1/albums/{resource_id}/tracks"
                params = {"limit": page_size, "offset": offset}

            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            page = resp.json()
            items = page.get("items") or []

            for item in items:
                track_data = _normalise_track(item)
                if track_data:
                    yield track_data

            offset += len(items)
            if not items:
                break
