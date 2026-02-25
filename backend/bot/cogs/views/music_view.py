"""
music_view.py — Discord UI buttons for the player controller.

All navigation (skip, previous, loop, shuffle) is routed through the
session queue (sq), NOT through Lavalink's internal queue, because
Lavalink's queue is intentionally kept empty — we manage ordering ourselves.
"""
from __future__ import annotations

import logging
import discord
import wavelink
from backend.bot import session_queue as sq

logger = logging.getLogger(__name__)


class MusicView(discord.ui.View):
    def __init__(
        self,
        bot,
        player: wavelink.Player,
        dashboard_url: str | None = None,
        music_cog=None,
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.player = player
        self.music_cog = music_cog  # reference to Music cog for session helpers

        if dashboard_url:
            self.add_item(
                discord.ui.Button(
                    label="Dashboard",
                    style=discord.ButtonStyle.link,
                    url=dashboard_url,
                    row=2,
                )
            )

        like_btn = discord.ui.Button(
            label="💖 Like",
            style=discord.ButtonStyle.secondary,
            custom_id="like_song_btn",
            row=2,
        )
        like_btn.callback = self.like_action
        self.add_item(like_btn)

        self.update_buttons()

    # ------------------------------------------------------------------ #
    # Helper: get the session for this player's guild                     #
    # ------------------------------------------------------------------ #
    def _session(self):
        if self.player and self.player.guild:
            return sq.get(self.player.guild.id)
        return None

    # ------------------------------------------------------------------ #
    # Update button visuals to match current session state                #
    # ------------------------------------------------------------------ #
    def update_buttons(self):
        session = self._session()

        # Play / Pause
        pp_btn = next((x for x in self.children if getattr(x, "custom_id", None) == "play_pause"), None)
        if pp_btn:
            if self.player.paused:
                pp_btn.emoji = "▶️"
                pp_btn.style = discord.ButtonStyle.success
            else:
                pp_btn.emoji = "⏸️"
                pp_btn.style = discord.ButtonStyle.secondary

        # Loop — reflect session repeat_mode, not player.queue.mode
        loop_btn = next((x for x in self.children if getattr(x, "custom_id", None) == "loop"), None)
        if loop_btn and session:
            if session.repeat_mode == "off":
                loop_btn.emoji = "🔁"
                loop_btn.style = discord.ButtonStyle.secondary
            elif session.repeat_mode == "all":
                loop_btn.emoji = "🔁"
                loop_btn.style = discord.ButtonStyle.success
            elif session.repeat_mode == "one":
                loop_btn.emoji = "🔂"
                loop_btn.style = discord.ButtonStyle.success

        # Shuffle — highlight when enabled
        shuf_btn = next((x for x in self.children if getattr(x, "custom_id", None) == "shuffle"), None)
        if shuf_btn and session:
            shuf_btn.style = (
                discord.ButtonStyle.success if session.shuffle_enabled
                else discord.ButtonStyle.secondary
            )

    # ------------------------------------------------------------------ #
    # Internal: defer first, then rebuild & refresh the player message    #
    # ------------------------------------------------------------------ #
    async def _ack_and_refresh(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.update_buttons()
        if self.music_cog:
            await self.music_cog.refresh_player_interface(
                self.player.guild.id, force_new=False
            )
        else:
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

    # ================================================================== #
    # Buttons
    # ================================================================== #

    # -- Previous -------------------------------------------------------
    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0, custom_id="prev")
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()

        session = self._session()
        if not session or session.current_index <= 0:
            await interaction.response.send_message("Already at the first track.", ephemeral=True)
            return

        await interaction.response.defer()
        prev_track = session.previous()
        if prev_track and self.music_cog:
            await self.music_cog._play_session_track(self.player, prev_track)

    # -- Play / Pause ---------------------------------------------------
    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, row=0, custom_id="play_pause")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()
        await interaction.response.defer()
        await self.player.pause(not self.player.paused)
        self.update_buttons()
        if self.music_cog:
            await self.music_cog.refresh_player_interface(self.player.guild.id, force_new=False)
        else:
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

    # -- Skip (Next) ----------------------------------------------------
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0, custom_id="next")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()

        session = self._session()
        if not session:
            return await interaction.response.defer()

        await interaction.response.defer()
        next_track = session.advance()
        if next_track and self.music_cog:
            await self.music_cog._play_session_track(self.player, next_track)
        else:
            # End of queue — stop cleanly
            self.player.queue.clear()
            await self.player.stop()

    # -- Stop -----------------------------------------------------------
    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=0, custom_id="stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()

        await interaction.response.defer()
        guild_id = self.player.guild.id
        self.player.queue.clear()
        sq.clear(guild_id)
        await self.player.stop()
        await self.player.disconnect()

        if self.music_cog and guild_id in self.music_cog.player_messages:
            try:
                cid, mid = self.music_cog.player_messages[guild_id]
                ch = self.bot.get_channel(cid)
                if ch:
                    m = await ch.fetch_message(mid)
                    await m.delete()
            except Exception:
                pass
            self.music_cog.player_messages.pop(guild_id, None)

    # -- Shuffle --------------------------------------------------------
    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1, custom_id="shuffle")
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()
        session = self._session()
        if not session:
            return await interaction.response.defer()
        if session.shuffle_enabled:
            session.unshuffle()
        else:
            session.shuffle()
        await self._ack_and_refresh(interaction)

    # -- Volume Down ----------------------------------------------------
    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1, custom_id="vol_down")
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()
        vol = max(0, self.player.volume - 10)
        await self.player.set_volume(vol)
        await self._ack_and_refresh(interaction)

    # -- Volume Up ------------------------------------------------------
    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1, custom_id="vol_up")
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()
        vol = min(100, self.player.volume + 10)
        await self.player.set_volume(vol)
        await self._ack_and_refresh(interaction)

    # -- Loop (repeat) --------------------------------------------------
    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=1, custom_id="loop")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.defer()
        session = self._session()
        if not session:
            return await interaction.response.defer()
        # Cycle: off -> all -> one -> off
        if session.repeat_mode == "off":
            session.repeat_mode = "all"
        elif session.repeat_mode == "all":
            session.repeat_mode = "one"
        else:
            session.repeat_mode = "off"
        await self._ack_and_refresh(interaction)

    async def like_action(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.player or not self.player.current:
            await interaction.followup.send("Nothing playing.", ephemeral=True)
            return

        track = self.player.current

        from backend.database.core.db import async_session_factory
        from backend.database.models.models import Playlist, PlaylistTrack, User
        from sqlalchemy import select
        import datetime

        async with async_session_factory() as session:
            # Get Liked Songs playlist
            stmt = select(Playlist).where(Playlist.user_id == interaction.user.id, Playlist.is_liked_songs == True)
            playlist = (await session.execute(stmt)).scalar_one_or_none()

            if not playlist:
                # Ensure user exists
                u_stmt = select(User).where(User.id == interaction.user.id)
                if not (await session.execute(u_stmt)).scalar_one_or_none():
                    session.add(User(id=interaction.user.id, username=interaction.user.name))

                playlist = Playlist(name="Liked Songs", user_id=interaction.user.id, is_liked_songs=True)
                session.add(playlist)
                await session.commit()
                await session.refresh(playlist)

            # Check for duplicate track
            await session.refresh(playlist, ["tracks"])
            for t in playlist.tracks:
                # Handle both formats for duplicate checking
                t_info = t.track_data.get("info", t.track_data)
                if t_info.get("uri") == track.uri:
                    await interaction.followup.send("Already in Liked Songs!", ephemeral=True)
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

            await interaction.followup.send(f"Added **{track.title}** to Liked Songs ❤️", ephemeral=True)
