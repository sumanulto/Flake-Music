from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from backend.database.core.db import get_db
from backend.database.models.models import Playlist, PlaylistTrack, User
from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playlist", tags=["Playlist"])

# Pydantic Models
class PlaylistCreate(BaseModel):
    name: str
    user_id: int # Discord ID
    guild_id: Optional[int] = None

class TrackAdd(BaseModel):
    track_data: dict # Full wavelink track object or similar
    playlist_id: int

class PlaylistResponse(BaseModel):
    id: int
    name: str
    is_liked_songs: bool
    track_count: int

class TrackResponse(BaseModel):
    id: int
    track_data: dict
    added_at: Optional[str]

class CheckContainmentRequest(BaseModel):
    user_id: int
    uri: str

# Routes

@router.post("/create")
async def create_playlist(playlist: PlaylistCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists, if not create (lazy load user)
    # Actually, we should probably ensure the user exists first.
    # For now, let's assume we might need to create the user entry if it's their first playlist?
    # Or just check if exists.
    
    user_stmt = select(User).where(User.id == playlist.user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    
    if not user:
         # Create user stub
         user = User(id=playlist.user_id, username="Unknown")
         db.add(user)
         await db.commit() # Commit user first
    
    new_playlist = Playlist(
        name=playlist.name,
        user_id=playlist.user_id,
        guild_id=playlist.guild_id,
        is_liked_songs=False
    )
    db.add(new_playlist)
    await db.commit()
    await db.refresh(new_playlist)
    return {"id": new_playlist.id, "name": new_playlist.name}

@router.get("/user/{user_id}")
async def get_user_playlists(user_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Playlist).where(Playlist.user_id == user_id).options(selectinload(Playlist.tracks))
    result = await db.execute(stmt)
    playlists = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "is_liked_songs": p.is_liked_songs,
            "track_count": len(p.tracks),
            "tracks": [
                {
                    "id": t.id,
                    "track_data": t.track_data,
                    "added_at": t.added_at,
                }
                for t in p.tracks
            ],
        }
        for p in playlists
    ]

@router.get("/{playlist_id}")
async def get_playlist(playlist_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Playlist).where(Playlist.id == playlist_id).options(selectinload(Playlist.tracks))
    result = await db.execute(stmt)
    playlist = result.scalar_one_or_none()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
        
    return {
        "id": playlist.id,
        "name": playlist.name,
        "is_liked_songs": playlist.is_liked_songs,
        "tracks": [
            {
                "id": t.id,
                "track_data": t.track_data,
                "added_at": t.added_at
            }
            for t in playlist.tracks
        ]
    }

@router.post("/{playlist_id}/add")
async def add_track(playlist_id: int, track: TrackAdd, db: AsyncSession = Depends(get_db)):
    # Verify playlist exists
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    playlist = (await db.execute(stmt)).scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Normalize track data to nested format
    final_track_data = track.track_data
    if "info" not in final_track_data:
        # It's flat format from website, convert to nested
        final_track_data = {
            "encoded": None,
            "info": {
                "title": track.track_data.get("title"),
                "author": track.track_data.get("author") or track.track_data.get("artist"),
                "uri": track.track_data.get("uri"),
                "length": track.track_data.get("duration") if "duration" in track.track_data else track.track_data.get("length"),
                "is_stream": track.track_data.get("is_stream", False),
                "thumbnail": track.track_data.get("thumbnail")
            }
        }

    new_track = PlaylistTrack(
        playlist_id=playlist_id,
        track_data=final_track_data,
        added_at=datetime.utcnow().isoformat()
    )
    db.add(new_track)
    await db.commit()
    return {"success": True, "track_id": new_track.id}

@router.delete("/{playlist_id}/remove/{track_db_id}")
async def remove_track(playlist_id: int, track_db_id: int, db: AsyncSession = Depends(get_db)):
    stmt = delete(PlaylistTrack).where(PlaylistTrack.id == track_db_id, PlaylistTrack.playlist_id == playlist_id)
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Track not found in playlist")
    return {"success": True}

@router.post("/like")
async def like_track(user_id: int, track_data: dict, db: AsyncSession = Depends(get_db)):
    # Find or Create "Liked Songs" playlist for user
    stmt = select(Playlist).where(Playlist.user_id == user_id, Playlist.is_liked_songs == True)
    playlist = (await db.execute(stmt)).scalar_one_or_none()
    
    if not playlist: # Create if doesn't exist
         # Ensure user exists
         user_stmt = select(User).where(User.id == user_id)
         user = (await db.execute(user_stmt)).scalar_one_or_none()
         if not user:
             user = User(id=user_id, username="Unknown")
             db.add(user)
             await db.commit()
             
         playlist = Playlist(
             name="Liked Songs",
             user_id=user_id,
             is_liked_songs=True
         )
         db.add(playlist)
         await db.commit()
         await db.refresh(playlist)

    # Normalize track data to nested format
    final_track_data = track_data
    if "info" not in final_track_data:
        # It's flat format from website, convert to nested
        final_track_data = {
            "encoded": None,
            "info": {
                "title": track_data.get("title"),
                "author": track_data.get("author") or track_data.get("artist"),
                "uri": track_data.get("uri"),
                "length": track_data.get("duration") if "duration" in track_data else track_data.get("length"),
                "is_stream": track_data.get("is_stream", False),
                "thumbnail": track_data.get("thumbnail")
            }
        }

    # Check if track already exists (duplicate check? based on uri?)
    # track_data should have 'info' or 'uri'
    uri = final_track_data.get('info', {}).get('uri')
    
    # If we want to toggle, we need to check existence.
    # Complex with JSON, but we can iterate or use a specialized query if we extracted URI.
    # For now, let's just add (simple 'like'). Or check all tracks in playlist.
    # Optimization: Extract URI to a column later.
    
    # Let's verify if encoded uri matches.
    # Iterate for now (inefficient for large lists but fine for MVP)
    # Or just add blindly? User asked for "Love icon work". Usually a toggle.
    
    # Let's try to find if it exists (Toggle logic)
    # We need to load tracks
    await db.refresh(playlist, attribute_names=['tracks'])
    
    found_track = None
    for t in playlist.tracks:
        t_info = t.track_data.get('info', t.track_data) # Handle legacy flat data in DB
        t_uri = t_info.get('uri')
        if t_uri == uri:
            found_track = t
            break
    
    if found_track:
        # Unlike
        await db.delete(found_track)
        await db.commit()
        return {"liked": False, "msg": "Removed from Liked Songs"}
    else:
        # Like
        new_track = PlaylistTrack(
            playlist_id=playlist.id,
            track_data=final_track_data,
            added_at=datetime.utcnow().isoformat()
        )
        db.add(new_track)
        await db.commit()
        return {"liked": True, "msg": "Added to Liked Songs"}

@router.post("/check-containment")
async def check_track_containment(request: CheckContainmentRequest, db: AsyncSession = Depends(get_db)):
    # Optimized query to search within JSON
    # Use SQLAlchemy JSON path operators which work across supported dialects
    stmt = (
        select(Playlist.id, PlaylistTrack.id, Playlist.name, Playlist.is_liked_songs)
        .join(PlaylistTrack, Playlist.id == PlaylistTrack.playlist_id)
        .where(
            Playlist.user_id == request.user_id,
            # Check both possible locations for URI in the JSON blob
            (PlaylistTrack.track_data['info']['uri'].as_string() == request.uri) | 
            (PlaylistTrack.track_data['uri'].as_string() == request.uri)
        )
    )
    
    try:
        result = await db.execute(stmt)
        rows = result.all()
    except Exception as e:
        # Fallback for SQLite or other DBs if JSON operators fail, or general error
        print(f"Error in optimized query: {e}")
        return []

    containing_playlists = []
    for row in rows:
        containing_playlists.append({
            "playlist_id": row[0],
            "track_db_id": row[1],
            "playlist_name": row[2],
            "is_liked_songs": row[3]
        })

    return containing_playlists


# ---------------------------------------------------------------------------
# Playlist Import via SSE (Server-Sent Events)
# ---------------------------------------------------------------------------

class ImportPlaylistRequest(BaseModel):
    url: str
    # Accept as str so the frontend can send the raw Discord snowflake without
    # JavaScript's Number() truncating it beyond Number.MAX_SAFE_INTEGER.
    user_id: str


@router.post("/import")
async def import_playlist_sse(request: ImportPlaylistRequest):
    """
    Import tracks from a playlist URL and stream progress via Server-Sent Events.

    Supported sources:
      • YouTube / any yt-dlp-supported URL  — uses yt-dlp (flat extraction)
      • Spotify playlist / album / track    — uses Spotify Web API (no DRM issues)

    All tracks are built in-memory; only 2 DB round-trips happen regardless
    of playlist size: one to create the playlist, one bulk-insert of all tracks.
    """
    from backend.utils.spotify import is_spotify_url, fetch_spotify_playlist
    from backend.utils.youtube import extract_info
    from backend.database.core.db import async_session_factory

    # Python int is arbitrary-width — full snowflake precision preserved.
    user_id_int = int(request.user_id)

    # ── Detect source ────────────────────────────────────────────────────────
    use_spotify = is_spotify_url(request.url)

    async def event_generator():
        async with async_session_factory() as db:
            try:
                # ── 1. Fetch playlist info ───────────────────────────────────
                if use_spotify:
                    try:
                        spotify_result = await fetch_spotify_playlist(request.url)
                    except ValueError as ve:
                        yield f"data: {json.dumps({'type': 'error', 'message': str(ve)})}\n\n"
                        return
                    if not spotify_result:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Could not parse Spotify URL. Supported: playlist, album, track links.'})}\n\n"
                        return
                    playlist_name = spotify_result.name
                    total = spotify_result.total
                else:
                    info = await extract_info(request.url)
                    if not info:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Could not extract playlist from the given URL. Please check the URL and try again.'})}\n\n"
                        return
                    playlist_name = (
                        info.get("title")
                        or info.get("playlist_title")
                        or "Imported Playlist"
                    )
                    entries = list(info.get("entries") or [])
                    if not entries and info.get("id"):
                        entries = [info]
                    if not entries:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'No tracks found at that URL.'})}\n\n"
                        return
                    total = len(entries)

                # ── 2. Ensure user row exists (1 read, maybe 1 write) ────────
                user_stmt = select(User).where(User.id == user_id_int)
                user = (await db.execute(user_stmt)).scalar_one_or_none()
                if not user:
                    user = User(id=user_id_int, username="Unknown")
                    db.add(user)
                    await db.commit()

                # ── 3. Create the playlist (1 write) ─────────────────────────
                new_playlist = Playlist(
                    name=playlist_name,
                    user_id=user_id_int,
                    is_liked_songs=False,
                )
                db.add(new_playlist)
                await db.commit()
                await db.refresh(new_playlist)

                yield f"data: {json.dumps({'type': 'start', 'playlist_id': new_playlist.id, 'playlist_name': playlist_name, 'total': total})}\n\n"

                # ── 4. Build track objects in-memory, stream progress ────────
                now = datetime.utcnow().isoformat()
                track_objects: list = []

                if use_spotify:
                    # Async iterator — pages fetched lazily from Spotify API
                    i = 0
                    async for track_entry in spotify_result.tracks:
                        title    = track_entry.get("title", "Unknown Track")
                        author   = track_entry.get("author", "Unknown")
                        uri      = track_entry.get("uri", "")
                        duration_secs = track_entry.get("duration_secs", 0)
                        thumbnail = track_entry.get("thumbnail")

                        track_objects.append(PlaylistTrack(
                            playlist_id=new_playlist.id,
                            track_data={
                                "encoded": None,
                                "info": {
                                    "title": title,
                                    "author": author,
                                    "uri": uri,
                                    "length": int(duration_secs * 1000) if duration_secs else 0,
                                    "is_stream": False,
                                    "thumbnail": thumbnail,
                                },
                            },
                            added_at=now,
                        ))

                        i += 1
                        yield f"data: {json.dumps({'type': 'track', 'current': i, 'total': total, 'track_title': title})}\n\n"
                else:
                    # yt-dlp entries — all in memory already
                    for i, entry in enumerate(entries):
                        if not entry:
                            continue

                        title = (
                            entry.get("title")
                            or entry.get("fulltitle")
                            or "Unknown Track"
                        )
                        raw_uri = (
                            entry.get("webpage_url")
                            or entry.get("url")
                            or ""
                        )
                        if raw_uri and not raw_uri.startswith("http"):
                            raw_uri = f"https://www.youtube.com/watch?v={raw_uri}"

                        author = (
                            entry.get("uploader")
                            or entry.get("channel")
                            or entry.get("artist")
                            or "Unknown"
                        )
                        duration_secs = entry.get("duration") or 0

                        thumbnail = entry.get("thumbnail")
                        if not thumbnail:
                            thumbs = entry.get("thumbnails") or []
                            if thumbs:
                                last = thumbs[-1]
                                thumbnail = last.get("url") if isinstance(last, dict) else last
                        elif isinstance(thumbnail, dict):
                            thumbnail = thumbnail.get("url")

                        track_objects.append(PlaylistTrack(
                            playlist_id=new_playlist.id,
                            track_data={
                                "encoded": None,
                                "info": {
                                    "title": title,
                                    "author": author,
                                    "uri": raw_uri,
                                    "length": int(duration_secs * 1000) if duration_secs else 0,
                                    "is_stream": False,
                                    "thumbnail": thumbnail,
                                },
                            },
                            added_at=now,
                        ))

                        yield f"data: {json.dumps({'type': 'track', 'current': i + 1, 'total': total, 'track_title': title})}\n\n"

                # ── 5. Single bulk-insert for ALL tracks (1 DB write total) ──
                db.add_all(track_objects)
                await db.commit()

                yield f"data: {json.dumps({'type': 'done', 'playlist_id': new_playlist.id, 'playlist_name': playlist_name, 'total': len(track_objects)})}\n\n"

            except Exception as exc:
                logger.error(f"Playlist import error: {exc}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    # Verify ownership
    stmt = select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user_id)
    playlist = (await db.execute(stmt)).scalar_one_or_none()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found or access denied")
        
    await db.delete(playlist)
    await db.commit()
    
    return {"success": True, "message": f"Playlist {playlist.name} deleted"}
