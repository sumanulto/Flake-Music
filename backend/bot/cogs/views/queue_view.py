import os
import discord
import wavelink
from backend.bot import session_queue as sq

TRACKS_PER_PAGE = 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_emoji(uri: str) -> str:
    if not uri:
        return "🎵"
        
    use_custom_icon = os.getenv("USE_CUSTOM_EMOJIS_ICON", "False").lower() == "true"
    
    if "spotify" in uri:
        return os.getenv("EMOJI_SPOTIFY", "<:spotify:1476099462463230116>") if use_custom_icon else "🟢"
    if "youtube" in uri or "youtu.be" in uri:
        return os.getenv("EMOJI_YOUTUBE", "<:youtube:1476099464744800408>") if use_custom_icon else "🔴"
    if "soundcloud" in uri:
        return "🟠"
    return "🎵"


def _fmt_duration(ms: int) -> str:
    secs = int(ms / 1000)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _total_duration_str(tracks: list[sq.TrackInfo]) -> str:
    return _fmt_duration(sum(t.duration for t in tracks))


def _parse_positions(raw: str) -> list[int]:
    """
    Parse a position string like '1,2,5', '3-4', '3,6-7,1' into a
    sorted list of unique 1-based integers. Returns empty list on error.
    """
    positions: set[int] = set()
    # Remove surrounding brackets/parens just in case
    raw = raw.strip().strip("()[]")
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                lo, hi = int(bounds[0].strip()), int(bounds[1].strip())
                for n in range(min(lo, hi), max(lo, hi) + 1):
                    positions.add(n)
            except ValueError:
                return []
        else:
            try:
                positions.add(int(part))
            except ValueError:
                return []
    return sorted(positions)


# ---------------------------------------------------------------------------
# Delete Modal
# ---------------------------------------------------------------------------

class DeleteModal(discord.ui.Modal, title="Delete Tracks from Queue"):
    positions_input = discord.ui.TextInput(
        label="Track number(s) to remove",
        placeholder="e.g.  1,2,5  or  3-4  or  3,6-7,1",
        style=discord.TextStyle.short,
        required=True,
        max_length=100,
    )

    def __init__(self, queue_view: "QueueView"):
        super().__init__()
        self.queue_view = queue_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.positions_input.value
        positions = _parse_positions(raw)

        session = self.queue_view.session
        upcoming = self.queue_view._upcoming()          # list of (global_idx, track)

        if not positions:
            await interaction.response.send_message(
                "❌ Invalid format. Use `1,2,5` or `3-4` or `3,6-7,1`.", ephemeral=True
            )
            return

        # Map 1-based upcoming positions → global session indices
        global_indices_to_remove: set[int] = set()
        invalid: list[int] = []
        for pos in positions:
            idx = pos - 1  # convert to 0-based index into upcoming
            if 0 <= idx < len(upcoming):
                global_indices_to_remove.add(upcoming[idx][0])
            else:
                invalid.append(pos)

        if not global_indices_to_remove:
            await interaction.response.send_message(
                f"❌ No valid positions found (upcoming queue has {len(upcoming)} tracks).",
                ephemeral=True,
            )
            return

        # Remove tracks in reverse order to keep indices stable
        for gi in sorted(global_indices_to_remove, reverse=True):
            del session.tracks[gi]
            # Adjust current_index if a removed track was before/at it
            if gi < session.current_index:
                session.current_index -= 1
            elif gi == session.current_index:
                # Current track was deleted — clamp to valid position
                session.current_index = min(session.current_index, len(session.tracks) - 1)

        removed_count = len(global_indices_to_remove)
        warning = ""
        if invalid:
            warning = f"\n⚠️ Position(s) {', '.join(str(x) for x in invalid)} out of range."

        # Clamp page in case the queue shrank
        total_pages = self.queue_view._total_pages()
        self.queue_view.page = min(self.queue_view.page, max(0, total_pages - 1))

        self.queue_view._update_buttons()
        embed = self.queue_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.queue_view)

        if warning:
            await interaction.followup.send(
                f"✅ Removed **{removed_count}** track(s).{warning}", ephemeral=True
            )


# ---------------------------------------------------------------------------
# QueueView
# ---------------------------------------------------------------------------

class QueueView(discord.ui.View):
    def __init__(self, session: sq.GuildSession, player: wavelink.Player | None):
        super().__init__(timeout=180)
        self.session = session
        self.player = player
        self.page = 0
        self._update_buttons()

    # ------------------------------------------------------------------ #

    def _upcoming(self) -> list[tuple[int, sq.TrackInfo]]:
        """(global_index, track) for every track after current_index."""
        idx = self.session.current_index
        return [(i, t) for i, t in enumerate(self.session.tracks) if i > idx]

    def _total_pages(self) -> int:
        count = len(self._upcoming())
        return max(1, -(-count // TRACKS_PER_PAGE))   # ceiling division

    def _update_buttons(self):
        total = self._total_pages()
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            cid = item.custom_id
            if cid in ("q_first", "q_prev"):
                item.disabled = self.page == 0
            elif cid in ("q_next", "q_last"):
                item.disabled = self.page >= total - 1

    # ------------------------------------------------------------------ #

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Music Queue",
            color=discord.Color.from_rgb(43, 45, 49),
        )

        # --- Now Playing ---
        current = self.session.current
        if current:
            icon = _source_emoji(current.uri)
            dur = _fmt_duration(current.duration)
            title_link = f"[{current.title}]({current.uri})" if current.uri else current.title
            embed.add_field(
                name="Now Playing:",
                value=f"{icon} {title_link}\n`[{dur}]` — **{current.author}**",
                inline=False,
            )
        else:
            embed.add_field(name="Now Playing:", value="*Nothing*", inline=False)

        # --- Upcoming Queue ---
        upcoming = self._upcoming()
        total_pages = self._total_pages()

        if upcoming:
            start = self.page * TRACKS_PER_PAGE
            slice_ = upcoming[start: start + TRACKS_PER_PAGE]

            lines = []
            for pos, (_, track) in enumerate(slice_, start=start + 1):
                icon = _source_emoji(track.uri)
                dur = _fmt_duration(track.duration)
                title_link = f"[{track.title}]({track.uri})" if track.uri else track.title
                lines.append(f"`{pos}.` {icon} `[{dur}]` {title_link}")

            embed.add_field(
                name="Upcoming Queue:",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(name="Upcoming Queue:", value="*Queue is empty*", inline=False)

        total_dur = _total_duration_str(self.session.tracks)
        embed.set_footer(
            text=f"Page {self.page + 1}/{total_pages}  •  Total Duration: {total_dur}  •  🗑️ delete by number | 🗑️All clears upcoming"
        )
        return embed

    # ------------------------------------------------------------------ #

    async def _refresh(self, interaction: discord.Interaction):
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    # Row 0: pagination + 🗑️ (delete specific)
    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary, custom_id="q_first", row=0)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await self._refresh(interaction)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="q_prev", row=0)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="q_next", row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self._total_pages() - 1, self.page + 1)
        await self._refresh(interaction)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary, custom_id="q_last", row=0)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self._total_pages() - 1
        await self._refresh(interaction)

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="q_delete", row=0)
    async def delete_tracks(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open a modal so the user can type which track numbers to remove."""
        upcoming = self._upcoming()
        if not upcoming:
            await interaction.response.send_message(
                "There are no upcoming tracks to delete.", ephemeral=True
            )
            return
        await interaction.response.send_modal(DeleteModal(self))

    # Row 1: 🗑️All
    @discord.ui.button(label="🗑️ All", style=discord.ButtonStyle.danger, custom_id="q_clear_all", row=1)
    async def clear_all_upcoming(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove all upcoming tracks; keep the bot playing the current song."""
        session = self.session
        ci = session.current_index

        # Keep only tracks up to and including the current one
        session.tracks = session.tracks[: ci + 1]
        session._original_tracks = []   # reset shuffle baseline

        # Lavalink queue has nothing to do with our session, but clear it too
        if self.player:
            self.player.queue.clear()

        self.page = 0
        self._update_buttons()
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
