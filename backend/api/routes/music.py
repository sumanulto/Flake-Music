import wavelink
import logging
from fastapi import APIRouter, Depends, HTTPException
from backend.api.middleware.auth_middleware import get_current_user
from backend.database.models.models import User
from backend.bot.core.bot import bot
from backend.api.schemas.music import PlayRequest, MusicStatus, VolumeRequest, SeekRequest
from typing import cast

router = APIRouter(prefix="/music", tags=["Music"])
logger = logging.getLogger(__name__)

def get_player(guild_id: int) -> wavelink.Player:
    logger.info(f"Attempting to get player for guild {guild_id}")
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error(f"Guild {guild_id} not found in bot cache. Available guilds: {[g.id for g in bot.guilds]}")
        raise HTTPException(status_code=404, detail="Guild not found")
    
    player = cast(wavelink.Player, guild.voice_client)
    if not player:
        logger.error(f"Bot is not in a voice channel for guild {guild_id}")
        raise HTTPException(status_code=400, detail="Bot is not in a voice channel")
    return player

async def update_discord_interface(guild_id: int, force_new: bool = False):
    cog = bot.get_cog("Music")
    if cog and hasattr(cog, "refresh_player_interface"):
        await cog.refresh_player_interface(guild_id, force_new=force_new)

@router.post("/play")
async def play_music(request: PlayRequest, current_user: User = Depends(get_current_user)):
    # Note: For security, we should check if current_user is in the same voice channel or has permissions
    try:
        logger.info(f"Received play request: {request}")
        player = get_player(request.guild_id)

        search_query = request.query.strip()

        if search_query.startswith("ytmsearch:"):
            search_query = search_query[len("ytmsearch:"):].strip()

        if search_query.startswith("ytsearch:ytsearch:"):
            search_query = f"ytsearch:{search_query[len('ytsearch:ytsearch:'):].strip()}"

        if search_query.startswith("ytsearch:") and search_query[len("ytsearch:"):].startswith("http"):
            search_query = search_query[len("ytsearch:"):].strip()

        tracks = await wavelink.Playable.search(search_query)
        if not tracks:
            logger.warning(f"No tracks found for query: {search_query}")
            raise HTTPException(status_code=404, detail="No tracks found")
        
        if isinstance(tracks, wavelink.Playlist):
            await player.queue.put_wait(tracks)
            msg = f"Added playlist {tracks.name}"
        else:
            track = tracks[0]
            await player.queue.put_wait(track)
            msg = f"Added {track.title}"
            
        if not player.playing:
            await player.play(player.queue.get())
            
        await update_discord_interface(request.guild_id, force_new=False)
        return {"message": msg}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"API Play Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{guild_id}/pause")
async def pause_music(guild_id: int, current_user: User = Depends(get_current_user)):
    player = get_player(guild_id)
    await player.pause(not player.paused)
    await update_discord_interface(guild_id, force_new=False)
    return {"message": "Toggled pause"}

@router.post("/{guild_id}/skip")
async def skip_music(guild_id: int, current_user: User = Depends(get_current_user)):
    player = get_player(guild_id)
    if not player.playing:
         raise HTTPException(status_code=400, detail="Not playing")
    await player.skip(force=True)
    await update_discord_interface(guild_id, force_new=False)
    return {"message": "Skipped track"}

@router.post("/{guild_id}/volume")
async def set_volume(guild_id: int, request: VolumeRequest, current_user: User = Depends(get_current_user)):
    player = get_player(guild_id)
    await player.set_volume(max(0, min(100, request.volume)))
    await update_discord_interface(guild_id, force_new=False)
    return {"message": f"Volume set to {request.volume}"}

@router.put("/{guild_id}/seek")
async def seek_music(guild_id: int, request: SeekRequest, current_user: User = Depends(get_current_user)):
    player = get_player(guild_id)
    if not player.playing:
         raise HTTPException(status_code=400, detail="Not playing")
    await player.seek(request.position)
    await update_discord_interface(guild_id, force_new=False)
    return {"message": f"Seeked to {request.position}ms"}

@router.get("/{guild_id}")
async def get_music_status(guild_id: int, current_user: User = Depends(get_current_user)):
    # This might fail if bot isn't in guild, so handle gracefully
    guild = bot.get_guild(guild_id)
    if not guild:
         raise HTTPException(status_code=404, detail="Guild not found")
    
    player = cast(wavelink.Player, guild.voice_client)
    if not player:
        return {
            "guild_id": guild_id,
            "is_playing": False,
            "title": None,
            "author": None,
            "position": 0,
            "duration": 0,
            "volume": 100,
            "queue": []
        }
    
    current = player.current
    return {
        "guild_id": guild_id,
        "is_playing": player.playing and not player.paused,
        "title": current.title if current else None,
        "author": current.author if current else None,
        "position": player.position,
        "duration": current.length if current else 0,
        "volume": player.volume,
        "queue": [t.title for t in player.queue]
    }
