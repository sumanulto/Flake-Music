import discord
import wavelink
import logging
from discord import app_commands
from discord.ext import commands
from typing import cast, Dict, Optional
from backend.bot.cogs.views.music_view import MusicView

logger = logging.getLogger(__name__)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionary to store the message ID of the player controller per guild
        self.player_messages: Dict[int, int] = {}

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
        view = MusicView(self.bot, player)

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
                      # For now, just play the first one or handle differently?
                      # Request: "fetch album title and send that to lavalink"
                      # So if it's a playlist, maybe play the playlist name?
                      title = info.get('title')
                      if title:
                          query = f"ytmsearch:{title}"
                          await interaction.followup.send(f"Fallback: Searching for playlist **{title}**...", ephemeral=True)
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
            track = tracks[0] # Use first track for info
            # Tag requester
            for t in tracks:
                t.requester = interaction.user.id
            await interaction.followup.send(f"Added playlist **{tracks.name}** ({added} songs).", ephemeral=True)
        else:
            track = tracks[0]
            track.requester = interaction.user.id
            await player.queue.put_wait(track)
            await interaction.followup.send(f"Added **{track.title}** to queue.", ephemeral=True)

        if not player.playing:
            await player.play(player.queue.get())
            # on_track_start will handle the interface creation

        # Only update interface here if we were ALREADY playing (queue update)
        if was_playing:
             await self.refresh_player_interface(interaction.guild.id, force_new=False)


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
            
            embed.add_field(name=f"Queue Length", value=f"{len(player.queue)} Tracks", inline=False)
            
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            
            embed.set_footer(text="Designed by Flake Music")

        else:
            embed.title = "NOTHING PLAYING"
            embed.description = "Queue is empty. Join a voice channel and play a song!"
            embed.color = discord.Color.dark_grey()

        view = MusicView(self.bot, player)

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
        if player and player.playing:
            await player.skip(force=True)
            await interaction.response.send_message("Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing playing.", ephemeral=True)

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
            await player.stop()
            await player.disconnect()
            await interaction.response.send_message("Stopped.", ephemeral=True)
            # Remove message context
            if interaction.guild.id in self.player_messages:
                # We might want to clear the player message or show "Disconnected"
                # For now, let's delete it to be clean
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

    @app_commands.command(name="queue", description="Show queue")
    async def queue(self, interaction: discord.Interaction):
        # We can keep this command or just rely on the interface
        player: wavelink.Player = cast(wavelink.Player, interaction.guild.voice_client)
        if player:
             # Just show a simple ephemeral list
             if player.queue.is_empty:
                  await interaction.response.send_message("Queue empty", ephemeral=True)
                  return
             desc = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(player.queue[:10])])
             await interaction.response.send_message(desc, ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Helper to cleanup player message when bot disconnects
        if member.id == self.bot.user.id and after.channel is None:
            guild_id = member.guild.id
            if hasattr(self, 'player_messages') and guild_id in self.player_messages:
                try:
                    cid, mid = self.player_messages[guild_id]
                    ch = self.bot.get_channel(cid)
                    if ch:
                        m = await ch.fetch_message(mid)
                        await m.delete()
                except:
                    pass
                # Safe delete
                self.player_messages.pop(guild_id, None)
                logger.info(f"Cleaned up player message for guild {guild_id} on disconnect")

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

        # Update UI - New Track = New Message (to keep it at bottom)
        await self.refresh_player_interface(guild_id, force_new=True)

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
        
        if player.queue.is_empty and not player.playing:
             await self.refresh_player_interface(guild_id, force_new=False)

async def setup(bot):
    await bot.add_cog(Music(bot))

