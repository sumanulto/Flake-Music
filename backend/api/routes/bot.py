from fastapi import APIRouter, HTTPException, BackgroundTasks
from backend.bot.core.bot import bot
import wavelink
from typing import Optional, List, Any
import logging
from pydantic import BaseModel

router = APIRouter(prefix="/bot", tags=["Bot"])
logger = logging.getLogger(__name__)

class ControlRequest(BaseModel):
    action: str
    guildId: str
    query: Optional[str] = None
    enabled: Optional[bool] = None # For shuffle
    mode: Optional[str] = None # For repeat
    index: Optional[int] = None # For remove/playNext


def _build_lavalink_search_query(title: str, author: Optional[str]) -> str:
    query = f"{title} {author}" if author else title
    return f"ytmsearch:{query.strip()}"

@router.get("/status")
async def get_bot_status():
    # Gather stats
    try:
        nodes = []
        if hasattr(wavelink.Pool, "nodes"):
             for node in wavelink.Pool.nodes.values():
                 nodes.append({
                     "identifier": node.identifier,
                     "connected": node.status == wavelink.NodeStatus.CONNECTED,
                     "stats": {
                         "players": len(node.players),
                         "memory_used": getattr(node, "stats", None).memory_used if getattr(node, "stats", None) else 0,
                         "cpu_cores": getattr(node, "stats", None).cpu_cores if getattr(node, "stats", None) else 0
                     } if getattr(node, "stats", None) else None
                 })

        
        # Count total players
        total_players = len(bot.voice_clients)
        
        return {
            "botOnline": not bot.is_closed(),
            "guilds": len(bot.guilds),
            "users": len(bot.users),
            "players": total_players,
            "nodes": nodes
        }
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        return {"error": str(e), "botOnline": False}

@router.get("/players")
async def get_players():
    # List all active players
    players_data = []
    for vc in bot.voice_clients:
        if isinstance(vc, wavelink.Player):
            try:
                current = None
                if vc.current:
                    current = {
                        "title": vc.current.title,
                        "author": vc.current.author,
                        "duration": vc.current.length,
                        "uri": vc.current.uri,
                        "thumbnail": vc.current.artwork or vc.current.preview_url # fallback
                    }
                
                queue_items = []
                for t in vc.queue:
                    queue_items.append({
                        "title": t.title,
                        "author": t.author,
                        "duration": t.length,
                        "thumbnail": t.artwork or None 
                    })

                players_data.append({
                    "guildId": str(vc.guild.id),
                    "voiceChannel": vc.channel.name if vc.channel else "Unknown",
                    "textChannel": "Unknown", # Not easily tracked unless stored on player
                    "connected": vc.connected,
                    "playing": vc.playing,
                    "paused": vc.paused,
                    "position": vc.position,
                    "volume": vc.volume,
                    "current": current,
                    "queue": queue_items,
                    "settings": {
                        "shuffleEnabled": False, # Shuffle is an action, state hard to track without custom var
                        "repeatMode": "one" if vc.queue.mode == wavelink.QueueMode.loop else "all" if vc.queue.mode == wavelink.QueueMode.loop_all else "off",
                        "volume": vc.volume
                    }
                })
            except Exception as e:
                logger.error(f"Error processing player for guild {vc.guild.id}: {e}")
                continue
    return players_data

@router.get("/search")
async def search_tracks(query: str, guildId: str):
    try:
        if not query:
            return []
            
        # Wavelink search
        tracks = await wavelink.Playable.search(query)
        if not tracks:
            return []
            
        results = []
        # Handle Playlist vs List[Playable]
        if isinstance(tracks, wavelink.Playlist):
             items = tracks.tracks
        else:
             items = tracks

        for t in items[:10]: # Limit to 10
            play_query = _build_lavalink_search_query(t.title, t.author)
            results.append({
                "title": t.title,
                "author": t.author,
                "duration": t.length,
                "uri": t.uri or t.identifier, # detailed uri or identifier if uri missing
                "thumbnail": t.artwork or t.preview_url,
                "playQuery": play_query
            })
            
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

@router.post("/control")
async def control_player(req: ControlRequest):
    try:
        guild_id = int(req.guildId)
        guild = bot.get_guild(guild_id)
        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")
        
        player: wavelink.Player = guild.voice_client
        if not player:
            raise HTTPException(status_code=400, detail="Bot not connected")

        # Reuse logic from music router or implement direct calls
        if req.action == "play":
            if not req.query:
                # Just resume if paused?
                if player.paused:
                    await player.pause(False)
                return {"success": True}
            
            # Search and play
            try:
                search_query = req.query.strip()
                if not search_query:
                    raise HTTPException(status_code=400, detail="Empty query")

                has_prefix = search_query.startswith(("ytsearch:", "ytmsearch:", "scsearch:"))
                is_url = search_query.startswith(("http://", "https://"))

                # Website-side searches should use ytmsearch for reliable Lavalink lookups.
                if not has_prefix and not is_url:
                    search_query = f"ytmsearch:{search_query}"

                tracks = await wavelink.Playable.search(search_query)
            except Exception as search_err:
                # Fallback or specific error handling
                logger.error(f"Wavelink search failed: {search_err}")
                raise HTTPException(status_code=400, detail=f"Failed to load track: {str(search_err)}")

            if not tracks:
                raise HTTPException(status_code=404, detail="No tracks found")
            
            if isinstance(tracks, wavelink.Playlist):
                await player.queue.put_wait(tracks)
            else:
                await player.queue.put_wait(tracks[0])
                
            if not player.playing:
                await player.play(player.queue.get())
                
        elif req.action == "pause":
             await player.pause(True)
             
        elif req.action == "resume":
             await player.pause(False)
             
        elif req.action == "skip":
             await player.skip(force=True)
             
        elif req.action == "volume":
             if req.query:
                 vol = int(float(req.query)) # flexible parsing
                 await player.set_volume(max(0, min(100, vol)))
                 
        elif req.action == "seek":
             if req.query:
                 pos = int(float(req.query))
                 await player.seek(pos)
        
        elif req.action == "remove":
            if req.index is not None and 0 <= req.index < len(player.queue):
                del player.queue[req.index]

        elif req.action == "playNext":
             if req.index is not None and 0 <= req.index < len(player.queue):
                 track = player.queue[req.index]
                 del player.queue[req.index]
                 
                 # Wavelink 3.x Queue usually helps with put_at, but check type or try/except
                 if hasattr(player.queue, "put_at"):
                     player.queue.put_at(0, track)
                 else:
                     # Fallback for list-like
                     player.queue.insert(0, track)

                
                     player.queue.insert(0, track)
                 
        elif req.action == "shuffle":
             # Shuffle the queue
             # Wavelink 3.x Queue has simple shuffle method?
             # Check wavelink docs pattern: typically random.shuffle(player.queue) if it's a list proxy
             # But wavelink.Queue usually has shuffle() method
             if hasattr(player.queue, "shuffle"):
                 player.queue.shuffle()
             else:
                 import random
                 # Fallback if queue is list-like
                 random.shuffle(player.queue)
                 
             # We might want to store shuffle state in metadata if needed for UI "toggle"
             # But for now, action based is fine.
             
        elif req.action == "repeat":
             if req.mode:
                 if req.mode == "one":
                     player.queue.mode = wavelink.QueueMode.loop
                 elif req.mode == "all":
                     player.queue.mode = wavelink.QueueMode.loop_all
                 else:
                     player.queue.mode = wavelink.QueueMode.normal
 
        elif req.action == "filter":
            if req.mode:
                filters = wavelink.Filters()
                mode = req.mode.lower()
                
                if mode == "nightcore":
                    filters.timescale.set(pitch=1.25, speed=1.25)
                elif mode == "vaporwave":
                    filters.timescale.set(pitch=0.8, speed=0.8)
                elif mode == "karaoke":
                    filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
                elif mode == "8d":
                    filters.rotation.set(rotation_hz=0.2)
                elif mode == "tremolo":
                    filters.tremolo.set(frequency=2.0, depth=0.5)
                elif mode == "vibrato":
                    filters.vibrato.set(frequency=2.0, depth=0.5)
                elif mode == "off":
                    await player.set_filters(None)
                    return {"success": True}
                
                await player.set_filters(filters)


        # Trigger UI update
        cog = bot.get_cog("Music")
        if cog and hasattr(cog, "refresh_player_interface"):
            await cog.refresh_player_interface(guild_id)

        return {"success": True}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Control error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
