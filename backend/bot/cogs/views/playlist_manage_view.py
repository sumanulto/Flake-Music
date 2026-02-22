import discord
from discord import app_commands
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from backend.database.core.db import async_session_factory
from backend.database.models.models import Playlist, PlaylistTrack, User
import wavelink
import datetime
import logging

logger = logging.getLogger(__name__)

OWNER_ONLY_MSG = "This button can only be used by the user who executed the command."


def format_duration(ms: int) -> str:
    """Convert milliseconds to MM:SS string."""
    seconds = int(ms / 1000)
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------

class AddTracksModal(discord.ui.Modal, title="Add Tracks to Playlist"):
    query = discord.ui.TextInput(
        label="Song / URL",
        placeholder="Enter song name or YouTube/Spotify URL...",
        style=discord.TextStyle.short,
        max_length=200,
    )

    def __init__(self, playlist_name: str, playlist_id: int):
        super().__init__()
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        raw_query = self.query.value.strip()

        # YouTube URL fallback
        from backend.utils.youtube import extract_info
        resolved_query = raw_query
        if "youtube.com" in raw_query or "youtu.be" in raw_query:
            info = await extract_info(raw_query)
            if info:
                title = info.get("title")
                artist = info.get("artist") or info.get("uploader")
                if title:
                    resolved_query = f"ytmsearch:{title} {artist}" if artist else f"ytmsearch:{title}"

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(resolved_query)
        except Exception as e:
            logger.warning(f"Search failed for {resolved_query}: {e}")
            await interaction.followup.send("❌ Could not search for that track.", ephemeral=True)
            return

        if not tracks:
            await interaction.followup.send("❌ No tracks found.", ephemeral=True)
            return

        track = tracks[0] if isinstance(tracks, list) else tracks.tracks[0]

        track_data = {
            "encoded": track.encoded,
            "info": {
                "title": track.title,
                "author": track.author,
                "uri": track.uri,
                "length": track.length,
                "is_stream": track.is_stream,
            },
        }

        try:
            async with async_session_factory() as session:
                new_track = PlaylistTrack(
                    playlist_id=self.playlist_id,
                    track_data=track_data,
                    added_at=datetime.datetime.utcnow().isoformat(),
                )
                session.add(new_track)
                await session.commit()
        except Exception as e:
            logger.error(f"DB error adding track: {e}")
            await interaction.followup.send("❌ Failed to save track to playlist.", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ Added **{track.title}** (`{format_duration(track.length)}`) to **{self.playlist_name}**.",
            ephemeral=True,
        )


class RemoveTrackModal(discord.ui.Modal, title="Remove Track"):
    track_number = discord.ui.TextInput(
        label="Track Number",
        placeholder="Enter the track number to remove (from /playlist manage → View Tracks)...",
        style=discord.TextStyle.short,
        max_length=5,
    )

    def __init__(self, playlist_name: str, playlist_id: int):
        super().__init__()
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        raw_val = self.track_number.value.strip()
        if not raw_val.isdigit():
            await interaction.followup.send("❌ Please enter a valid track number.", ephemeral=True)
            return

        index = int(raw_val) - 1  # 0-indexed

        try:
            async with async_session_factory() as session:
                stmt = (
                    select(Playlist)
                    .where(Playlist.id == self.playlist_id)
                    .options(selectinload(Playlist.tracks))
                )
                playlist = (await session.execute(stmt)).scalar_one_or_none()

                if not playlist or not playlist.tracks:
                    await interaction.followup.send("❌ Playlist not found or empty.", ephemeral=True)
                    return

                if index < 0 or index >= len(playlist.tracks):
                    await interaction.followup.send(
                        f"❌ Track number out of range. Playlist has **{len(playlist.tracks)}** tracks.",
                        ephemeral=True,
                    )
                    return

                target = playlist.tracks[index]
                title = target.track_data.get("info", target.track_data).get("title", "Unknown")
                await session.delete(target)
                await session.commit()

            await interaction.followup.send(
                f"✅ Removed **{title}** (track #{index + 1}) from **{self.playlist_name}**.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"DB error removing track: {e}")
            await interaction.followup.send("❌ Failed to remove track.", ephemeral=True)


# ---------------------------------------------------------------------------
# Track List Paginator (50 tracks per page, Previous / Next buttons)
# ---------------------------------------------------------------------------

TRACKS_PER_PAGE = 50


class TrackListView(discord.ui.View):
    """Paginated ephemeral view for listing tracks with ◀ Previous / Next ▶ buttons."""

    def __init__(self, tracks: list, playlist_name: str, owner_id: int):
        super().__init__(timeout=120)
        self.tracks = tracks
        self.playlist_name = playlist_name
        self.owner_id = owner_id
        self.page = 0
        self.total_pages = max(1, -(-len(tracks) // TRACKS_PER_PAGE))  # ceiling div
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.total_pages - 1

    def build_embed(self) -> discord.Embed:
        start = self.page * TRACKS_PER_PAGE
        chunk = self.tracks[start : start + TRACKS_PER_PAGE]

        embed = discord.Embed(
            title=f"📋 {self.playlist_name}",
            color=discord.Color.blurple(),
        )
        lines = []
        for i, t in enumerate(chunk, start=start + 1):
            info = t.track_data.get("info", t.track_data)
            title = info.get("title", "Unknown")
            length = info.get("length", 0)
            lines.append(f"**{i}.** 🎵 {title} — `[{format_duration(length)}]`")
        embed.description = "\n".join(lines)
        embed.set_footer(
            text=f"Page {self.page + 1} / {self.total_pages}  •  {len(self.tracks)} tracks total"
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(OWNER_ONLY_MSG, ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


# ---------------------------------------------------------------------------
# Main View
# ---------------------------------------------------------------------------

class PlaylistManageView(discord.ui.View):
    """
    Management panel for a single playlist.
    Only the user who invoked  /playlist manage  can interact with the buttons.
    Any other user gets an ephemeral "owner-only" message.
    """

    def __init__(self, owner_id: int, playlist_name: str, playlist_id: int):
        super().__init__(timeout=300)  # 5-minute window
        self.owner_id = owner_id
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(OWNER_ONLY_MSG, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # Disable all buttons when view times out
        for item in self.children:
            item.disabled = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _fetch_playlist(self):
        async with async_session_factory() as session:
            stmt = (
                select(Playlist)
                .where(Playlist.id == self.playlist_id)
                .options(selectinload(Playlist.tracks))
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    @discord.ui.button(
        label="Add Tracks",
        emoji="➕",
        style=discord.ButtonStyle.success,
        row=0,
        custom_id="pl_add_tracks",
    )
    async def add_tracks(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddTracksModal(self.playlist_name, self.playlist_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="View Tracks",
        emoji="📋",
        style=discord.ButtonStyle.primary,
        row=0,
        custom_id="pl_view_tracks",
    )
    async def view_tracks(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        playlist = await self._fetch_playlist()
        if not playlist or not playlist.tracks:
            await interaction.followup.send(
                f"**{self.playlist_name}** has no tracks yet.", ephemeral=True
            )
            return

        view = TrackListView(
            tracks=playlist.tracks,
            playlist_name=self.playlist_name,
            owner_id=self.owner_id,
        )
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Remove Tracks",
        emoji="➖",
        style=discord.ButtonStyle.secondary,
        row=1,
        custom_id="pl_remove_tracks",
    )
    async def remove_tracks(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveTrackModal(self.playlist_name, self.playlist_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Delete",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        row=1,
        custom_id="pl_delete",
    )
    async def delete_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show a confirmation view before deleting
        confirm_view = _ConfirmDeleteView(
            owner_id=self.owner_id,
            playlist_name=self.playlist_name,
            playlist_id=self.playlist_id,
            parent_view=self,
            parent_message=interaction.message,
        )
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to delete **{self.playlist_name}**? This cannot be undone.",
            view=confirm_view,
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# Confirmation view for Delete
# ---------------------------------------------------------------------------

class _ConfirmDeleteView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        playlist_name: str,
        playlist_id: int,
        parent_view: PlaylistManageView,
        parent_message: discord.Message,
    ):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id
        self.parent_view = parent_view
        self.parent_message = parent_message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(OWNER_ONLY_MSG, ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            async with async_session_factory() as session:
                stmt = select(Playlist).where(Playlist.id == self.playlist_id)
                playlist = (await session.execute(stmt)).scalar_one_or_none()
                if playlist:
                    await session.delete(playlist)
                    await session.commit()

            # Disable all buttons on the original management panel
            for item in self.parent_view.children:
                item.disabled = True
            try:
                await self.parent_message.edit(
                    content=f"~~{self.playlist_name}~~ ❌ Playlist deleted.",
                    view=self.parent_view,
                )
            except Exception:
                pass

            # Stop this confirmation view too
            self.stop()
            await interaction.followup.send(f"✅ **{self.playlist_name}** has been deleted.", ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to delete playlist {self.playlist_id}: {e}")
            await interaction.followup.send("❌ Failed to delete playlist.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.send_message("Deletion cancelled.", ephemeral=True)
