import discord
import wavelink
import logging
import os
from discord import app_commands
from discord.ext import commands
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

    async def cog_load(self):
        logger.info("Music Cog loaded")

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
        view = MusicView(self.bot, player, self.dashboard_url)

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
                                      t = found_tracks[0]
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
                          await interaction.followup.send(f"Fallback: Searching for **{search_query}**...", ephemeral=True)

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)
        except Exception as e:
            await interaction.followup.send("Could not find any tracks.", ephemeral=True)
            return

        if not tracks:
            await interaction.followup.send("No tracks found.", ephemeral=True)
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

    # ---------------------------------------------------------------------- #
    # Internal helper: resolve a TrackInfo and play it immediately            #
    # Lavalink's player.queue is NEVER used for routing — only for playing    #
    # ---------------------------------------------------------------------- #
    async def _play_session_track(self, player: wavelink.Player, track_info: sq.TrackInfo):
        """Load a session track via Lavalink and play it immediately.
        Sets player._session_navigating = True so on_track_end knows the
        'replaced' event was intentional and should NOT advance the session.
        """
        try:
            search_q = f"ytmsearch:{track_info.title} {track_info.author}"
            found = await wavelink.Playable.search(search_q)
            if not found:
                logger.warning(f"Session track not found: {track_info.title}")
                # Skip to next automatically
                session = sq.get(player.guild.id)
                next_track = session.advance()
                if next_track:
                    await self._play_session_track(player, next_track)
                return
            wl_track = found[0]
            player.queue.clear()           # Lavalink queue stays empty
            player._session_navigating = True  # Signal: don't auto-advance in on_track_end
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
            embed.add_field(name="Queue Length", value=f"{remaining} Tracks", inline=False)
            
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            
            embed.set_footer(text="Designed by Kraftamine")

        else:
            embed.title = "NOTHING PLAYING"
            embed.description = "Queue is empty. Join a voice channel and play a song!"
            embed.color = discord.Color.dark_grey()

        view = MusicView(self.bot, player, self.dashboard_url)

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
                await self._play_session_track(player, next_track)
            else:
                # End of queue
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

