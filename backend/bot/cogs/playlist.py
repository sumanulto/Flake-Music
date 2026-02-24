import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database.core.db import async_session_factory
from backend.database.models.models import Playlist, PlaylistTrack, User
from backend.utils.youtube import extract_info
from backend.bot.cogs.views.playlist_manage_view import PlaylistManageView
import wavelink
import logging
import datetime

logger = logging.getLogger(__name__)

class PlaylistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user_playlist(self, user_id: int, name: str, session):
        stmt = select(Playlist).where(Playlist.user_id == user_id, Playlist.name == name)
        return (await session.execute(stmt)).scalar_one_or_none()

    playlist_group = app_commands.Group(name="playlist", description="Manage your playlists")

    @playlist_group.command(name="create", description="Create a new playlist")
    async def create(self, interaction: discord.Interaction, name: str):
        async with async_session_factory() as session:
            # Check if exists
            if await self.get_user_playlist(interaction.user.id, name, session):
                await interaction.response.send_message(f"Playlist **{name}** already exists!", ephemeral=True)
                return

            # Ensure user exists
            user_stmt = select(User).where(User.id == interaction.user.id)
            user = (await session.execute(user_stmt)).scalar_one_or_none()
            if not user:
                user = User(id=interaction.user.id, username=interaction.user.name)
                session.add(user)
            
            new_playlist = Playlist(name=name, user_id=interaction.user.id)
            session.add(new_playlist)
            await session.commit()
            await interaction.response.send_message(f"Created playlist **{name}**.", ephemeral=True)

    @playlist_group.command(name="add", description="Add a song to a playlist")
    async def add(self, interaction: discord.Interaction, name: str, query: str):
        # Detect playlist URLs early and reject them with a helpful message
        _q = query.strip()
        _is_yt_playlist = (
            ("youtube.com/playlist" in _q or "music.youtube.com/playlist" in _q)
            and "list=" in _q
        )
        _is_spotify_playlist = "open.spotify.com/playlist/" in _q

        if _is_yt_playlist or _is_spotify_playlist:
            source = "YouTube Music" if _is_yt_playlist else "Spotify"
            await interaction.response.send_message(
                f"⚠️ **{source} playlist links cannot be added here.**\n\n"
                "This command only supports **individual tracks**.\n"
                "To import an entire playlist, use the **Playlist Transfer** option on the web dashboard.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # YouTube Fallback Logic (Reuse from music.py)
        if "youtube.com" in query or "youtu.be" in query:
             info = await extract_info(query)
             if info:
                  title = info.get('title')
                  artist = info.get('artist') or info.get('uploader')
                  if title:
                      query = f"ytmsearch:{title} {artist}" if artist else f"ytmsearch:{title}"

        # Search Track
        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)
        except Exception:
            await interaction.followup.send("Could not find track.")
            return

        if not tracks:
            await interaction.followup.send("No tracks found.")
            return

        idx = 0
        if isinstance(tracks, wavelink.Playlist):
            # Maybe add all? For now just first or error?
            # User might want to add a whole playlist. 
            # Let's add all for now if it's a playlist object, OR just first if it's a search result list.
            # Wavelink search returns Playlist if it's a playlist URL, or list[Playable] if search.
            # If search, tracks is list.
            pass
        
        # Just grab first result
        track = tracks[0] if isinstance(tracks, list) else tracks.tracks[0]

        async with async_session_factory() as session:
            playlist = await self.get_user_playlist(interaction.user.id, name, session)
            if not playlist:
                await interaction.followup.send(f"Playlist **{name}** not found.")
                return

            # Store track data
            # We store the encoded string generally, plus metadata for easy display
            track_data = {
                "encoded": track.encoded,
                "info": {
                    "title": track.title,
                    "author": track.author,
                    "uri": track.uri,
                    "length": track.length,
                    "is_stream": track.is_stream
                }
            }
            
            new_track = PlaylistTrack(
                playlist_id=playlist.id, 
                track_data=track_data,
                added_at=datetime.datetime.utcnow().isoformat()
            )
            session.add(new_track)
            await session.commit()
            
            await interaction.followup.send(f"Added **{track.title}** to **{name}**.")

    @playlist_group.command(name="play", description="Play a playlist")
    async def play_playlist(self, interaction: discord.Interaction, name: str):
         # Check voice state
        if not interaction.user.voice:
             await interaction.response.send_message("Join voice first!", ephemeral=True)
             return
             
        await interaction.response.defer()
        
        # Register context with Music Cog for UI
        music_cog = self.bot.get_cog("Music")
        if music_cog:
            if not hasattr(music_cog, 'guild_contexts'):
                music_cog.guild_contexts = {}
            music_cog.guild_contexts[interaction.guild.id] = interaction.channel.id
        
        # Connect
        player: wavelink.Player
        try:
            player = interaction.guild.voice_client 
            if not player:
                player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        except Exception as e:
             logger.error(f"Connection error: {e}")
             await interaction.followup.send("Failed to connect.", ephemeral=True)
             return
        
        player.autoplay = wavelink.AutoPlayMode.partial

        # 1. Fetch all track data from DB first
        tracks_data = []
        try:
            async with async_session_factory() as session:
                stmt = select(Playlist).where(Playlist.user_id == interaction.user.id, Playlist.name == name).options(selectinload(Playlist.tracks))
                playlist = (await session.execute(stmt)).scalar_one_or_none()
                
                if not playlist or not playlist.tracks:
                    logger.info(f"Playlist {name} not found or empty.")
                    await interaction.followup.send("Playlist empty or not found.", ephemeral=True)
                    return
                
                logger.info(f"Playlist {name} found with {len(playlist.tracks)} tracks.")
                
                # Collect all track data needed
                for t_db in playlist.tracks:
                    if t_db.track_data:
                        tracks_data.append(t_db.track_data)
                    else:
                        logger.warning(f"Track {t_db.id} missing track_data.")

        except Exception as e:
            logger.error(f"Database error in play_playlist: {e}")
            await interaction.followup.send("An error occurred while fetching the playlist.", ephemeral=True)
            return
        
        logger.info(f"Collected {len(tracks_data)} tracks.")

        # 2. Process tracks (No DB usage here)
        count = 0
        for i, data in enumerate(tracks_data):
            track = None
            # Handle both nested 'info' (old/bot) and flat (new/web) formats
            info = data.get("info", data) 
            title = info.get("title")
            author = info.get("author") or info.get("artist") # Fallback for flat format which might use artist

            uri = info.get("uri")

            # Strategy: Search Only (Most Reliable per User)
            # Remove Encoded/URI attempts to fix "URI load failed" and blocking issues.
            
            if title:
                try:
                    query = f"ytmsearch:{title} {author}" if author else f"ytmsearch:{title}"
                    # logger.info(f"Track {i}: Searching: {query}")
                    tracks = await wavelink.Playable.search(query)
                    if tracks:
                        track = tracks[0]
                except Exception as e:
                     logger.warning(f"Track {i}: Search load failed: {e}")
            else:
                 logger.warning(f"Track {i}: Missing title in data: {data}")

            if track:
                try:
                    await player.queue.put_wait(track)
                    count += 1
                except Exception as e:
                    logger.error(f"Track {i}: Failed to queue: {e}")
            else:
                logger.error(f"Track {i} failed to load. Data: {data}")
        
        logger.info(f"Finished loading. Queued: {count}")

        if count > 0:
            await interaction.followup.send(f"Queued **{count}** tracks from **{name}**.")
            try:
                if not player.playing:
                    await player.play(player.queue.get())
            except Exception as e:
                logger.error(f"Failed to start playback: {e}")
        else:
            await interaction.followup.send("Failed to load any tracks.")

    @playlist_group.command(name="list", description="List your playlists")
    async def list_playlists(self, interaction: discord.Interaction):
         async with async_session_factory() as session:
             stmt = select(Playlist).where(Playlist.user_id == interaction.user.id)
             playlists = (await session.execute(stmt)).scalars().all()
             
             if not playlists:
                 await interaction.response.send_message("You have no playlists.", ephemeral=True)
                 return
                 
             desc = "\n".join([f"- **{p.name}** {'(Liked Songs)' if p.is_liked_songs else ''}" for p in playlists])
             await interaction.response.send_message(f"**Your Playlists**:\n{desc}", ephemeral=True)

    # -----------------------------------------------------------------------
    # /playlist manage
    # -----------------------------------------------------------------------

    @playlist_group.command(name="manage", description="Open the management panel for one of your playlists")
    @app_commands.describe(name="The playlist to manage")
    async def manage(self, interaction: discord.Interaction, name: str):
        async with async_session_factory() as session:
            stmt = (
                select(Playlist)
                .where(Playlist.user_id == interaction.user.id, Playlist.name == name)
                .options(selectinload(Playlist.tracks))
            )
            playlist = (await session.execute(stmt)).scalar_one_or_none()

        if not playlist:
            await interaction.response.send_message(
                f"❌ Playlist **{name}** not found or doesn't belong to you.", ephemeral=True
            )
            return

        track_count = len(playlist.tracks) if playlist.tracks else 0

        # Build the management embed
        embed = discord.Embed(
            title="🎵 Playlist Settings",
            description="Personalize and take full control of your playlist\n\nManage your playlist below using the available actions.",
            color=discord.Color.from_rgb(88, 101, 242),  # Discord blurple
        )
        embed.add_field(name="🎵 Playlist", value=playlist.name, inline=False)
        embed.add_field(name="∑ Total Tracks", value=str(track_count), inline=True)
        embed.add_field(
            name="🕒 Last Updated",
            value=(
                playlist.tracks[-1].added_at if playlist.tracks and playlist.tracks[-1].added_at
                else "N/A"
            ),
            inline=True,
        )
        embed.set_footer(text=f"Playlist owned by {interaction.user.display_name}")
        embed.set_image(url="https://i.ibb.co/qGpXh5D/image.jpg")  # music banner image

        view = PlaylistManageView(
            owner_id=interaction.user.id,
            playlist_name=playlist.name,
            playlist_id=playlist.id,
        )
        await interaction.response.send_message(embed=embed, view=view)

    @manage.autocomplete("name")
    async def manage_autocomplete(self, interaction: discord.Interaction, current: str):
        async with async_session_factory() as session:
            stmt = (
                select(Playlist.name)
                .where(Playlist.user_id == interaction.user.id, Playlist.name.ilike(f"%{current}%"))
                .limit(25)
            )
            playlists = (await session.execute(stmt)).scalars().all()
        return [app_commands.Choice(name=p, value=p) for p in playlists]

    @app_commands.command(name="like", description="Add current song to Liked Songs")
    async def like(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if not player or not player.current:
            await interaction.response.send_message("Nothing playing.", ephemeral=True)
            return
            
        track = player.current
        
        async with async_session_factory() as session:
            # Get Liked Songs playlist
            stmt = select(Playlist).where(Playlist.user_id == interaction.user.id, Playlist.is_liked_songs == True)
            playlist = (await session.execute(stmt)).scalar_one_or_none()
            
            if not playlist:
                # Ensure user
                u_stmt = select(User).where(User.id == interaction.user.id)
                if not (await session.execute(u_stmt)).scalar_one_or_none():
                    session.add(User(id=interaction.user.id, username=interaction.user.name))
                
                playlist = Playlist(name="Liked Songs", user_id=interaction.user.id, is_liked_songs=True)
                session.add(playlist)
                await session.commit()
                await session.refresh(playlist)
            
            # Check duplicate (simple check)
            # We need to fetch tracks
            await session.refresh(playlist, ["tracks"])
            for t in playlist.tracks:
                # Handle both formats for duplicate checking
                t_info = t.track_data.get("info", t.track_data)
                if t_info.get("uri") == track.uri:
                     await interaction.response.send_message("Already in Liked Songs!", ephemeral=True)
                     return

            track_data = {
                "encoded": track.encoded,
                "info": {
                    "title": track.title,
                    "author": track.author,
                    "uri": track.uri,
                    "length": track.length
                }
            }
            session.add(PlaylistTrack(
                playlist_id=playlist.id,
                track_data=track_data,
                added_at=datetime.datetime.utcnow().isoformat()
            ))
            await session.commit()
            
            await interaction.response.send_message(f"Added **{track.title}** to Liked Songs ❤️", ephemeral=True)

    @playlist_group.command(name="delete", description="Delete a playlist")
    @app_commands.describe(name="The name of the playlist to delete")
    async def delete(self, interaction: discord.Interaction, name: str):
        async with async_session_factory() as session:
            playlist = await self.get_user_playlist(interaction.user.id, name, session)
            if not playlist:
                await interaction.response.send_message(f"Playlist **{name}** not found.", ephemeral=True)
                return

            await session.delete(playlist)
            await session.commit()
            await interaction.response.send_message(f"Deleted playlist **{name}**.", ephemeral=True)

    @delete.autocomplete("name")
    async def delete_autocomplete(self, interaction: discord.Interaction, current: str):
        async with async_session_factory() as session:
            stmt = select(Playlist.name).where(Playlist.user_id == interaction.user.id, Playlist.name.ilike(f"%{current}%")).limit(25)
            playlists = (await session.execute(stmt)).scalars().all()
            return [app_commands.Choice(name=p, value=p) for p in playlists]

async def setup(bot):
    await bot.add_cog(PlaylistCog(bot))
