import discord
import wavelink
import logging
import os
from discord import app_commands
from discord.ext import commands, tasks
from typing import cast, Dict, Optional
from backend.bot.cogs.views.music_view import MusicView
from backend.bot.cogs.views.queue_view import QueueView
import asyncio
from backend.bot import session_queue as sq

logger = logging.getLogger(__name__)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionary to store the message ID of the player controller per guild
        self.player_messages: Dict[int, int] = {}
        self.dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:5173/dashboard")
        
        # Reference to companion listener bot (set if VOICE_MODULE_ENABLED)
        self.listener_bot = None
        self.inactive_since: Dict[int, float] = {}

    async def _handle_voice_command(self, guild_id: int, text_channel_id: int, user_id: int, command_text: str):
        """Callback for the Voice Module when 'Hey Flake ...' is detected"""
        logger.info(f"Music Cog received voice command from {user_id} in {guild_id}: {command_text}")
        
        # Fake a basic /play invocation for now
        # Command forms: "play [song]", "skip", "pause", "resume", "stop"
        
        guild = self.bot.get_guild(guild_id)
        channel = guild.get_channel(text_channel_id) if guild else None
        
        if not guild or not channel:
            return
            
        if not hasattr(self, 'guild_contexts'):
            self.guild_contexts = {}
        self.guild_contexts[guild_id] = text_channel_id
            
        cmds = command_text.split(" ", 1)
        action = cmds[0].lower()
        args = cmds[1] if len(cmds) > 1 else ""
        
        # Fuzzy match actions because Vosk mishears often
        # play -> placebo, bleach, blame, plane, from
        # pause -> boss, post, poles
        # skip -> sheep, keep, skiff
        play_aliases = ["play", "start", "song", "গান", "baja", "placebo", "bleach", "blame", "plane", "from"]
        stop_aliases = ["stop", "clear", "leave", "স্টপ", "বন্ধ", "stock", "stuff"]
        skip_aliases = ["skip", "next", "স্কিপ", "পরের", "sheep", "keep", "skiff", "scape"]
        pause_aliases = ["pause", "resume", "boss", "post", "poles", "bosses", "paws"]
        
        if action in play_aliases:
            if not args:
                await channel.send("I didn't hear what song you wanted me to play.", delete_after=5)
                return
                
            await channel.send(f"🎙️ **Voice Command:** Playing `{args}`...")
            
            # Since we can't easily fake a discord.Interaction for app_commands.command
            # We must pull the logic out slightly or use the bot's raw message parsing
            # Easiest way is to connect to wavelink directly here like the play command does
            try:
                # Find user voice channel
                member = guild.get_member(user_id)
                if not member or not member.voice:
                    await channel.send("You need to be in a voice channel.")
                    return
                
                player: wavelink.Player = guild.voice_client
                if not player:
                    player = await member.voice.channel.connect(cls=wavelink.Player)
                
                player.autoplay = wavelink.AutoPlayMode.partial
                
                # Assume raw query for now
                search_query = f"ytsearch:{args}"
                tracks: wavelink.Search = await wavelink.Playable.search(search_query)
                
                if tracks:
                    track = tracks[0]
                    track.requester = user_id
                    session = sq.get(guild_id)
                    idx = session.add(sq.from_wavelink_track(track))
                    await channel.send(f"Added **{track.title}** to queue from Voice Command.", delete_after=10)
                    if not player.playing:
                        session.set_index(idx)
                        player.queue.clear()
                        await player.play(track)
                    else:
                        await self.refresh_player_interface(guild_id, force_new=False)
                else:
                    await channel.send("I couldn't find that song.", delete_after=5)
            except Exception as e:
                logger.error(f"Voice /play failed: {e}")
                
        elif action in stop_aliases:
            await channel.send("🎙️ **Voice Command:** Stopping music.", delete_after=5)
            player: wavelink.Player = guild.voice_client
            if player:
                player.queue.clear()
                await player.stop()
                await player.disconnect()
        elif action in skip_aliases:
             player: wavelink.Player = guild.voice_client
             if player and player.playing:
                 session = sq.get(guild_id)
                 next_track = session.advance()
                 if next_track:
                     await self._play_session_track(player, next_track)
                     await channel.send("🎙️ **Voice Command:** Skipped track.", delete_after=5)
                 else:
                     await player.stop()
                     await channel.send("🎙️ **Voice Command:** Queue ended.", delete_after=5)
        elif action in pause_aliases:
             player: wavelink.Player = guild.voice_client
             if player:
                 await player.pause(not player.paused)
                 state = "Paused" if player.paused else "Resumed"
                 await channel.send(f"🎙️ **Voice Command:** {state} track.", delete_after=5)
                 await self.refresh_player_interface(guild_id, force_new=False)

    @tasks.loop(seconds=10.0)
    async def auto_disconnect_task(self):
        import time
        now = time.time()
        for guild in self.bot.guilds:
            player: wavelink.Player = cast(wavelink.Player, guild.voice_client)
            if getattr(player, "channel", None) is None:
                self.inactive_since.pop(guild.id, None)
                continue
                
            # Check if alone in voice channel (excluding bots)
            members = player.channel.members
            non_bots = [m for m in members if not m.bot]
            is_empty = len(non_bots) == 0
            
            is_idle = not player.playing and not player.paused
            
            if is_empty or is_idle:
                if guild.id not in self.inactive_since:
                    self.inactive_since[guild.id] = now
                elif now - self.inactive_since[guild.id] >= 60.0:  # 1 minute
                    # Disconnect
                    logger.info(f"Auto-disconnecting from guild {guild.id} due to inactivity/empty channel.")
                    player.queue.clear()
                    sq.clear(guild.id)
                    await player.stop()
                    await player.disconnect()
                    self.inactive_since.pop(guild.id, None)
                    
                    if guild.id in self.player_messages:
                        try:
                            cid, mid = self.player_messages[guild.id]
                            ch = self.bot.get_channel(cid)
                            if ch:
                                await ch.send("Disconnected due to 1 minute of inactivity.", delete_after=10)
                                m = await ch.fetch_message(mid)
                                await m.delete()
                        except:
                            pass
                        del self.player_messages[guild.id]
            else:
                self.inactive_since.pop(guild.id, None)

    @auto_disconnect_task.before_loop
    async def before_auto_disconnect_task(self):
        await self.bot.wait_until_ready()

    async def cog_load(self):
        logger.info("Music Cog loaded")
        self.auto_disconnect_task.start()

    async def cog_unload(self):
        self.auto_disconnect_task.cancel()

    async def update_player_message(self, guild_id: int):
        """
        Updates or sends the player controller message.
        Ensures only one message exists per guild.
        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        player: wavelink.Player = cast(wavelink.Player, guild.voice_client)
        if not player:
            return

        # Prepare Embed
        embed = discord.Embed(color=discord.Color.from_rgb(0, 255, 127)) # Design color
        
        if not player.playing:
            embed.title = "NOTHING PLAYING"
            embed.description = "Queue is empty."
        else:
            track = player.current
            embed.title = "NOW PLAYING"
            embed.description = f"[{track.title}]({track.uri})"
            
            # Fields matching the screenshot
            embed.add_field(name="Author", value=track.author, inline=True)
            
            # Try to get requester if stored (Wavelink tracks allow external data)
            requester = getattr(track, "requester", None)
            req_val = f"<@{requester}>" if requester else "Unknown"
            embed.add_field(name="Requested by", value=req_val, inline=True)
            
            # Duration format
            def format_duration(ms):
                seconds = int(ms / 1000)
                m, s = divmod(seconds, 60)
                return f"{m}:{s:02d}"
            
            embed.add_field(name="Duration", value=format_duration(track.length), inline=True)
            
            embed.add_field(name="Volume", value=f"{player.volume}%", inline=True)
            embed.add_field(name="Queue Length", value=f"{len(player.queue)} Tracks", inline=False)
            
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)

        # Prepare View
        view = MusicView(self.bot, player, self.dashboard_url, music_cog=self)

        # Logic to delete old and send new, or edit if last message
        channel = guild.voice_client.channel if guild.voice_client else None
        # We need a text channel to send the message. 
        # Ideally, we should store the channel ID where the command was last used.
        # For now, let's try to find a channel or use the one from the last interaction if we can track it.
        # BUT `update_player_message` might be called from API where we don't have interaction.
        # We need to store the channel_id alongside the message_id.
        
        # Let's adjust `self.player_messages` to store (channel_id, message_id)
        pass 

    # We need to store channel_id. Let's redefine __init__ and update logic below.
    # Refactoring slightly during write.

    @app_commands.command(name="play", description="Play a song from YouTube, Spotify, etc.")
    @app_commands.describe(query="The song to play")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.guild:
            return
        
        # Store context for this guild
        if not hasattr(self, 'guild_contexts'):
            self.guild_contexts = {}
        self.guild_contexts[interaction.guild.id] = interaction.channel.id

        # Clean off Lavalink prefixes so our yt-dlp and fallback logic can handle it purely
        for prefix in ["ytmsearch:", "ytsearch:", "scsearch:"]:
            if query.startswith(prefix):
                query = query[len(prefix):]

        await interaction.response.defer()

        # Check voice
        if not interaction.user.voice:
            await interaction.followup.send("You must be in a voice channel.", ephemeral=True)
            return

        # Connect
        player: wavelink.Player
        try:
            player = cast(wavelink.Player, interaction.guild.voice_client)
            if not player:
                player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            await interaction.followup.send("Failed to connect.", ephemeral=True)
            return
        
        player.autoplay = wavelink.AutoPlayMode.partial

        # Search
        from backend.utils.youtube import extract_info
        
        # Check if query is a YouTube URL
        if "youtube.com" in query or "youtu.be" in query:
             info = await extract_info(query)
             if info:
                 if 'entries' in info: # Playlist
                      entries = list(info['entries']) # Convert generator if needed
                      # Limit to avoid blocking/timeouts for now
                      limit = 100
                      tracks_to_load = entries[:limit]
                      
                      await interaction.followup.send(f"Processing playlist **{info.get('title', 'Unknown')}** ({len(tracks_to_load)} tracks)...", ephemeral=True)
                      
                      count = 0
                      first_track = None
                      
                      for entry in tracks_to_load:
                          t_title = entry.get('title')
                          t_uploader = entry.get('uploader') or entry.get('artist')
                          
                          if t_title:
                              search_q = f"ytmsearch:{t_title} {t_uploader}" if t_uploader else f"ytmsearch:{t_title}"
                              try:
                                  # Individual search
                                  found_tracks = await wavelink.Playable.search(search_q)
                                  if found_tracks:
                                      t = found_tracks[0] if isinstance(found_tracks, list) else found_tracks.tracks[0]
                                      t.requester = interaction.user.id
                                      await player.queue.put_wait(t)
                                      if not first_track:
                                          first_track = t
                                      count += 1
                              except Exception as e:
                                  logger.warning(f"Failed to load playlist track {t_title}: {e}")
                                  
                      if count > 0:
                          await interaction.followup.send(f"Queued **{count}** tracks from playlist.", ephemeral=True)
                          # All tracks are already in player.queue — mirror them into session
                          session = sq.get(interaction.guild.id)
                          was_playing = player.playing
                          for t in list(player.queue):  # snapshot before clearing
                              session.add(sq.from_wavelink_track(t))
                          if not was_playing:
                              first_t = list(player.queue)[0] if player.queue else None
                              player.queue.clear()
                              if first_t:
                                  session.set_index(0)
                                  await player.play(first_t)
                          else:
                              player.queue.clear()  # Lavalink queue no longer needed
                          return
                      else:
                           await interaction.followup.send("Failed to load any tracks from playlist.", ephemeral=True)
                           return
                 else:
                      title = info.get('title')
                      artist = info.get('artist') or info.get('uploader')
                      if title:
                          search_query = f"{title} {artist}" if artist else title
                          query = f"ytmsearch:{search_query}"
                          await interaction.followup.send(f"Searching YouTube Music for **{search_query}**...", ephemeral=True)
                      else:
                          await interaction.followup.send("Failed to extract video title from YouTube.", ephemeral=True)
                          return
             else:
                 await interaction.followup.send("Failed to fetch information from YouTube. URL might be private.", ephemeral=True)
                 return
        # Clean up accidental double-prefixes from autocomplete
        if query.startswith("ytmsearch:ytmsearch:"):
            query = query.replace("ytmsearch:", "", 1)
        if query.startswith("ytsearch:ytsearch:"):
            query = query.replace("ytsearch:", "", 1)

        if not query.startswith(("http://", "https://", "ytsearch:", "ytmsearch:", "scsearch:")):
            queries_to_try = [f"ytsearch:{query}", f"ytmsearch:{query}"]
        else:
            queries_to_try = [query]
            
            # If they provided a raw youtube URL but Lavalink fails to load it (due to block or sign-in),
            # we should immediately fallback to searching its title/artist via ytsearch instead.
            # But here we just have the raw string, so we'll just try to search it directly first.

        tracks = None
        for try_query in queries_to_try:
            try:
                tracks = await wavelink.Playable.search(try_query)
                if tracks:
                    break # Found something!
            except Exception as e:
                logger.warning(f"Failed to search '{try_query}' in /play: {e}")
                continue

        if not tracks:
            # Final fallback: if it's a direct link that failed, try searching it as text
            if query.startswith(("http://", "https://")):
                 try:
                     clean_query = query.split('&')[0] # remove playlist data just in case
                     tracks = await wavelink.Playable.search(f"ytsearch:{clean_query}")
                 except:
                     pass
                     
            if not tracks:
                await interaction.followup.send("No tracks found or Lavalink blocked the request.", ephemeral=True)
                return

        # Track loading
        track = None
        was_playing = player.playing # Check BEFORE adding to queue/playing
        
        if isinstance(tracks, wavelink.Playlist):
            added = await player.queue.put_wait(tracks)
            track = tracks[0]
            for t in tracks:
                t.requester = interaction.user.id
                sq.get(interaction.guild.id).add(sq.from_wavelink_track(t))
            await interaction.followup.send(f"Added playlist **{tracks.name}** ({added} songs).", ephemeral=True)
        else:
            track = tracks[0]
            track.requester = interaction.user.id
            session = sq.get(interaction.guild.id)
            idx = session.add(sq.from_wavelink_track(track))
            await interaction.followup.send(f"Added **{track.title}** to queue.", ephemeral=True)

        if not player.playing:
            session = sq.get(interaction.guild.id)
            if session.current_index < 0:
                session.set_index(len(session.tracks) - 1)
            player.queue.clear()
            await player.play(track)
            # on_track_start will handle interface creation

        # Only update interface if we were ALREADY playing (queue update)
        if was_playing:
             await self.refresh_player_interface(interaction.guild.id, force_new=False)

    _autocomplete_cache = {}

    @play.autocomplete("query")
    async def play_autocomplete(self, interaction: discord.Interaction, current: str):
        if not current or len(current) < 3:
            return []
            
        current_lower = current.lower()
        import time
        
        # Simple cache expiration (5 minutes)
        if hasattr(self, '_autocomplete_cache') and current_lower in self._autocomplete_cache:
            cache_time, cached_choices = self._autocomplete_cache[current_lower]
            if time.time() - cache_time < 300:
                return cached_choices
                
        try:
            tracks = await wavelink.Playable.search(f"ytmsearch:{current}")
            if not tracks:
                return []
            
            track_list = tracks.tracks if isinstance(tracks, wavelink.Playlist) else tracks
            
            choices = []
            seen = set()
            for track in track_list:
                name = f"{track.title[:60]} - {track.author[:30]}"
                if name not in seen:
                    seen.add(name)
                    # use URI if it fits in 100 chars, else use the name itself
                    val = track.uri if track.uri and len(track.uri) <= 100 else name
                    choices.append(app_commands.Choice(name=name, value=val))
                if len(choices) >= 25:
                    break
                    
            if not hasattr(self, '_autocomplete_cache'):
                self._autocomplete_cache = {}
            self._autocomplete_cache[current_lower] = (time.time(), choices)
            return choices
        except Exception as e:
            logger.error(f"Autocomplete error in /play: {e}")
            return []

    # ---------------------------------------------------------------------- #
    # Internal helper: resolve a TrackInfo and play it immediately            #
    # Lavalink's player.queue is NEVER used for routing — only for playing    #
    # ---------------------------------------------------------------------- #
    async def _play_session_track(self, player: wavelink.Player, track_info: sq.TrackInfo, is_manual: bool = True):
        """Load a session track via Lavalink and play it immediately.

        is_manual=True  (default): user-initiated skip/previous — sets
                        _session_navigating so on_track_end ignores the
                        'replaced' event that fires for the interrupted track.
        is_manual=False: called from on_track_end (natural advance / repeat) —
                        no 'replaced' event fires, so the flag must NOT be set
                        or it would swallow the next natural 'finished' event.
        """
        try:
            found = None
            if track_info.encoded:
                # If we saved the base64 encoded track from lavalink, try to decode and play it directly
                try:
                    found = await wavelink.Playable.search(track_info.encoded)
                except Exception:
                    pass
            
            if not found and track_info.uri:
                 # Search by exact URI
                 try:
                     found = await wavelink.Playable.search(track_info.uri)
                 except Exception:
                     pass
                     
            if not found:
                # Fallback to search
                search_q = f"ytmsearch:{track_info.title} {track_info.author}"
                found = await wavelink.Playable.search(search_q)
                
            if not found:
                logger.warning(f"Session track not found: {track_info.title}")
                # Skip to next automatically
                session = sq.get(player.guild.id)
                next_track = session.advance()
                if next_track:
                    await self._play_session_track(player, next_track, is_manual=is_manual)
                return
            wl_track = found[0]
            player.queue.clear()           # Lavalink queue stays empty
            if is_manual:
                # Signal on_track_end to ignore the 'replaced' event for the
                # track that is being interrupted right now.
                player._session_navigating = True
            await player.play(wl_track)
        except Exception as e:
            logger.error(f"_play_session_track error: {e}")


    async def refresh_player_interface(self, guild_id: int, force_new: bool = False):
        if not hasattr(self, 'player_messages'):
            self.player_messages = {}
        if not hasattr(self, 'guild_contexts'):
             self.guild_contexts = {}

        channel_id = self.guild_contexts.get(guild_id)
        if not channel_id:
            return 

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        player: wavelink.Player = channel.guild.voice_client
        if not player:
            return

        # Build Embed
        embed = discord.Embed(color=discord.Color.from_rgb(0, 255, 127))
        
        if player.playing and player.current:
            track = player.current
            
            # Main Description
            embed.description = f"[{track.title}]({track.uri})"
            if hasattr(track, "title"): 
                 if player.paused:
                    embed.title = "PAUSED ⏸️"
                 else:
                    embed.title = "NOW PLAYING ▶️"
            
            # Fields
            embed.add_field(name="Author", value=track.author or "Unknown", inline=True)

            
            req_id = getattr(track, "requester", None)
            req_str = f"<@{req_id}>" if req_id else "Unknown"
            embed.add_field(name="Requested by", value=req_str, inline=True)
            
            ms = track.length
            seconds = int(ms / 1000)
            m, s = divmod(seconds, 60)
            embed.add_field(name="Duration", value=f"{m}:{s:02d}", inline=True)
            
            embed.add_field(name="Volume", value=f"{player.volume}%", inline=True)
            
            session = sq.get(guild_id)
            remaining = max(0, len(session.tracks) - session.current_index - 1)
            autoplay_str = " (Autoplay ON)" if session.autoplay_enabled else ""
            embed.add_field(name="Queue Length", value=f"{remaining} Tracks{autoplay_str}", inline=False)
            
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            
            embed.set_footer(text="Designed by Kraftamine")

        else:
            embed.title = "NOTHING PLAYING"
            embed.description = "Queue is empty. Join a voice channel and play a song!"
            embed.color = discord.Color.dark_grey()

        view = MusicView(self.bot, player, self.dashboard_url, music_cog=self)

        # Helper to send new
        async def send_new():
            try:
                msg = await channel.send(embed=embed, view=view)
                self.player_messages[guild_id] = (channel_id, msg.id)
            except Exception as e:
                logger.error(f"Failed to send player interface: {e}")

        # Helper to delete old
        async def delete_old(mid, cid):
            try:
                ch = self.bot.get_channel(cid)
                if ch:
                    m = await ch.fetch_message(mid)
                    await m.delete()
            except:
                pass

        msg_data = self.player_messages.get(guild_id)
        
        if msg_data:
            existing_channel_id, existing_msg_id = msg_data
            
            if force_new:
                await delete_old(existing_msg_id, existing_channel_id)
                await send_new()
            else:
                # Try to edit
                try:
                    existing_channel = self.bot.get_channel(existing_channel_id)
                    if existing_channel:
                        old_msg = await existing_channel.fetch_message(existing_msg_id)
                        await old_msg.edit(embed=embed, view=view)
                    else:
                        await send_new()
                except discord.NotFound:
                    # Message deleted, send new
                    await send_new()
                except Exception as e:
                    logger.error(f"Failed to edit message: {e}")
                    await send_new()
        else:
            await send_new()


    @app_commands.command(name="skip", description="Skip song")
    async def skip(self, interaction: discord.Interaction):
        player: wavelink.Player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player or not player.playing:
            await interaction.response.send_message("Nothing playing.", ephemeral=True)
            return
        await interaction.response.send_message("Skipped.", ephemeral=True)
        session = sq.get(interaction.guild.id)
        next_track = session.advance()
        if next_track:
            await self._play_session_track(player, next_track)
        else:
            player.queue.clear()
            await player.stop()

    @app_commands.command(name="pause", description="Pause/Resume")
    async def pause(self, interaction: discord.Interaction):
        player: wavelink.Player = cast(wavelink.Player, interaction.guild.voice_client)
        if player:
            await player.pause(not player.paused)
            state = "Paused" if player.paused else "Resumed"
            await interaction.response.send_message(f"{state}", ephemeral=True)
            await self.refresh_player_interface(interaction.guild.id, force_new=False)

    @app_commands.command(name="stop", description="Stop music")
    async def stop(self, interaction: discord.Interaction):
        player: wavelink.Player = cast(wavelink.Player, interaction.guild.voice_client)
        if player:
            player.queue.clear()
            sq.clear(interaction.guild.id)   # clear session
            await player.stop()
            await player.disconnect()
            await interaction.response.send_message("Stopped.", ephemeral=True)
            if interaction.guild.id in self.player_messages:
                try:
                    cid, mid = self.player_messages[interaction.guild.id]
                    ch = self.bot.get_channel(cid)
                    if ch:
                        m = await ch.fetch_message(mid)
                        await m.delete()
                except:
                    pass
                del self.player_messages[interaction.guild.id]

    @app_commands.command(name="volume", description="Set volume")
    async def volume(self, interaction: discord.Interaction, level: int):
        player: wavelink.Player = cast(wavelink.Player, interaction.guild.voice_client)
        if player:
            await player.set_volume(max(0, min(100, level)))
            await interaction.response.send_message(f"Volume: {level}", ephemeral=True)
            await self.refresh_player_interface(interaction.guild.id, force_new=False)
    
    @app_commands.command(name="filter", description="Apply audio filters")
    @app_commands.describe(preset="The filter preset to apply")
    @app_commands.choices(preset=[
        app_commands.Choice(name="Nightcore", value="nightcore"),
        app_commands.Choice(name="Vaporwave", value="vaporwave"),
        app_commands.Choice(name="Karaoke", value="karaoke"),
        app_commands.Choice(name="8D Audio", value="8d"),
        app_commands.Choice(name="Tremolo", value="tremolo"),
        app_commands.Choice(name="Vibrato", value="vibrato"),
        app_commands.Choice(name="Clear/Off", value="off"),
    ])
    async def filter(self, interaction: discord.Interaction, preset: app_commands.Choice[str]):
        player: wavelink.Player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player:
             await interaction.response.send_message("Not playing anything.", ephemeral=True)
             return

        # Reuse logic is tricky without importing or duplicating.
        # Ideally we refactor filter logic to a helper in utils or on the bot/cog class.
        # For now, duplicating since it's short and simple.
        
        mode = preset.value
        filters = wavelink.Filters()
        
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
            await interaction.response.send_message(f"Filters cleared.", ephemeral=True)
            return
        
        await player.set_filters(filters)
        await interaction.response.send_message(f"Applied filter: **{preset.name}**", ephemeral=True)

    @app_commands.command(name="autoplay", description="Toggle autoplay (automatically play related songs when queue ends)")
    async def autoplay(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        session = sq.get(interaction.guild.id)
        session.autoplay_enabled = not session.autoplay_enabled
        
        state = "enabled" if session.autoplay_enabled else "disabled"
        await interaction.response.send_message(f"Autoplay is now **{state}**.", ephemeral=False)

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        session = sq.get(interaction.guild.id)
        player: wavelink.Player = cast(wavelink.Player, interaction.guild.voice_client)

        if not session.tracks:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return

        # Store context so refresh_player_interface always has a channel
        if not hasattr(self, 'guild_contexts'):
            self.guild_contexts = {}
        self.guild_contexts[interaction.guild.id] = interaction.channel.id

        view = QueueView(session, player)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.id == self.bot.user.id and after.channel is None:
            guild_id = member.guild.id
            # Clear session queue
            sq.clear(guild_id)
            if hasattr(self, 'player_messages') and guild_id in self.player_messages:
                try:
                    cid, mid = self.player_messages[guild_id]
                    ch = self.bot.get_channel(cid)
                    if ch:
                        m = await ch.fetch_message(mid)
                        await m.delete()
                except:
                    pass
                self.player_messages.pop(guild_id, None)
                logger.info(f"Cleaned up player message and session for guild {guild_id} on disconnect")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: wavelink.Player = payload.player
        if not player or not player.guild:
            return
            
        guild_id = player.guild.id
        
        # Broadcast WS
        from backend.api.websocket.manager import manager
        await manager.broadcast(str(guild_id), {
            "event": "TRACK_START",
            "track": payload.track.title,
            "author": payload.track.author,
            "duration": payload.track.length,
            "uri": payload.track.uri,
            "artwork": payload.track.artwork
        })

        # Only create a new message if one doesn't exist yet;
        # otherwise edit in-place to avoid spamming the channel on skip/previous.
        has_existing = bool(self.player_messages.get(guild_id))
        await self.refresh_player_interface(guild_id, force_new=not has_existing)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: wavelink.Player = payload.player
        if not player or not player.guild:
            return

        guild_id = player.guild.id

        from backend.api.websocket.manager import manager
        await manager.broadcast(str(guild_id), {
            "event": "TRACK_END",
            "track": payload.track.title,
            "reason": payload.reason
        })

        reason = str(payload.reason).lower()  # normalise e.g. 'TrackEndReason.FINISHED' -> 'finished'

        # If we navigated intentionally (skip/previous/play-index) the 'replaced' event fires.
        # In that case we already called _play_session_track which set the new index — don't advance.
        if getattr(player, '_session_navigating', False):
            player._session_navigating = False
            return

        # Natural track end — advance session and play next
        if 'finished' in reason or 'finish' in reason:
            session = sq.get(guild_id)
            next_track = session.advance()
            if next_track:
                # is_manual=False: no track is being interrupted, so don't set
                # _session_navigating (that flag is only for user-initiated skips).
                await self._play_session_track(player, next_track, is_manual=False)
            elif session.autoplay_enabled and session.current:
                # End of queue, but autoplay is enabled. Fetch recommended track.
                last_track = session.current
                try:
                    next_wl_track = None
                    valid_choices = []
                    
                    import os
                    import aiohttp
                    import re
                    import random
                    import urllib.parse
                    
                    last_fm_api_key = os.getenv("LASTFM_API_KEY")
                    
                    # Clean the title for better Last.fm matching (remove (Official Video), [Remix], etc)
                    clean_title = re.sub(r'[\[\(].*?[\]\)]|-.*|Official.*|Video.*|Audio.*|Lyrics.*', '', last_track.title).strip()
                    clean_author = re.sub(r'VEVO|Official|Topic', '', last_track.author, flags=re.IGNORECASE).strip()

                    # Try Last.fm first if API key is present
                    if last_fm_api_key and not next_wl_track:
                        url = f"http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&artist={urllib.parse.quote_plus(clean_author)}&track={urllib.parse.quote_plus(clean_title)}&api_key={last_fm_api_key}&format=json&limit=15"
                        try:
                            async with aiohttp.ClientSession() as http_session:
                                # Add user-agent to prevent 403s on AudioScrobbler
                                headers = {'User-Agent': 'FlakeMusicBot/1.0'}
                                async with http_session.get(url, headers=headers) as response:
                                    if response.status == 200:
                                        data = await response.json()
                                        similar_tracks = data.get('similartracks', {}).get('track', [])
                                        
                                        if similar_tracks:
                                            # We have Last.fm recommendations!
                                            random.shuffle(similar_tracks) # Mix them up
                                            existing_titles = {t.title.lower() for t in session.tracks}
                                            
                                            for sim_track in similar_tracks:
                                                sim_title = sim_track.get('name')
                                                sim_artist = sim_track.get('artist', {}).get('name')
                                                
                                                # Ensure both are present and not already played
                                                if sim_title and sim_artist and sim_title.lower() not in existing_titles:
                                                    # Try to resolve this specific track via Lavalink
                                                    # Last.fm returns very specific artist names that sometimes trip up YouTube search.
                                                    # We'll try ytsearch (standard youtube, usually best for exact title+artist), then ytmsearch.
                                                    
                                                    queries_to_try = [
                                                        f"ytsearch:{sim_title} {sim_artist}",
                                                        f"ytmsearch:{sim_title} {sim_artist}",
                                                        f"ytsearch:{sim_title} Official Audio",
                                                    ]
                                                    
                                                    found_valid = False
                                                    for query in queries_to_try:
                                                        try:
                                                            found = await wavelink.Playable.search(query)
                                                            if found:
                                                                track_list = found.tracks if isinstance(found, wavelink.Playlist) else found
                                                                if track_list:
                                                                    next_wl_track = track_list[0]
                                                                    logger.info(f"Last.fm chose: {sim_title} by {sim_artist} (Found via {query.split(':')[0]})")
                                                                    found_valid = True
                                                                    break
                                                        except Exception as search_e:
                                                            logger.warning(f"Lavalink search failed for '{query}': {search_e}")
                                                            continue
                                                    
                                                    if found_valid:
                                                        break # Break the outer Last.fm similar tracks loop since we found a song!
                                    else:
                                        logger.error(f"Last.fm API returned status {response.status}")
                        except Exception as e:
                            logger.error(f"Last.fm API fetch failed: {e}")

                    # Fallback to Wavelink Mix-based querying if Last.fm fails or is unavailable
                    if not next_wl_track:
                        query = f"ytmsearch:{clean_title} {clean_author} mix"
                        found = await wavelink.Playable.search(query)
                        
                        if not found:
                            query = f"ytmsearch:{clean_author} top tracks"
                            found = await wavelink.Playable.search(query)
    
                        if found:
                            track_list = found.tracks if isinstance(found, wavelink.Playlist) else found
                            choices = track_list[1:12] if len(track_list) > 1 else track_list
                            
                            existing_uris = {t.uri for t in session.tracks}
                            valid_choices = [t for t in choices if t.uri not in existing_uris]
                            
                            if not valid_choices and choices:
                                 valid_choices = choices
                                 
                            next_wl_track = random.choice(valid_choices) if valid_choices else choices[0]

                    if next_wl_track:
                        # Add to session and play
                        next_wl_track.requester = player.client.user.id # Bot requested it
                        sq_track = sq.from_wavelink_track(next_wl_track)
                        session.add(sq_track)
                        
                        # Advance session to this newly added track
                        session.set_index(session.current_index + 1)
                        await self._play_session_track(player, session.current, is_manual=False)
                        
                        # Send a message to the channel saying autoplay added a song
                        if guild_id in self.guild_contexts:
                            channel = self.bot.get_channel(self.guild_contexts[guild_id])
                            if channel:
                                await channel.send(f"📻 **Autoplay** added: **{next_wl_track.title}**", delete_after=15)
                                
                        # Crucial: Refresh the UI to reflect the new track and the "Auto" state
                        await self.refresh_player_interface(guild_id, force_new=False)
                    else:
                        await self.refresh_player_interface(guild_id, force_new=False)
                except Exception as e:
                    logger.error(f"Autoplay failed to find next track: {e}")
                    await self.refresh_player_interface(guild_id, force_new=False)
            else:
                # End of queue and no autoplay
                await self.refresh_player_interface(guild_id, force_new=False)
        # 'stopped' / 'replaced' without flag = ignore (bot was stopped or external force)

    # --- VOICE MODULE TOGGLE ---
    if os.getenv("VOICE_MODULE_ENABLED", "false").lower() == "true":
        @app_commands.command(name="ai", description="Toggle the Voice AI Assistant (Hey Flake)")
        @app_commands.describe(action="Enable or disable the voice listener")
        @app_commands.choices(action=[
            app_commands.Choice(name="Enable Listener", value="enable"),
            app_commands.Choice(name="Disable Listener", value="disable"),
        ])
        async def ai_toggle(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
            if not getattr(self.bot, "listener_bot", None):
                await interaction.response.send_message("The AI listener bot is not currently running. Check backend logs.", ephemeral=True)
                return
                
            listener = self.bot.listener_bot
            
            if action.value == "enable":
                if not interaction.user.voice:
                    await interaction.response.send_message("You must be in a voice channel first.", ephemeral=True)
                    return
                    
                await interaction.response.defer(ephemeral=False)
                
                voice_channel_id = interaction.user.voice.channel.id
                text_channel_id = interaction.channel.id
                
                # Ask companion bot to join
                success = await listener.join_channel(text_channel_id, voice_channel_id)
                if success:
                    await interaction.followup.send("✅ Aye aye captain flake is onboard")
                else:
                    await interaction.followup.send("❌ AI Listener failed to join. Check server permissions.")
                    
            elif action.value == "disable":
                success = await listener.leave_channel(interaction.guild.id)
                if success:
                    await interaction.response.send_message("🛑 adios amigo powering off captain", ephemeral=False)
                else:
                    await interaction.response.send_message("AI Listener is not currently in a voice channel here.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))

