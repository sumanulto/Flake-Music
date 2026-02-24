import discord
from discord import app_commands
from discord.ext import commands
import os

GITHUB_URL = os.getenv("GITHUB_URL", "")

# ─── Help content definition ──────────────────────────────────────────────────

HELP_SECTIONS: dict[str, dict] = {
    "music": {
        "emoji": "🎵",
        "label": "Music",
        "description": "Music playback & control commands",
        "commands": [
            ("/play `<song>`", "Play a song from YouTube, Spotify, and more"),
            ("/skip", "Skip the current song"),
            ("/pause", "Pause or resume playback"),
            ("/stop", "Stop music and disconnect the bot"),
            ("/volume `<1–100>`", "Adjust the player volume"),
            ("/queue", "View all songs in the current queue"),
        ],
    },
    "filters": {
        "emoji": "🎛️",
        "label": "Filters",
        "description": "Audio effect / filter presets powered by Lavalink",
        "commands": [
            ("/filter `Nightcore`", "Speed up & raise the pitch"),
            ("/filter `Vaporwave`", "Slow down & lower the pitch"),
            ("/filter `Karaoke`", "Attempt to remove vocals"),
            ("/filter `8D Audio`", "360° panning rotation effect"),
            ("/filter `Tremolo`", "Rapid volume oscillation"),
            ("/filter `Vibrato`", "Rapid pitch oscillation"),
            ("/filter `Clear/Off`", "Remove all active filters"),
        ],
    },
    "playlist": {
        "emoji": "📋",
        "label": "Playlist",
        "description": "Create and manage your personal playlists",
        "commands": [
            ("/playlist create `<name>`", "Create a new playlist"),
            ("/playlist add `<name>` `<song>`", "Add a track to a playlist"),
            ("/playlist play `<name>`", "Queue and play a saved playlist"),
            ("/playlist list", "List all your saved playlists"),
            ("/playlist manage `<name>`", "Open the playlist management panel"),
            ("/playlist delete `<name>`", "Delete a playlist permanently"),
            ("/like", "Save the currently playing song to Liked Songs"),
        ],
    },
    "general": {
        "emoji": "⚙️",
        "label": "General",
        "description": "Bot info & utility commands",
        "commands": [
            ("/help", "Show this help menu"),
            ("/status", "Display bot & system status"),
        ],
    },
}

# ─── Embed builders ───────────────────────────────────────────────────────────


def _overview_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📖  Flake Music — Help Menu",
        description=(
            "Flake Music is a feature-rich Discord music bot.\n"
            "It supports **YouTube**, **Spotify**, and more.\n\n"
            "Use `/play <song>` to get started — just join a voice channel first!\n\u200b"
        ),
        color=0x5865F2,
    )

    categories = "\n".join(
        f"{i + 1}. {v['emoji']} {v['label']}" for i, v in enumerate(HELP_SECTIONS.values())
    )
    embed.add_field(name=f"Available Categories [{len(HELP_SECTIONS)}]", value=categories, inline=True)
    embed.add_field(
        name="\u200b",
        value=(
            "**ℹ️ Get Started**\n"
            "Join a voice channel, then run `/play <song or URL>`.\n\n"
            "Use the dropdown below to browse each command category."
        ),
        inline=True,
    )
    embed.set_footer(text="Select a category from the dropdown to learn more.")
    return embed


def _section_embed(key: str) -> discord.Embed:
    section = HELP_SECTIONS[key]
    embed = discord.Embed(
        title=f"{section['emoji']}  {section['label']} Commands",
        description=section["description"] + "\n\u200b",
        color=0x5865F2,
    )
    for name, value in section["commands"]:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="Use the dropdown to switch categories.")
    return embed


# ─── UI Components ────────────────────────────────────────────────────────────


class HelpSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label="Overview",
                description="Back to the main help menu",
                emoji="🏠",
                value="overview",
            )
        ] + [
            discord.SelectOption(
                label=v["label"],
                description=v["description"],
                emoji=v["emoji"],
                value=key,
            )
            for key, v in HELP_SECTIONS.items()
        ]
        super().__init__(
            placeholder="Select a category…",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        value = self.values[0]
        embed = _overview_embed() if value == "overview" else _section_embed(value)
        await interaction.response.edit_message(embed=embed)


class HelpView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=180)
        self.add_item(HelpSelect())
        if GITHUB_URL:
            self.add_item(
                discord.ui.Button(
                    label="GitHub",
                    url=GITHUB_URL,
                    emoji="🐙",
                    style=discord.ButtonStyle.link,
                )
            )


# ─── Cog ──────────────────────────────────────────────────────────────────────


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Show the Flake Music help menu")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = _overview_embed()
        await interaction.response.send_message(embed=embed, view=HelpView())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
